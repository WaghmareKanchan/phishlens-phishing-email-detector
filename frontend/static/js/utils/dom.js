// Small helpers shared by every view/controller.
export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const bandLabel = { phish: 'Phishing', warn: 'Suspicious', safe: 'Looks safe' };
export const pct = score => Math.round((Number(score) || 0) * 100);
// Timestamps arrive as ISO-8601 with "Z" (UTC); the browser converts them to the user's local time.
export const fmtDate = iso => iso ? new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
export const timeNow = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export const EMAIL_RX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const pwOk = p => p.length >= 6 && /[A-Za-z]/.test(p) && /\d/.test(p);
export function pwScore(p) {
  let n = 0;
  if (p.length >= 6) n++; if (p.length >= 10) n++;
  if (/[a-z]/.test(p) && /[A-Z]/.test(p)) n++;
  if (/\d/.test(p) && /[^A-Za-z0-9]/.test(p)) n++;
  return n;
}

export function showBanner(sel, msg) { const el = $(sel); if (!el) return; el.textContent = msg || ''; el.hidden = !msg; }
export function fieldErr(inputId, msg) {
  $('#' + inputId + 'Err').textContent = msg || '';
  const i = $('#' + inputId);
  if (msg) i.setAttribute('aria-invalid', 'true'); else i.removeAttribute('aria-invalid');
  return !msg;
}
// Show server-side field errors ({field: message}) under the matching inputs when they exist.
export function applyServerErrors(map, err) {
  let any = false;
  for (const [apiField, inputId] of Object.entries(map)) {
    if (err.errors && err.errors[apiField]) { fieldErr(inputId, err.errors[apiField]); any = true; }
  }
  return any;
}
export function busy(btn, on, busyText) {
  if (typeof btn === 'string') btn = $(btn);
  if (on) { btn.dataset.label = btn.textContent; btn.textContent = busyText; } else if (btn.dataset.label) btn.textContent = btn.dataset.label;
  btn.disabled = on;
}
export function setStatus(sel, msg, kind) { const el = $(sel); if (el) { el.textContent = msg || ''; el.className = 'status ' + (kind || ''); } }

// ---- CSV export (runs in the browser) ----
// A cell that starts with = + - @ would be executed as a formula by Excel ("CSV injection"); prefix a quote.
export const csvCell = v => { let t = String(v == null ? '' : v); if (/^[=+\-@\t\r]/.test(t)) t = "'" + t; return '"' + t.replace(/"/g, '""') + '"'; };
export const toCsv = rows => rows.map(r => r.map(csvCell).join(',')).join('\r\n');
export function download(filename, text, mime = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob(['\ufeff' + text], { type: mime }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
