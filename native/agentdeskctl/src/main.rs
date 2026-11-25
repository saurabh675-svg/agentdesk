//! agentdeskctl — headless control of AgentDesk (0.6).
//!
//! Speaks to the loopback API (127.0.0.1:8756) with the desktop token read
//! from ``--token`` / ``AGENTDESK_API_TOKEN`` / ``data/api-token.txt``.
//! Every subcommand prints JSON so it composes in scripts.

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "agentdeskctl", version, about = "Headless AgentDesk control")]
struct Cli {
    #[arg(long, default_value = "http://127.0.0.1:8756")]
    base: String,
    #[arg(long, env = "AGENTDESK_API_TOKEN")]
    token: Option<String>,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// GET /api/health
    Health,
    /// GET /api/sessions
    Sessions,
    /// GET /api/diagnostics/native (Rust core + sidecars)
    Native,
    /// GET /api/browser/challenge
    Challenge,
    /// GET /api/mcp-server/capabilities
    McpCaps,
}

fn get_json(base: &str, token: &Option<String>, path: &str) -> Result<serde_json::Value> {
    let client = reqwest::blocking::Client::builder().timeout(std::time::Duration::from_secs(15)).build()?;
    let mut req = client.get(format!("{base}{path}"));
    if let Some(t) = token.as_deref().filter(|s| !s.is_empty()) {
        req = req.header("Authorization", format!("Bearer {t}"));
    }
    let resp = req.send().with_context(|| format!("GET {path}"))?;
    let val: serde_json::Value = resp.json().context("parse JSON")?;
    Ok(val)
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let path = match &cli.cmd {
        Cmd::Health => "/api/health",
        Cmd::Sessions => "/api/sessions",
        Cmd::Native => "/api/diagnostics/native",
        Cmd::Challenge => "/api/browser/challenge",
        Cmd::McpCaps => "/api/mcp-server/capabilities",
    };
    let val = get_json(&cli.base, &cli.token, path)?;
    println!("{}", serde_json::to_string_pretty(&val)?);
    Ok(())
}
