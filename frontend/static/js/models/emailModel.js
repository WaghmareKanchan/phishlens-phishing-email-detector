import { api } from './apiClient.js';

// API field names (sender, last_verdict ...) -> the names the views use.
const fromApi = e => ({
  id: e.id, from: e.sender, subject: e.subject, body: e.body, label: e.label,
  verdict: e.last_verdict, risk: e.last_score == null ? null : Math.round(e.last_score * 100),
  analyzedAt: e.last_analyzed_at, createdAt: e.created_at, updatedAt: e.updated_at
});
const toApi = (f, analysisId) => ({ sender: f.from, subject: f.subject, body: f.body, label: f.label || '', analysis_id: analysisId || null });

export const emailModel = {
  list: () => api('GET', '/emails').then(r => r.map(fromApi)),
  create: (f, analysisId) => api('POST', '/emails', { json: toApi(f, analysisId) }).then(fromApi),
  update: (id, f, analysisId) => api('PUT', '/emails/' + encodeURIComponent(id), { json: toApi(f, analysisId) }).then(fromApi),
  remove: id => api('DELETE', '/emails/' + encodeURIComponent(id)),
  bulkCreate: rows => api('POST', '/emails/bulk', { json: { emails: rows.map(r => toApi(r, r.analysisId)) } })
};
