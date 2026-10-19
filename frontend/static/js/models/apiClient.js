// The ONLY place that calls fetch(). Everything else uses the model modules built on top of it.
import { API_BASE } from '../config.js';

const KEY = 'phishlens_token';
let token = null;
try { token = sessionStorage.getItem(KEY); } catch (e) { /* storage blocked */ }

export const session = {
  get token() { return token; },
  set(t) { token = t || null; try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ } },
  clear() { this.set(null); }
};

export class ApiError extends Error {
  constructor(status, message, code, errors) { super(message); this.status = status; this.code = code || null; this.errors = errors || {}; }
}

let expiredHandler = () => {};
export const onSessionExpired = fn => { expiredHandler = fn; };

export async function api(method, path, { json, form, auth = true } = {}) {
  const headers = {};
  let body;
  if (auth && token) headers.Authorization = 'Bearer ' + token;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  if (form) body = form;                      // browser sets the multipart boundary itself
  let res;
  try { res = await fetch(API_BASE + path, { method, headers, body }); }
  catch (e) { throw new ApiError(0, 'Could not reach the server. Check your connection and try again.', 'network'); }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new ApiError(res.status, (data && typeof data.detail === 'string' && data.detail) || 'Something went wrong. Try again.',
      data && data.code, data && data.errors);
    // Only a dead SESSION logs the user out (wrong passwords/codes use other codes and statuses).
    if (auth && err.code === 'session_expired') { session.clear(); expiredHandler(); }
    throw err;
  }
  return data;
}
