import { api } from './apiClient.js';

export const analysisModel = {
  analyze: (f, emailId) => api('POST', '/analyze', { json: { sender: f.from, subject: f.subject, body: f.body, label: f.label || '', email_id: emailId || null } }),
  batch(file) {
    const form = new FormData(); form.append('file', file);
    return api('POST', '/analyze/batch', { form }).then(r => ({
      ...r, results: r.results.map(x => ({ row: x.row, from: x.sender, subject: x.subject, body: x.body, label: x.label,
        verdict: x.verdict, risk: Math.round(x.ensemble_score * 100), analysisId: x.analysis_id }))
    }));
  },
  history: () => api('GET', '/history').then(r => r.map(h => ({ id: h.id, from: h.sender, subject: h.subject, verdict: h.verdict,
    risk: Math.round(h.ensemble_score * 100), at: h.analyzed_at }))),
  clearHistory: () => api('DELETE', '/history'),
  models: () => api('GET', '/models', { auth: false })
};

export const adminModel = {
  stats: () => api('GET', '/admin/stats'),
  users: () => api('GET', '/admin/users'),
  activity: () => api('GET', '/admin/activity'),
  reloadModels: () => api('POST', '/admin/models/reload')
};
