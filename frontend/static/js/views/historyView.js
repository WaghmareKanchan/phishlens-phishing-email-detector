import { $, esc, bandLabel, fmtDate } from '../utils/dom.js';

export const statCards = items => items.map(([n, label]) => '<div class="stat"><b>' + n + '</b><span>' + label + '</span></div>').join('');

export const historyView = {
  render(history) {
    const has = history.length > 0;
    $('#histEmpty').hidden = has; $('#histWrap').hidden = !has; $('#histActions').hidden = !has;
    const c = { phish: 0, warn: 0, safe: 0 }; history.forEach(h => c[h.verdict]++);
    $('#stats').innerHTML = statCards([[history.length, 'Checked'], [c.phish, 'Phishing'], [c.warn, 'Suspicious'], [c.safe, 'Looks safe']]);
    $('#histBody').innerHTML = history.map(h => '<tr><td>' + esc(fmtDate(h.at)) + '</td><td>' + esc(h.from || 'Unknown sender') + '</td><td>' + esc(h.subject || '(no subject)') +
      '</td><td><span class="pill ' + h.verdict + '">' + bandLabel[h.verdict] + '</span></td><td class="num">' + h.risk + '%</td></tr>').join('');
  }
};
