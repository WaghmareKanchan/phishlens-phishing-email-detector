import { $, $$ } from '../utils/dom.js';

export const TABS = ['analyze', 'saved', 'models', 'history', 'batch', 'settings', 'admin'];

export const shellView = {
  showApp(user) {
    $('#uName').textContent = user.name; $('#uEmail').textContent = user.email;
    $('#avatar').textContent = (user.name.trim()[0] || '?').toUpperCase();
    $('#adminTabBtn').hidden = !user.is_admin;
    $('#authWrap').hidden = true; $('#app').hidden = false;
  },
  showAuth() { $('#app').hidden = true; $('#authWrap').hidden = false; $('#adminTabBtn').hidden = true; },
  showTab(tab) {
    $$('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.tab === tab));
    TABS.forEach(v => { $('#view-' + v).hidden = v !== tab; });
  },
  setSavedCount(n) { $('#savedCount').textContent = n; },
  toggleTheme() {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    $('#themeBtn').textContent = dark ? 'Dark mode' : 'Light mode';
  },
  initTheme() { if (matchMedia('(prefers-color-scheme: dark)').matches) $('#themeBtn').textContent = 'Light mode'; }
};
