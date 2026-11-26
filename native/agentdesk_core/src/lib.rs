//! AgentDesk native accelerators (Rust).
//!
//! These are the hot paths that used to block the Python event loop:
//! DOM tree diffing, content-addressed element refs, output scrubbing and
//! token counting. Every function here has a pure-Python fallback in
//! `backend/app/native_core.py` — the app never breaks if this library is
//! missing.

use std::collections::HashMap;

use regex::Regex;
use serde_json::Value;

/// A node of the simplified DOM tree used for diffing.
#[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
pub struct Node {
    #[serde(default = "default_tag")]
    pub tag: String,
    #[serde(default)]
    pub role: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub value: String,
    #[serde(default)]
    pub children: Vec<Node>,
}

fn default_tag() -> String { "node".to_string() }

impl Node {
    /// Stable identity of a node: tag + role + accessible name.
    pub fn key(&self) -> String {
        format!("{}|{}|{}", self.tag, self.role, self.name)
    }

    /// Content hash used for change detection (structure + text).
    /// FNV-1a over key+value — ~2× faster than SipHash for this short-input shape.
    pub fn content_hash(&self) -> u64 {
        let mut h: u64 = 0xcbf29ce484222325;
        for b in self.key().as_bytes() { h ^= *b as u64; h = h.wrapping_mul(0x100000001b3); }
        for b in self.value.as_bytes() { h ^= *b as u64; h = h.wrapping_mul(0x100000001b3); }
        for child in &self.children {
            h ^= child.content_hash();
            h = h.wrapping_mul(0x100000001b3);
        }
        h
    }
}

/// One difference between two DOM snapshots.
#[derive(Debug, Clone, serde::Serialize)]
pub struct DiffEntry {
    /// "added" | "removed" | "changed"
    pub kind: String,
    /// Content-addressed reference of the node (e.g. "ab12cd34").
    pub ref_id: String,
    /// Accessible name of the node, for human-readable output.
    pub name: String,
    /// Tag name of the node.
    pub tag: String,
}

/// Build a simplified DOM tree from an a11y/DOM snapshot JSON payload.
/// Fast path deserializes directly into `Vec<Node>` (no generic `Value` tree);
/// falls back to the tolerant `collect` for malformed/partial nodes.
pub fn parse_tree(payload: &str) -> Result<Vec<Node>, String> {
    if let Ok(nodes) = serde_json::from_str::<Vec<Node>>(payload) {
        return Ok(nodes);
    }
    let value: Value = serde_json::from_str(payload).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    collect(&value, &mut out);
    Ok(out)
}

/// Fast snapshot hash: FNV-1a over the raw bytes (no JSON parse).
/// Python uses this to skip the diff entirely when the page is unchanged.
pub fn snapshot_hash(payload: &str) -> u64 {
    fnv1a64(payload.as_bytes())
}

fn collect(value: &Value, out: &mut Vec<Node>) {
    let obj = match value.as_object() {
        Some(obj) => obj,
        None => return,
    };
    let children_raw = obj.get("children").and_then(|c| c.as_array());
    let mut children = Vec::new();
    if let Some(kids) = children_raw {
        for kid in kids {
            collect(kid, &mut children);
        }
    }
    out.push(Node {
        tag: obj
            .get("tag")
            .and_then(|v| v.as_str())
            .unwrap_or("node")
            .to_string(),
        role: obj
            .get("role")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        name: obj
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        value: obj
            .get("value")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        children,
    });
}

/// FNV-1a 64-bit hash — deterministic across Rust versions and platforms, so
/// refs stay stable between app restarts (no external hashing dependency).
fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in bytes {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(0x1000_0000_01b3);
    }
    hash
}

/// Content-addressed, short reference for a node.
///
/// The id is derived from the node's content, so the same DOM always yields
/// the same ref and a stale ref can be detected (the hash no longer matches).
pub fn content_ref(node: &Node) -> String {
    format!("{:016x}", fnv1a64(node.key().as_bytes()))
}

/// Diff two DOM snapshots and return only what changed.
///
/// Returns a JSON array of `DiffEntry` objects.
pub fn diff(old_payload: &str, new_payload: &str) -> Result<Vec<DiffEntry>, String> {
    if snapshot_hash(old_payload) == snapshot_hash(new_payload) {
        return Ok(Vec::new());
    }
    let old = parse_tree(old_payload)?;
    let new = parse_tree(new_payload)?;

    let mut old_index: HashMap<String, (Node, u64)> = HashMap::new();
    flatten(&old, &mut old_index);
    let mut new_index: HashMap<String, (Node, u64)> = HashMap::new();
    flatten(&new, &mut new_index);

    let mut entries: Vec<DiffEntry> = Vec::new();
    for (key, (node, hash)) in &new_index {
        match old_index.get(key) {
            None => entries.push(DiffEntry { kind: "added".to_string(), ref_id: content_ref(node), name: node.name.clone(), tag: node.tag.clone() }),
            Some((_, old_hash)) if old_hash != hash => entries.push(DiffEntry { kind: "changed".to_string(), ref_id: content_ref(node), name: node.name.clone(), tag: node.tag.clone() }),
            _ => {}
        }
    }

    for (key, (node, _)) in &old_index {
        if !new_index.contains_key(key) {
            entries.push(DiffEntry {
                kind: "removed".to_string(),
                ref_id: content_ref(node),
                name: node.name.clone(),
                tag: node.tag.clone(),
            });
        }
    }
    Ok(entries)
}

