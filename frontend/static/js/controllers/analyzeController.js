import { $, $$, timeNow } from '../utils/dom.js';
import { analysisModel } from '../models/analysisModel.js';
import { emailModel } from '../models/emailModel.js';
import { state, keyOf } from '../models/state.js';
import { analyzeView } from '../views/analyzeView.js';
import { SAMPLES } from '../samples.js';
import { bus } from '../utils/bus.js';

function updateDraft() {
  const cur = state.currentId && state.saved.find(s => s.id === state.currentId);
  analyzeView.setDraftState(!!state.currentId, cur);
}

function newDraft() {
  analyzeView.setForm({}); state.currentId = null; state.lastAnalysis = null;
  analyzeView.clearResult(); analyzeView.setStatus(''); updateDraft(); $('#from').focus();
}

async function analyze() {
  const f = analyzeView.getForm();
  if (!f.body) { analyzeView.focusBody('Add the email text before analyzing'); return; }
  analyzeView.setAnalyzing(true); analyzeView.setStatus('');
  try {
    // email_id lets the server store the verdict on the saved copy, but only if the text is unchanged
    const r = await analysisModel.analyze(f, state.currentId);
    state.lastAnalysis = { key: keyOf(f), id: r.analysis_id, verdict: r.verdict };
    analyzeView.renderResult(f, r, state.modelsInfo && state.modelsInfo.notice);
    if (r.email_id) bus.emit('saved:changed');
    bus.emit('history:stale');
  } catch (e) { analyzeView.setStatus('Could not analyze the email. ' + e.message, 'err'); }
  finally { analyzeView.setAnalyzing(false); }
}

async function save(asNew) {
  const f = analyzeView.getForm();
  if (!f.body) { analyzeView.setStatus('Add the email body before saving.', 'err'); $('#body').focus(); return; }
  const analysisId = state.lastAnalysis && state.lastAnalysis.key === keyOf(f) ? state.lastAnalysis.id : null;
  analyzeView.setSaving(true);
  try {
    if (state.currentId && !asNew) {
      await emailModel.update(state.currentId, f, analysisId);
      analyzeView.setStatus('Updated at ' + timeNow() + '.', 'ok');
    } else {
      const e = await emailModel.create(f, analysisId);
      state.currentId = e.id;
      analyzeView.setStatus('Saved at ' + timeNow() + '. Find it under Saved emails.', 'ok');
    }
    bus.emit('saved:changed');
  } catch (e) { analyzeView.setStatus('Could not save the email. ' + e.message, 'err'); }
  analyzeView.setSaving(false); updateDraft();
}

export const analyzeController = {
  init() {
    $$('[data-sample]').forEach(b => b.addEventListener('click', () => {
      analyzeView.setForm(SAMPLES[b.dataset.sample]); state.currentId = null; state.lastAnalysis = null; analyzeView.setStatus(''); updateDraft();
    }));
    $('#analyzeBtn').addEventListener('click', analyze);
    $('#saveBtn').addEventListener('click', () => save(false));
    $('#saveNewBtn').addEventListener('click', () => save(true));
    $('#newBtn').addEventListener('click', newDraft);
    bus.on('saved:loaded', updateDraft);
    bus.on('email:new', newDraft);
    bus.on('email:open', s => {
      analyzeView.setForm(s); state.currentId = s.id; state.lastAnalysis = null;
      analyzeView.clearResult(); updateDraft();
      analyzeView.setStatus('Opened from Saved emails. Select Analyze email to score it, or edit and update it.');
    });
  },
  reset() { newDraft(); }
};
