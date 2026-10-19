import { $, esc, bandLabel, setStatus } from '../utils/dom.js';
import { statCards } from './historyView.js';

export const batchView = {
  setStatus: (m, k) => setStatus('#batchStatus', m, k),
  render(results) {
    $('#batchResultsPanel').hidden = results.length === 0;
    const c = { phish: 0, warn: 0, safe: 0 }; results.forEach(r => c[r.verdict]++);
    $('#batchStats').innerHTML = statCards([[results.length, 'Scanned'], [c.phish, 'Phishing'], [c.warn, 'Suspicious'], [c.safe, 'Looks safe']]);
    $('#batchBody').innerHTML = results.map(r => '<tr><td>' + r.row + '</td><td>' + esc(r.subject || '(no subject)') + '</td><td>' + esc(r.from || 'Unknown') +
      '</td><td class="batchrow-' + r.verdict + '">' + bandLabel[r.verdict] + '</td><td class="num">' + r.risk + '%</td></tr>').join('');
    $('#batchExportBtn').hidden = !results.length; $('#batchSaveAllBtn').hidden = !results.length;
  },
  reset() { $('#batchResultsPanel').hidden = true; $('#batchBody').innerHTML = ''; setStatus('#batchStatus', ''); $('#batchFile').value = ''; },
  setSaving(on) { $('#batchSaveAllBtn').disabled = on; $('#batchSaveAllBtn').textContent = on ? 'Saving…' : 'Save all to my saved emails'; }
};
