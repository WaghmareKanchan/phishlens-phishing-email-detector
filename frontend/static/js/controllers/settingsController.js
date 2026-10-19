import { $, fieldErr, pwOk, busy, applyServerErrors } from '../utils/dom.js';
import { authModel } from '../models/authModel.js';
import { state } from '../models/state.js';
import { settingsView } from '../views/settingsView.js';
import { authView } from '../views/authView.js';


async function load() {
  settingsView.resetPanels(); settingsView.loading();
  try {
    const me = await authModel.me(); state.me = me;
    settingsView.renderTfStatus(me.two_factor_enabled);
  } catch (e) { settingsView.unavailable(e.message); }
}

async function changePassword() {
  settingsView.banner('#pwErr'); settingsView.banner('#pwOk');
  const cur = $('#curPw').value, pw = $('#newPw').value, pw2 = $('#newPw2').value;
  const ok = [fieldErr('curPw', cur ? '' : 'Enter your current password.'),
    fieldErr('newPw', pwOk(pw) ? '' : 'Use at least 6 characters, including a letter and a number.'),
    fieldErr('newPw2', pw2 === pw ? '' : 'The passwords do not match.')];
  if (ok.includes(false)) return;
  busy('#changePwBtn', true, 'Updating…');
  try {
    await authModel.changePassword(cur, pw);     // also swaps in the fresh token (all other devices are signed out)
    ['#curPw', '#newPw', '#newPw2'].forEach(x => { $(x).value = ''; });
    settingsView.banner('#pwOk', 'Your password has been updated. Other devices were signed out.');
  } catch (e) {
    if (e.code === 'wrong_password') fieldErr('curPw', e.message);
    else if (!applyServerErrors({ new_password: 'newPw' }, e)) settingsView.banner('#pwErr', e.message);
  } finally { busy('#changePwBtn', false); }
}

async function beginEnable() {
  settingsView.banner('#setupErr');
  try {
    authView.renderQr('#setQr', await authModel.setup2fa());
    settingsView.showSetup(true); $('#setCode').value = ''; $('#setCode').focus();
  } catch (e) { settingsView.banner('#setupErr', e.message); }
}
async function confirmEnable() {
  const code = $('#setCode').value.trim();
  if (!fieldErr('setCode', /^\d{6}$/.test(code) ? '' : 'Enter the 6-digit code.')) return;
  busy('#setConfirmBtn', true, 'Checking…');
  try {
    await authModel.confirm2fa(code);
    if (state.me) state.me.two_factor_enabled = true;
    settingsView.showSetup(false); settingsView.renderTfStatus(true);
  } catch (e) { fieldErr('setCode', e.message); }
  finally { busy('#setConfirmBtn', false); }
}

export const settingsController = {
  init() {
    $('#changePwBtn').addEventListener('click', changePassword);
    $('#tfEnableBtn').addEventListener('click', beginEnable);
    $('#setConfirmBtn').addEventListener('click', confirmEnable);
    $('#setCancelBtn').addEventListener('click', () => { settingsView.showSetup(false); settingsView.banner('#setupErr'); });
  },
  load,
  reset() {}
};
