import { $, esc, bandLabel, fmtDate, setStatus } from '../utils/dom.js';
import { statCards } from './historyView.js';

export const adminView = {
  setStatus: (m, k) => setStatus('#adminStatus', m, k),
  render(stats, users, activity) {
    $('#adminStats').innerHTML = statCards([[stats.total_users, 'Users'], [stats.total_emails, 'Saved emails'], [stats.total_analyses, 'Analyses'], [stats.users_with_2fa, 'With 2FA on']]);
    const v = stats.verdict_counts, total = (v.phish + v.warn + v.safe) || 1;
    const bar = (label, n, cls) => '<div class="mrow"><div class="name">' + label + '</div><div class="bar"><i class="' + cls + '" style="width:' + Math.round(n / total * 100) + '%"></i></div><div class="pct">' + n + '</div></div>';
    $('#adminVerdictBars').innerHTML = bar('Phishing', v.phish, 'phish') + bar('Suspicious', v.warn, 'warn') + bar('Looks safe', v.safe, 'safe');
    $('#adminUsersBody').innerHTML = users.map(u => '<tr><td>' + esc(u.name) + (u.is_admin ? ' <span class="badge-admin">ADMIN</span>' : '') + '</td><td>' + esc(u.email) +
      '</td><td>' + esc(fmtDate(u.created_at)) + '</td><td>' + (u.two_factor_enabled ? 'On' : 'Off') + '</td><td class="num">' + u.saved_email_count + '</td></tr>').join('');
    $('#adminActivityBody').innerHTML = activity.map(a => '<tr><td>' + esc(fmtDate(a.analyzed_at)) + '</td><td>' + esc(a.user) + '</td><td>' + esc(a.subject || '(no subject)') +
      '</td><td class="batchrow-' + a.verdict + '">' + bandLabel[a.verdict] + '</td><td class="num">' + Math.round(a.ensemble_score * 100) + '%</td></tr>').join('');
  }
};
