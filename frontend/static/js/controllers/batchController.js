import { $, download, toCsv } from '../utils/dom.js';
import { analysisModel } from '../models/analysisModel.js';
import { emailModel } from '../models/emailModel.js';
import { state } from '../models/state.js';
import { batchView } from '../views/batchView.js';
import { bus } from '../utils/bus.js';

async function handleFile(file) {
  batchView.setStatus('Analyzing ' + file.name + '…');
  try {
    const r = await analysisModel.batch(file);
    state.batch = r; batchView.render(r.results);
    const n = r.results.length;
    batchView.setStatus('Scanned ' + n + ' email' + (n === 1 ? '' : 's') +
      (r.skipped_empty ? ', skipped ' + r.skipped_empty + ' without a body' : '') +
      (r.truncated ? ' (only the first 500 rows are scanned)' : '') +
      (r.engine === 'heuristic' ? '. Rule-based fallback, not machine learning.' : '.'), 'ok');
    bus.emit('history:stale');
  } catch (e) { batchView.setStatus(e.message, 'err'); }
}

async function saveAll() {
  if (!state.batch) return;
  batchView.setSaving(true);
  try {
    const r = await emailModel.bulkCreate(state.batch.results);
    batchView.setStatus('Saved ' + r.saved + ' emails to your saved emails list.', 'ok');
    bus.emit('saved:changed');
  } catch (e) { batchView.setStatus('Could not save the emails. ' + e.message, 'err'); }
  batchView.setSaving(false);
}

function exportCsv() {
  if (!state.batch) return;
  download('batch-results.csv', toCsv([['subject', 'from', 'body', 'label', 'verdict', 'risk_percent']].concat(
    state.batch.results.map(r => [r.subject, r.from, r.body, r.label || '', r.verdict, r.risk]))));
}

export const batchController = {
  init() {
    $('#batchFile').addEventListener('change', e => { const f = e.target.files && e.target.files[0]; if (f) handleFile(f); });
    $('#batchExportBtn').addEventListener('click', exportCsv);
    $('#batchSaveAllBtn').addEventListener('click', saveAll);
  },
  reset() { state.batch = null; batchView.reset(); }
};
