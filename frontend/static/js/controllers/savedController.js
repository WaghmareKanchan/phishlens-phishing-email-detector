import { $, download, toCsv } from '../utils/dom.js';
import { emailModel } from '../models/emailModel.js';
import { state } from '../models/state.js';
import { savedView } from '../views/savedView.js';
import { shellView } from '../views/shellView.js';
import { analyzeView } from '../views/analyzeView.js';
import { bus } from '../utils/bus.js';

let pendingDelete = null, deleteTimer = null;
const render = () => { shellView.setSavedCount(state.saved.length); savedView.render(state.saved, $('#filterLabel').value, pendingDelete); };

async function load() {
  try { state.saved = await emailModel.list(); }
  catch (e) { analyzeView.setStatus('Could not load saved emails. ' + e.message, 'err'); return; }
  if (state.currentId && !state.saved.some(s => s.id === state.currentId)) state.currentId = null;
  render(); bus.emit('saved:loaded');
}

async function onRowClick(e) {
  const btn = e.target.closest('button[data-act]'); if (!btn) return;
  const id = btn.dataset.id, s = state.saved.find(x => x.id === id); if (!s) return;
  if (btn.dataset.act === 'open') { bus.emit('email:open', s); bus.emit('tab:show', 'analyze'); return; }
  if (pendingDelete !== id) {          // first click arms the button, second click deletes
    pendingDelete = id; clearTimeout(deleteTimer);
    deleteTimer = setTimeout(() => { pendingDelete = null; render(); }, 4000);
    render(); return;
  }
  clearTimeout(deleteTimer); pendingDelete = null;
  try { await emailModel.remove(id); analyzeView.setStatus('Deleted.', 'ok'); await load(); }
  catch (err) { analyzeView.setStatus('Could not delete the email. ' + err.message, 'err'); render(); }
}

function exportCsv() {
  const rows = [['subject', 'from', 'body', 'label', 'verdict', 'risk_percent', 'saved_at']].concat(
    state.saved.map(s => [s.subject, s.from, s.body, s.label || '', s.verdict || '', s.risk ?? '', s.createdAt || '']));
  download('saved-emails.csv', toCsv(rows));
}

export const savedController = {
  init() {
    $('#savedBody').addEventListener('click', onRowClick);
    $('#filterLabel').addEventListener('change', render);
    $('#newFromSaved').addEventListener('click', () => { bus.emit('tab:show', 'analyze'); bus.emit('email:new'); });
    $('#exportBtn').addEventListener('click', exportCsv);
    bus.on('saved:changed', load);
  },
  load, render,
  reset() { state.saved = []; pendingDelete = null; render(); }
};
