import { $, $$, esc, bandLabel, pct, fmtDate, setStatus } from '../utils/dom.js';

const ICONS = {
  phish: '<svg class="icon" viewBox="0 0 44 44" aria-hidden="true"><path d="M22 4l18 32H4z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M22 16v10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="22" cy="31" r="2" fill="currentColor"/></svg>',
  warn: '<svg class="icon" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="17" fill="none" stroke="currentColor" stroke-width="3"/><path d="M22 12v12" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="22" cy="31" r="2" fill="currentColor"/></svg>',
  safe: '<svg class="icon" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="17" fill="none" stroke="currentColor" stroke-width="3"/><path d="M13 23l6 6 12-13" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
};
const VERDICT_TEXT = {
  phish: 'Do not click any links or reply. Report it and delete it.',
  warn: 'Some warning signs found. Check with the sender through another channel first.',
  safe: 'No strong warning signs. Stay careful with unexpected requests.'
};
const CAT_LABEL = { text: 'Language', links: 'Links', sender: 'Sender' };
const SEV_LABEL = { high: 'High', med: 'Medium', low: 'Low' };
const SEG_TIP = { url: 'Link to check', urg: 'Urgency wording', cred: 'Asks for sensitive details', rew: 'Reward wording' };
const SEV_ORDER = { high: 0, med: 1, low: 2 };

const annotate = segments => segments.map(s => s.kind
  ? '<mark class="' + esc(s.kind) + '" title="' + esc(SEG_TIP[s.kind] || '') + '">' + esc(s.text) + '</mark>' : esc(s.text)).join('');

export const analyzeView = {
  getForm: () => ({ from: $('#from').value.trim(), subject: $('#subject').value.trim(), body: $('#body').value.trim(), label: $('#label').value }),
  setForm(f) { $('#from').value = f.from || ''; $('#subject').value = f.subject || ''; $('#body').value = f.body || ''; $('#label').value = f.label || ''; },
  focusBody(msg) { $('#body').focus(); if (msg) $('#body').placeholder = msg; },
  setStatus: (msg, kind) => { setStatus('#status', msg, kind); setStatus('#savedStatus', msg, kind); },

  setDraftState(editing, saved) {
    $('#draftState').innerHTML = editing
      ? '<b>Editing a saved email</b>' + (saved ? ' · last saved ' + esc(fmtDate(saved.updatedAt)) : '')
      : 'New email, not saved yet';
    $('#saveBtn').textContent = editing ? 'Update saved email' : 'Save email';
    $('#saveNewBtn').hidden = !editing;
  },
  setSaving(on) { $('#saveBtn').disabled = $('#saveNewBtn').disabled = on; },
  setAnalyzing(on) { $('#analyzeBtn').disabled = on; $('#analyzeBtn').textContent = on ? 'Analyzing…' : 'Analyze email'; },

  clearResult() { $('#result').hidden = true; $('#emptyState').hidden = false; },

  renderResult(email, r, modelsNotice) {
    const b = r.verdict, p = pct(r.ensemble_score);
    const sigs = [...r.evidence].sort((a, c) => SEV_ORDER[a.severity] - SEV_ORDER[c.severity]);
    let note;
    if (r.engine === 'heuristic') {
      note = '<p class="note"><b>Rule-based result, not machine learning.</b> No trained model is loaded on the server, so this score comes from simple rules. Train the models (see the README) to get real predictions.</p>';
    } else {
      note = '<p class="note">Scored by ' + r.models_loaded + ' of ' + r.models_expected + ' trained models.' +
        (modelsNotice ? ' ' + esc(modelsNotice) : '') + '</p>';
    }
    $('#result').innerHTML =
      '<div class="verdict ' + b + '">' + ICONS[b] + '<div><h3>' + bandLabel[b] + ' · ' + p + '% risk</h3><p>' + VERDICT_TEXT[b] + '</p></div></div>' +
      '<div class="meter"><div class="track"><span class="z1"></span><span class="z2"></span><span class="z3"></span><span class="pin" style="left:0" id="pin"></span></div>' +
      '<div class="scale"><span>Safe</span><span>Suspicious</span><span>Phishing</span></div></div>' +
      '<h4>What the models saw in this email</h4>' +
      '<div class="mailview"><div class="hdr"><b>From:</b> ' + esc(email.from) + '<br><b>Subject:</b> ' + esc(email.subject) + '</div><div class="body">' + annotate(r.body_segments) + '</div></div>' +
      '<div class="legend"><span style="--c:var(--warn-mark)">Urgency</span><span style="--c:var(--danger-mark)">Sensitive request or link</span><span style="--c:var(--info-mark)">Reward wording</span></div>' +
      '<h4>Score from each model</h4><div class="models">' +
      r.predictions.map(x => { const v = pct(x.score);
        return '<div class="mrow"><div class="name">' + esc(x.model_name) + '<span class="tag">' + esc(x.model_type) + '</span></div><div class="bar" role="img" aria-label="' +
          esc(x.model_name) + ' risk ' + v + ' percent"><i class="' + x.verdict + '" data-w="' + v + '"></i></div><div class="pct">' + v + '% · ' + bandLabel[x.verdict] + '</div></div>'; }).join('') +
      '<div class="mrow" style="border-top:1px solid var(--line);padding-top:10px"><div class="name">Ensemble</div><div class="bar"><i class="' + b + '" data-w="' + p + '"></i></div><div class="pct">' + p + '% · ' + bandLabel[b] + '</div></div></div>' +
      '<h4>Evidence</h4><ul class="signals">' +
      sigs.map(s => '<li><span class="sev ' + esc(s.severity) + '">' + (SEV_LABEL[s.severity] || '') + '</span><div><b>' + (CAT_LABEL[s.category] || '') + ': ' + esc(s.title) + '</b><span>' + esc(s.detail) + '</span></div></li>').join('') + '</ul>' + note;
    $('#emptyState').hidden = true; $('#result').hidden = false;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      $$('.bar i').forEach(i => { i.style.width = i.dataset.w + '%'; });
      const pin = $('#pin'); if (pin) pin.style.left = p + '%';
    }));
  }
};
