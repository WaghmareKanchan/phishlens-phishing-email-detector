import { $, showBanner } from '../utils/dom.js';

export const settingsView = {
  banner: showBanner,
  resetPanels() {
    ['#pwErr', '#pwOk', '#setupErr'].forEach(id => showBanner(id));
    $('#tfSetupPanel').hidden = true;
  },
  loading() { $('#tfStatusText').textContent = 'Checking\u2026'; $('#tfDot').className = 'dot'; },
  renderTfStatus(on) {
    $('#tfDot').className = 'dot ' + (on ? 'on' : 'off');
    $('#tfStatusText').textContent = on ? 'Two-factor authentication is on' : 'Two-factor authentication is off';
    $('#tfStatusSub').textContent = on ? 'A code from your authenticator app is required at every login.' : 'Off \u2014 only your password is needed to log in. You will be asked to turn it on each time you log in.';
    $('#tfEnableBtn').hidden = on;
  },
  unavailable(msg) { $('#tfStatusText').textContent = 'Not available'; $('#tfStatusSub').textContent = msg; },
  showSetup(on) { $('#tfSetupPanel').hidden = !on; }
};
