// Tiny publish/subscribe so controllers do not import each other (avoids circular imports).
const handlers = {};
export const bus = {
  on(evt, fn) { (handlers[evt] ||= []).push(fn); },
  emit(evt, data) { (handlers[evt] || []).forEach(fn => fn(data)); }
};
