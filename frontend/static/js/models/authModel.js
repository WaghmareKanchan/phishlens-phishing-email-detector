import { api, session } from './apiClient.js';

const keepToken = r => { if (r && r.access_token) session.set(r.access_token); return r; };

export const authModel = {
  register: (name, email, password) => api('POST', '/auth/register', { json: { name, email, password }, auth: false }).then(keepToken),
  login: (email, password) => api('POST', '/auth/login', { json: { email, password }, auth: false }).then(keepToken),
  verify2fa: (temp_token, code) => api('POST', '/auth/2fa/verify', { json: { temp_token, code }, auth: false }).then(keepToken),
  me: () => api('GET', '/auth/me'),
  logout: () => session.clear(),
  hasSession: () => !!session.token,

  forgot: email => api('POST', '/auth/forgot-password', { json: { email }, auth: false }),
  reset: (email, code, new_password) => api('POST', '/auth/reset-password', { json: { email, code, new_password }, auth: false }),
  changePassword: (current_password, new_password) =>
    api('POST', '/auth/change-password', { json: { current_password, new_password } }).then(keepToken),

  setup2fa: () => api('POST', '/auth/2fa/setup'),
  confirm2fa: code => api('POST', '/auth/2fa/confirm', { json: { code } })
};