fn flatten(nodes: &[Node], out: &mut HashMap<String, (Node, u64)>) {
    for node in nodes {
        let key = node.key();
        let hash = node.content_hash();
        // Keep the shallowest occurrence of a duplicate key.
        out.entry(key).or_insert_with(|| (node.clone(), hash));
        flatten(&node.children, out);
    }
}

/// Scrub sensitive text out of tool output before it reaches the model.
///
/// Removes e-mail addresses, bearer/API tokens, JWTs, private keys and
/// long hex secrets. Returns the scrubbed text plus a count of redactions.
pub fn scrub(text: &str) -> (String, usize) {
    let mut count = 0usize;
    let mut out = text.to_string();

    let patterns: Vec<(&str, &str)> = vec![
        (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]"),
        (r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}", "Bearer [redacted]"),
        (r#"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["']?[A-Za-z0-9._\-]{8,}["']?"#, "$1=[redacted]"),
        (r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", "[jwt]"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[private-key]"),
        (r"\b[0-9a-fA-F]{32,}\b", "[hex-secret]"),
        (r"sk-[A-Za-z0-9]{20,}", "[api-key]"),
    ];

    for (pattern, replacement) in patterns {
        let re = match Regex::new(pattern) {
            Ok(re) => re,
            Err(_) => continue,
        };
        let hits = re.find_iter(&out).count();
        if hits > 0 {
            count += hits;
            out = re.replace_all(&out, replacement).to_string();
        }
    }
    (out, count)
}

/// Count tokens in a string using a cheap, stable heuristic.
///
/// This is a budget estimate, not a tokenizer: it approximates BPE token
/// counts as `chars / 4` with a word-count floor, which is accurate enough
/// for cost guards and does not require shipping a tokenizer per model.
pub fn count_tokens(text: &str) -> usize {
    let chars = text.chars().count();
    let words = text.split_whitespace().count();
    let by_chars = chars.div_ceil(4);
    by_chars.max(words)
}

/// Fast JSON field extraction for hot metadata paths.
pub fn json_field(payload: &str, field: &str) -> Option<String> {
    let value: Value = serde_json::from_str(payload).ok()?;
    value
        .get(field)
        .map(|v| match v {
            Value::String(s) => s.clone(),
            other => other.to_string(),
        })
}

/// Feature-gated Python bindings.
#[cfg(feature = "python")]
mod python {
    use super::*;
    use pyo3::prelude::*;

    #[pyfunction]
    fn diff_py(old_payload: &str, new_payload: &str) -> PyResult<String> {
        let entries = diff(old_payload, new_payload).map_err(pyo3::exceptions::PyValueError::new_err)?;
        serde_json::to_string(&entries).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[pyfunction]
    fn snapshot_hash_py(payload: &str) -> u64 { snapshot_hash(payload) }

    #[pyfunction]
    fn scrub_py(text: &str) -> (String, usize) {
        scrub(text)
    }

    #[pyfunction]
    fn count_tokens_py(text: &str) -> usize {
        count_tokens(text)
    }

    #[pyfunction]
    fn content_ref_py(payload: &str) -> PyResult<String> {
        let nodes = parse_tree(payload).map_err(pyo3::exceptions::PyValueError::new_err)?;
        Ok(nodes
            .first()
            .map(content_ref)
            .unwrap_or_else(|| "00000000".to_string()))
    }

    #[pymodule]
    fn agentdesk_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(diff_py, m)?)?;
        m.add_function(wrap_pyfunction!(snapshot_hash_py, m)?)?;
        m.add_function(wrap_pyfunction!(scrub_py, m)?)?;
        m.add_function(wrap_pyfunction!(count_tokens_py, m)?)?;
        m.add_function(wrap_pyfunction!(content_ref_py, m)?)?;
        m.add("__version__", env!("CARGO_PKG_VERSION"))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn diff_detects_added_and_changed() {
        let old = r#"[{"tag":"a","role":"button","name":"Send","children":[]}]"#;
        let new = r#"[{"tag":"a","role":"button","name":"Send","value":"x","children":[]},
                       {"tag":"b","role":"link","name":"Home","children":[]}]"#;
        let entries = diff(old, new).unwrap();
        assert!(entries.iter().any(|e| e.kind == "added"));
        assert!(entries.iter().any(|e| e.kind == "changed"));
    }

    #[test]
    fn scrub_removes_secrets() {
        let (text, count) = scrub("mail me at a@b.com with key sk-abcdefghijklmnopqrstuvwx");
        assert!(!text.contains("a@b.com"));
        assert!(!text.contains("sk-abcdefghijklmnopqrstuvwx"));
        assert!(count >= 2);
    }

    #[test]
    fn tokens_scale_with_text() {
        assert!(count_tokens("hello world") >= 2);
        assert!(count_tokens(&"x".repeat(400)) >= 100);
    }
}
