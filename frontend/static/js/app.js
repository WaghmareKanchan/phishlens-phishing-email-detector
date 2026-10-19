// Entry point: wires models, views and controllers together and handles log-in / log-out.
import { $, $$ } from './utils/dom.js';
import { bus } from './utils/bus.js';
import { state } from './models/state.js';
import { authModel } from './models/authModel.js';
import { onSessionExpired } from './models/apiClient.js';
import { shellView } from './views/shellView.js';
import { authController } from './controllers/authController.js';
import { analyzeController } from './controllers/analyzeController.js';
import { savedController } from './controllers/savedController.js';
import { modelsController } from './controllers/modelsController.js';
import { historyController } from './controllers/historyController.js';
import { batchController } from './controllers/batchController.js';
import { settingsController } from './controllers/settingsController.js';
import { adminController } from './controllers/adminController.js';

const loaders = {
  saved: () => savedController.load(),
  models: () => modelsController.load(),
  history: () => historyController.loadIfStale(),
  settings: () => settingsController.load(),
  admin: () => (state.me && state.me.is_admin ? adminController.load() : null)
};

function show(tab) {
  shellView.showTab(tab);
  if (loaders[tab]) loaders[tab]();
}

async function enterApp(user) {
  state.me = user; state.currentId = null; state.lastAnalysis = null;
  shellView.showApp(user);
  show('analyze');
  modelsController.load();     // also tells the Analyze tab whether the models are demo/untrained
  savedController.load();
}

function leaveApp(message) {
  state.me = null; state.currentId = null; state.lastAnalysis = null; state.modelsInfo = null;
  analyzeController.reset(); savedController.reset(); historyController.reset(); batchController.reset(); settingsController.reset();
  shellView.showAuth(); authController.resetForms();
  if (message) authController.notice(message);
}

authController.init({ onLogin: enterApp, onLogout: () => leaveApp() });
[analyzeController, savedController, modelsController, historyController, batchController, settingsController, adminController].forEach(c => c.init());
$$('.tab').forEach(t => t.addEventListener('click', () => { $('#status').textContent = ''; show(t.dataset.tab); }));
$('#themeBtn').addEventListener('click', () => shellView.toggleTheme());
shellView.initTheme();
bus.on('tab:show', show);
bus.on('models:changed', () => modelsController.load());
onSessionExpired(() => leaveApp('Your session has expired. Log in again.'));

// Restore the session after a page reload
(async () => {
  if (!authModel.hasSession()) return;
  try { await enterApp(await authModel.me()); } catch (e) { authModel.logout(); }
})();
