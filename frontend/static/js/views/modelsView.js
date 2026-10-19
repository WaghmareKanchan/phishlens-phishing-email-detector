import { $, esc, fmtDate } from '../utils/dom.js';

export const modelsView = {
  render(info) {
    const n = $('#modelsNotice');
    n.hidden = !info.notice; n.textContent = info.notice || '';
    const trained = info.models.filter(m => m.trained);
    const withMetrics = trained.filter(m => m.n_test > 0);
    const best = Math.max(0, ...withMetrics.map(m => m.f1));
    $('#modelsSub').textContent = withMetrics.length
      ? 'Measured on a held-out test set of ' + withMetrics[0].n_test.toLocaleString() + ' emails (dataset: ' + withMetrics[0].dataset +
        (withMetrics[0].trained_at ? ', trained ' + fmtDate(withMetrics[0].trained_at) : '') + ').'
      : 'No measurements yet. Metrics appear here after you train the models.';
    $('#metricsTable tbody').innerHTML = info.models.map(m => {
      if (!m.trained) return '<tr><td>' + esc(m.name) + '</td><td>' + esc(m.type) + '</td><td colspan="5" class="num" style="text-align:left;color:var(--muted)">Not trained yet</td></tr>';
      if (!m.n_test) return '<tr><td>' + esc(m.name) + '</td><td>' + esc(m.type) + '</td><td colspan="5" style="color:var(--muted)">Loaded, but no metrics were recorded</td></tr>';
      return '<tr class="' + (m.f1 === best ? 'best' : '') + '"><td>' + esc(m.name) + '</td><td>' + esc(m.type) + '</td><td class="num">' + m.accuracy.toFixed(1) + '%</td><td class="num">' +
        m.precision.toFixed(1) + '%</td><td class="num">' + m.recall.toFixed(1) + '%</td><td class="num">' + m.f1.toFixed(1) + '%</td><td class="num">' + m.latency_ms.toFixed(0) + ' ms</td></tr>';
    }).join('');
    const sel = $('#cmSelect'), prev = sel.value;
    sel.innerHTML = withMetrics.map(m => '<option value="' + esc(m.name) + '"' + (m.name === prev ? ' selected' : '') + '>' + esc(m.name) + '</option>').join('');
    if (!withMetrics.length) sel.innerHTML = '<option value="">No trained models</option>';
    this.drawCM(info);
  },
  drawCM(info) {
    const m = info.models.find(x => x.name === $('#cmSelect').value && x.trained && x.n_test);
    $('#cm').innerHTML = !m ? '' :
      '<div class="h"></div><div class="h">Predicted legitimate</div><div class="h">Predicted phishing</div>' +
      '<div class="h">Actually legitimate</div><div class="good">' + m.tn + '<small>Correct</small></div><div class="bad">' + m.fp + '<small>False alarm</small></div>' +
      '<div class="h">Actually phishing</div><div class="bad">' + m.fn + '<small>Missed</small></div><div class="good">' + m.tp + '<small>Caught</small></div>';
  }
};
