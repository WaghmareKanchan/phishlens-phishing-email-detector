import { $, $$, EMAIL_RX, pwOk, pwScore, fieldErr, busy, applyServerErrors } from '../utils/dom.js';
import { authModel } from '../models/authModel.js';
import { state } from '../models/state.js';
import { authView } from '../views/authView.js';

const FIELD_MAP_REGISTER = { name: 'rgName', email: 'rgEmail', password: 'rgPw' };
let hooks = { onLogin() {}, onLogout() {} };
let tsAttempts = 0;

// Show the "turn on two-factor authentication" screen for a logged-in user. The user may press
// "Skip for now", but is asked again at every login until the setup is finished.
async function startTotpSetup(user) {
  state.pending.user = user;
  try {
    authView.renderQr('#tsQr', await authModel.setup2fa());
    tsAttempts = 0; $('#tsCode').value = ''; authView.setMode('totpsetup');
  } catch (e) { state.pending.user = null; hooks.onLogin(user); }   // could not start setup: do not lock them out
}

async function doLogin(ev) {
  ev.preventDefault(); authView.banner('#loginErr');
  const email = $('#liEmail').value.trim().toLowerCase(), pw = $('#liPw').value;
  const ok = [fieldErr('liEmail', EMAIL_RX.test(email) ? '' : 'Enter a valid email address.'), fieldErr('liPw', pw ? '' : 'Enter your password.')];
  if (ok.includes(false)) return;
  busy('#loginBtn', true, 'Logging in…');
  try {
    const r = await authModel.login(email, pw);
    $('#liPw').value = '';
    if (r.two_factor_required) {
      state.pending.tempToken = r.temp_token;
      $('#tvSub').textContent = 'Open your authenticator app and enter the current code for ' + email + '.';
      $('#tvCode').value = '';
      authView.setMode('totpverify');
    } else if (r.two_factor_setup_required) await startTotpSetup(r.user);
    else hooks.onLogin(r.user);
  } catch (e) { authView.banner('#loginErr', e.message); }
  finally { busy('#loginBtn', false); }
}

async function doRegister(ev) {
  ev.preventDefault(); authView.banner('#regErr');
  const name = $('#rgName').value.trim(), email = $('#rgEmail').value.trim().toLowerCase(), pw = $('#rgPw').value, pw2 = $('#rgPw2').value;
  const ok = [
    fieldErr('rgName', name.length >= 2 ? '' : 'Enter your full name.'),
    fieldErr('rgEmail', EMAIL_RX.test(email) ? '' : 'Enter a valid email address.'),
    fieldErr('rgPw', pwOk(pw) ? '' : 'Use at least 6 characters, including a letter and a number.'),
    fieldErr('rgPw2', pw2 === pw ? '' : 'The passwords do not match.')];
  if (ok.includes(false)) return;
  busy('#registerBtn', true, 'Creating account…');
  try {
    const r = await authModel.register(name, email, pw);
    authView.clearFields(['#rgName', '#rgEmail', '#rgPw', '#rgPw2']); $('#strength').dataset.level = 0;
    await startTotpSetup(r.user);
  } catch (e) {
    if (e.code === 'email_taken') fieldErr('rgEmail', 'An account with this email already exists. Log in instead.');
    else if (!applyServerErrors(FIELD_MAP_REGISTER, e)) authView.banner('#regErr', e.message);
  } finally { busy('#registerBtn', false); }
}

async function doTotpSetupConfirm(ev) {
  ev.preventDefault(); authView.banner('#tsErr');
  const code = $('#tsCode').value.trim();
  if (!fieldErr('tsCode', /^\d{6}$/.test(code) ? '' : 'Enter the 6-digit code.')) return;
  busy('#tsConfirmBtn', true, 'Checking…');
  try {
    await authModel.confirm2fa(code);
    tsAttempts = 0; $('#tsCode').value = '';
    finishSetup();
  } catch (e) {
    tsAttempts++;
    fieldErr('tsCode', e.code === 'rate_limited' ? e.message : tsAttempts >= 5
      ? 'Still not matching. Check that your phone\u2019s clock is correct, or select Skip for now.' : 'That code is not correct. Check the app and try again.');
  } finally { busy('#tsConfirmBtn', false); }
}

function finishSetup() {
  const user = state.pending.user; state.pending.user = null;
  $('#tsCode').value = '';
  if (user) hooks.onLogin(user); else authView.setMode('login');
}

async function doTotpVerify(ev) {
  ev.preventDefault(); authView.banner('#tvErr');
  const code = $('#tvCode').value.trim();
  if (!state.pending.tempToken) { authView.setMode('login'); authView.banner('#loginErr', 'Your session expired. Log in again.'); return; }
  if (!fieldErr('tvCode', /^\d{6}$/.test(code) ? '' : 'Enter the 6-digit code.')) return;
  busy('#tvConfirmBtn', true, 'Verifying…');
  try {
    const r = await authModel.verify2fa(state.pending.tempToken, code);
    state.pending.tempToken = null; $('#tvCode').value = '';
    hooks.onLogin(r.user);
  } catch (e) {
    if (e.code === 'login_expired') { state.pending.tempToken = null; authView.setMode('login'); authView.banner('#loginErr', e.message); }
    else fieldErr('tvCode', e.code === 'rate_limited' ? e.message : 'That code is not correct, expired, or already used.');
  } finally { busy('#tvConfirmBtn', false); }
}

