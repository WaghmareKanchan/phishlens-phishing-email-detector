import { $, esc, bandLabel, fmtDate } from '../utils/dom.js';

const LABEL_TEXT = { phishing: 'Phishing', legitimate: 'Legitimate' };

export const savedView = {
  render(saved, filter, pendingDelete) {
    const c = { phishing: 0, legitimate: 0, none: 0 };
    saved.forEach(s => { c[LABEL_TEXT[s.label] ? s.label : 'none']++; });
    $('#savedStats').innerHTML =
      '<div class="stat"><b>' + saved.length + '</b><span>Saved</span></div><div class="stat"><b>' + c.phishing + '</b><span>Labeled phishing</span></div>' +
      '<div class="stat"><b>' + c.legitimate + '</b><span>Labeled legitimate</span></div><div class="stat"><b>' + c.none + '</b><span>Not labeled</span></div>';
    const rows = saved.filter(s => filter === 'all' || (LABEL_TEXT[s.label] ? s.label : 'none') === filter);
    $('#savedEmpty').hidden = rows.length > 0; $('#savedWrap').hidden = rows.length === 0;
    $('#savedEmpty').innerHTML = saved.length
      ? '<strong>No emails match this filter</strong>Choose a different label above.'
      : '<strong>No saved emails yet</strong>Write a new email on the Analyze tab and select Save email.';
    $('#exportBtn').hidden = !saved.length;
    $('#savedBody').innerHTML = rows.map(s => {
      const body = String(s.body || ''), lb = LABEL_TEXT[s.label] ? s.label : '';
      const verdict = bandLabel[s.verdict] ? '<span class="pill ' + s.verdict + '">' + bandLabel[s.verdict] + ' · ' + (s.risk ?? 0) + '%</span>' : '<span class="lab">Not analyzed</span>';
      return '<tr><td>' + esc(fmtDate(s.updatedAt)) + '</td>' +
        '<td class="wrap"><b>' + esc(s.subject || '(no subject)') + '</b><span class="prev">' + esc(body.slice(0, 90)) + (body.length > 90 ? '…' : '') + '</span></td>' +
        '<td class="wrap">' + esc(s.from || 'Unknown sender') + '</td>' +
        '<td>' + (lb ? '<span class="lab ' + lb + '">' + LABEL_TEXT[lb] + '</span>' : '<span class="lab">Not labeled</span>') + '</td>' +
        '<td>' + verdict + '</td>' +
        '<td><div class="rowbtns"><button class="btn ghost small" type="button" data-act="open" data-id="' + esc(s.id) + '">Open</button>' +
        '<button class="btn small danger" type="button" data-act="del" data-id="' + esc(s.id) + '">' + (pendingDelete === s.id ? 'Confirm delete' : 'Delete') + '</button></div></td></tr>';
    }).join('');
  }
};
