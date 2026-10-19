import { $ } from '../utils/dom.js';
import { analysisModel } from '../models/analysisModel.js';
import { state } from '../models/state.js';
import { modelsView } from '../views/modelsView.js';

async function load() {
  try { state.modelsInfo = await analysisModel.models(); modelsView.render(state.modelsInfo); }
  catch (e) { $('#modelsSub').textContent = 'Could not load model information. ' + e.message; }
}
export const modelsController = {
  init() { $('#cmSelect').addEventListener('change', () => state.modelsInfo && modelsView.drawCM(state.modelsInfo)); },
  load
};