async function requestCode(email) {
  const r = await authModel.forgot(email);
  state.pending.resetEmail = email; state.pending.resendAt = Date.now() + 30000;
  $('#rsSub').textContent = r.message;
  authView.showDevMail(email, r.dev_code);
}
async function doForgot(ev) {
  ev.preventDefault(); authView.banner('#fgErr');
  const email = $('#fgEmail').value.trim().toLowerCase();
  if (!fieldErr('fgEmail', EMAIL_RX.test(email) ? '' : 'Enter a valid email address.')) return;
  busy('#forgotBtn', true, 'Sending…');
  try {
    await requestCode(email);
    authView.clearFields(['#rsCode', '#rsPw', '#rsPw2']); $('#rsStrength').dataset.level = 0;
    authView.setMode('reset');
  } catch (e) { authView.banner('#fgErr', e.message); }
  finally { busy('#forgotBtn', false); }
}
async function resend() {
  const wait = state.pending.resendAt - Date.now();
  if (wait > 0) { authView.banner('#rsErr', 'Wait ' + Math.ceil(wait / 1000) + ' seconds before asking for another code.'); return; }
  authView.banner('#rsErr');
  try { await requestCode(state.pending.resetEmail); $('#rsCode').value = ''; $('#rsCode').focus(); }
  catch (e) { authView.banner('#rsErr', e.message); }
}
async function doReset(ev) {
  ev.preventDefault(); authView.banner('#rsErr');
  const code = $('#rsCode').value.trim(), pw = $('#rsPw').value, pw2 = $('#rsPw2').value;
  const ok = [fieldErr('rsCode', /^\d{6}$/.test(code) ? '' : 'Enter the 6-digit code.'),
    fieldErr('rsPw', pwOk(pw) ? '' : 'Use at least 6 characters, including a letter and a number.'),
    fieldErr('rsPw2', pw2 === pw ? '' : 'The passwords do not match.')];
  if (ok.includes(false)) return;
  busy('#resetBtn', true, 'Saving…');
  try {
    await authModel.reset(state.pending.resetEmail, code, pw);
    const email = state.pending.resetEmail; state.pending.resetEmail = '';
    authView.clearFields(['#rsCode', '#rsPw', '#rsPw2']);
    authView.setMode('login'); $('#liEmail').value = email; $('#liPw').focus();
    authView.banner('#loginOk', 'Your password was updated. Log in with your new password.');
  } catch (e) { if (e.code === 'bad_reset_code') fieldErr('rsCode', e.message); else authView.banner('#rsErr', e.message); }
  finally { busy('#resetBtn', false); }
}

function bindStrength(input, bar, help) {
  $(input).addEventListener('input', () => authView.setStrength(bar, help, input, pwScore($(input).value)));
}

export const authController = {
  init(h) {
    hooks = h;
    $$('[data-auth]').forEach(b => b.addEventListener('click', () => authView.setMode(b.dataset.auth)));
    $$('.pwtoggle').forEach(b => b.addEventListener('click', () => {
      const i = $('#' + b.dataset.target), showing = i.type === 'text';
      i.type = showing ? 'password' : 'text'; b.textContent = showing ? 'Show' : 'Hide';
      b.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    }));
    bindStrength('#rgPw', '#strength', '#pwHelp'); bindStrength('#rsPw', '#rsStrength', '#rsHelp');
    $('#loginForm').addEventListener('submit', doLogin);
    $('#registerForm').addEventListener('submit', doRegister);
    $('#forgotForm').addEventListener('submit', doForgot);
    $('#resetForm').addEventListener('submit', doReset);
    $('#resendBtn').addEventListener('click', resend);
    $('#totpSetupForm').addEventListener('submit', doTotpSetupConfirm);
    $('#tsSkipBtn').addEventListener('click', finishSetup);
    $('#totpVerifyForm').addEventListener('submit', doTotpVerify);
    $('#tvCancelBtn').addEventListener('click', () => { state.pending.tempToken = null; $('#tvCode').value = ''; authView.setMode('login'); });
    $('#logoutBtn').addEventListener('click', () => { authModel.logout(); hooks.onLogout(); });
  },
  resetForms() {
    authView.clearFields(['#liPw', '#rgPw', '#rgPw2', '#rsCode', '#rsPw', '#rsPw2', '#tsCode', '#tvCode']);
    state.pending = { tempToken: null, user: null, resetEmail: '', resendAt: 0 };
    authView.setMode('login');
  },
  notice(msg) { authView.banner('#loginErr', msg); }
};
