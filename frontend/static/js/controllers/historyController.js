import { $ } from '../utils/dom.js';
import { analysisModel } from '../models/analysisModel.js';
import { historyView } from '../views/historyView.js';
import { bus } from '../utils/bus.js';

let stale = true;
async function load() {
  try { historyView.render(await analysisModel.history()); stale = false; }
  catch (e) { $('#histEmpty').hidden = false; $('#histEmpty').innerHTML = '<strong>Could not load history</strong>' + e.message; }
}
export const historyController = {
  init() {
    $('#histClear').addEventListener('click', async () => {
      try { await analysisModel.clearHistory(); await load(); } catch (e) { $('#histEmpty').hidden = false; $('#histEmpty').textContent = e.message; }
    });
    bus.on('history:stale', () => { stale = true; });
  },
  load, loadIfStale() { return stale ? load() : Promise.resolve(); },
  reset() { stale = true; historyView.render([]); }
};
