"""browser-pilot page snapshot JS — ported from browser-pilot (MIT-ish style).

Runs inside the page. Produces a numbered, LLM-friendly snapshot plus
readable main text, mirroring the browser-pilot extractPage() function.
"""

PILOT_ELEMENTS_JS = r"""
(limit) => {
  const MAX_ELEMENTS = limit || 120;
  const clean = (v) => String(v||'').replace(/\s+/g,' ').trim();
  document.querySelectorAll('[data-pilot-id]').forEach(el => el.removeAttribute('data-pilot-id'));
  const visible = (el) => {
    const s = window.getComputedStyle(el);
    if (!s) return false;
    if (s.display === 'none' || s.visibility === 'hidden' || s.visibility === 'collapse') return false;
    if (Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2;
  };
  const describeName = (el) => {
    const tag = el.tagName.toLowerCase();
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) return aria.slice(0,90);
    let text = clean(el.innerText || '');
    if (text) return text.slice(0,90);
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const type = (el.getAttribute('type')||'').toLowerCase();
      const val = type === 'password' ? '' : clean(el.value);
      return (clean(el.getAttribute('placeholder')) || val || clean(el.getAttribute('name')) || clean(el.getAttribute('id')) || tag).slice(0,90);
    }
    return (clean(el.getAttribute('title')) || clean(el.getAttribute('alt')) || clean(el.getAttribute('value')) || tag).slice(0,90);
  };
  const sel = ['a[href]','button','input:not([type="hidden"])','textarea','select','summary','[role="button"]','[role="link"]','[role="tab"]','[role="checkbox"]','[role="menuitem"]','[role="option"]','[role="searchbox"]','[contenteditable="true"]','[onclick]'].join(',');
  const seen = new Set();
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (out.length >= MAX_ELEMENTS) break;
    if (seen.has(el)) continue;
    seen.add(el);
    if (!visible(el)) continue;
    const idx = out.length;
    el.setAttribute('data-pilot-id', String(idx));
    el.setAttribute('data-adk-idx', String(idx));
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type')||'').toLowerCase();
    const item = { index: idx, id: idx, tag, name: describeName(el) };
    if (type) item.type = type;
    if (tag === 'a' && el.getAttribute('href')) item.href = clean(el.getAttribute('href')).slice(0,120);
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const val = type === 'password' ? '' : clean(el.value);
      if (val) item.value = val.slice(0,60);
      if (el.getAttribute('placeholder')) item.placeholder = clean(el.getAttribute('placeholder')).slice(0,60);
    }
    if (el.getAttribute('role')) item.role = el.getAttribute('role');
    if (el instanceof HTMLInputElement && (type === 'checkbox' || type === 'radio')) item.checked = el.checked;
    if (el.getAttribute('aria-expanded')) item.expanded = el.getAttribute('aria-expanded');
    if (el.disabled) item.disabled = true;
    const r = el.getBoundingClientRect();
    item.x = Math.round(r.x); item.y = Math.round(r.y); item.w = Math.round(r.width); item.h = Math.round(r.height);
    if (r.bottom < 0 || r.top > window.innerHeight) item.offscreen = true;
    out.push(item);
  }
  return out;
}
"""

PILOT_SNAPSHOT_JS = r"""
(opts) => {
  const MAX_ELEMENTS = (opts && opts.limit) || 120;
  const MAX_TEXT = (opts && opts.textLimit) || 3600;
  const clean = (v) => String(v||'').replace(/\s+/g,' ').trim();
  document.querySelectorAll('[data-pilot-id]').forEach(el => el.removeAttribute('data-pilot-id'));
  const visible = (el) => {
    const s = window.getComputedStyle(el);
    if (!s) return false;
    if (s.display === 'none' || s.visibility === 'hidden' || s.visibility === 'collapse') return false;
    if (Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2;
  };
  const describeName = (el) => {
    const tag = el.tagName.toLowerCase();
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) return aria.slice(0,90);
    let text = clean(el.innerText || '');
    if (text) return text.slice(0,90);
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const type = (el.getAttribute('type')||'').toLowerCase();
      const val = type === 'password' ? '' : clean(el.value);
      return (clean(el.getAttribute('placeholder')) || val || clean(el.getAttribute('name')) || clean(el.getAttribute('id')) || tag).slice(0,90);
    }
    return (clean(el.getAttribute('title')) || clean(el.getAttribute('alt')) || clean(el.getAttribute('value')) || tag).slice(0,90);
  };
  const sel = ['a[href]','button','input:not([type="hidden"])','textarea','select','summary','[role="button"]','[role="link"]','[role="tab"]','[role="checkbox"]','[role="menuitem"]','[role="option"]','[role="searchbox"]','[contenteditable="true"]','[onclick]'].join(',');
  const seen = new Set();
  const elements = [];
  for (const el of document.querySelectorAll(sel)) {
    if (elements.length >= MAX_ELEMENTS) break;
    if (seen.has(el)) continue;
    seen.add(el);
    if (!visible(el)) continue;
    const idx = elements.length;
    el.setAttribute('data-pilot-id', String(idx));
    el.setAttribute('data-adk-idx', String(idx));
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type')||'').toLowerCase();
    const item = { id: idx, index: idx, tag, name: describeName(el) };
    if (type) item.type = type;
    if (tag === 'a' && el.getAttribute('href')) item.href = clean(el.getAttribute('href')).slice(0,120);
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const val = type === 'password' ? '' : clean(el.value);
      if (val) item.value = val.slice(0,60);
      if (el.getAttribute('placeholder')) item.placeholder = clean(el.getAttribute('placeholder')).slice(0,60);
    }
    if (el.getAttribute('role')) item.role = el.getAttribute('role');
    if (el instanceof HTMLInputElement && (type === 'checkbox' || type === 'radio')) item.checked = el.checked;
    if (el.getAttribute('aria-expanded')) item.expanded = el.getAttribute('aria-expanded');
    if (el.disabled) item.disabled = true;
    if (el.getBoundingClientRect().bottom < 0 || el.getBoundingClientRect().top > window.innerHeight) item.offscreen = true;
    elements.push(item);
  }
  const main = document.querySelector('main, [role="main"], article') || document.body;
  const text = clean(main?.innerText || document.body?.innerText || '').slice(0, MAX_TEXT);
  return {
    url: location.href,
    title: document.title || '',
    scroll: { y: Math.round(window.scrollY), height: Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0), viewport: window.innerHeight },
    text, elements
  };
}
"""
