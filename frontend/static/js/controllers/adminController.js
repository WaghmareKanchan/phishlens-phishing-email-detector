import { $ } from '../utils/dom.js';
import { adminModel } from '../models/analysisModel.js';
import { adminView } from '../views/adminView.js';
import { bus } from '../utils/bus.js';

async function load() {
  adminView.setStatus('');
  try {
    const [stats, users, activity] = await Promise.all([adminModel.stats(), adminModel.users(), adminModel.activity()]);
    adminView.render(stats, users, activity);
  } catch (e) { adminView.setStatus('Could not load the dashboard. ' + e.message, 'err'); }
}
async function reload() {
  adminView.setStatus('Reloading models…');
  try {
    const r = await adminModel.reloadModels();
    const errs = Object.entries(r.errors).map(([k, v]) => k + ': ' + v).join('; ');
    adminView.setStatus('Loaded models: ' + (r.loaded.join(', ') || 'none') + (errs ? '. Problems: ' + errs : '.'), errs ? 'err' : 'ok');
    bus.emit('models:changed');
  } catch (e) { adminView.setStatus(e.message, 'err'); }
}
export const adminController = {
  init() { $('#adminRefreshBtn').addEventListener('click', load); $('#adminReloadBtn').addEventListener('click', reload); },
  load
};
