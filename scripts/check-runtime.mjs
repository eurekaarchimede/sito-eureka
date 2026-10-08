#!/usr/bin/env node
// Small, offline regression checks for the actual inline runtime in eureka.html.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../eureka.html', import.meta.url), 'utf8');
const section = (start, end) => {
  const from = html.indexOf(start), to = html.indexOf(end, from);
  assert.ok(from >= 0 && to > from, `Runtime markers missing: ${start}`);
  return html.slice(from, to);
};
const common = section('// ===== FUNZIONI COMUNI =====', '// ===== HERO PARALLAX');
const swirl = section('// ===== VORTICI DELL\'HERO:', '// ===== EASTER EGG');
const bulb = section('// ===== LAMPADINA: pendolo', '// ===== year =====');

function harness({ reduced = false, renderCost = 0, background = false } = {}) {
  let now = 0, sequence = 0;
  let clockReads = 0;
  const rootClasses = new Set();
  const frames = new Map(), timers = new Map(), observers = [];
  const listeners = new Map(), motionListeners = new Map(), docListeners = new Map(), windowListeners = new Map();
  const addListener = (registry, name, callback) => {
    const previous = registry.get(name);
    registry.set(name, event => { previous?.(event); callback(event); });
  };
  const classes = new Set(['on']);
  const rig = {
    style: { removeProperty(name) { delete this[name]; } },
    classList: { contains: name => classes.has(name), toggle(name, value) { value ? classes.add(name) : classes.delete(name); } },
    setAttribute() {}, closest: () => ({ classList: { toggle() {} } }),
    addEventListener: (name, callback) => listeners.set(name, callback),
    setPointerCapture() {}
  };
  const draws = [];
  let strokes = 0;
  const canvasContext = {
    clearRect() {}, setTransform() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() { strokes++; }, fillRect() {},
    createLinearGradient: () => ({ addColorStop() {} }), createRadialGradient: () => ({ addColorStop() {} }),
    drawImage(_image, ...bounds) {
      assert.ok(bounds.every(Number.isFinite), 'Star projection must stay finite');
      draws.push(bounds);
    }
  };
  const canvas = { width: 0, height: 0, getContext: () => canvasContext };
  const document = {
    hidden: background, documentElement: { classList: { add: name => rootClasses.add(name) } }, getElementById: () => rig, querySelector: () => canvas, querySelectorAll: () => [],
    createElement: () => ({ width: 0, height: 0, getContext: () => canvasContext }),
    addEventListener: (name, callback) => addListener(docListeners, name, callback)
  };
  const motion = { matches: reduced, addEventListener: (name, callback) => addListener(motionListeners, name, callback) };
  class IntersectionObserver {
    constructor(callback) { this.callback = callback; this.targets = new Set(); observers.push(this); }
    observe(target) { this.targets.add(target); }
    unobserve(target) { this.targets.delete(target); }
    disconnect() { this.targets.clear(); }
    emit(visible) {
      if (this.targets.size) this.callback([...this.targets].map(target => ({ target, isIntersecting: visible })));
    }
  }
  const context = vm.createContext({
    document, window: {
      matchMedia: () => motion, IntersectionObserver, innerWidth: 390, innerHeight: 844, devicePixelRatio: 3, scrollY: 0,
      addEventListener: (name, callback) => windowListeners.set(name, callback)
    }, IntersectionObserver,
    getComputedStyle: () => ({ getPropertyValue: () => '#f5cd47' }), Math,
    AbortController, performance: { now: () => now + (clockReads++ % 2) * renderCost },
    requestAnimationFrame: callback => { const id = ++sequence; frames.set(id, callback); return id; },
    cancelAnimationFrame: id => frames.delete(id),
    setTimeout: (callback, delay) => { const id = ++sequence; timers.set(id, { callback, at: now + delay }); return id; },
    clearTimeout: id => timers.delete(id), fetch: () => Promise.reject(new Error('fetch mock not configured'))
  });
  vm.runInContext(common + '\nglobalThis.runtime = { fetchJSON, onApproach };', context);
  if (background) {
    docListeners.get('visibilitychange')();
    document.hidden = false; // leave the bulb visible while keeping the ambient star loop paused
  }
  const advance = ms => {
    now += ms;
    for (const [id, timer] of [...timers]) if (timer.at <= now) { timers.delete(id); timer.callback(); }
  };
  const flushFrames = (limit = 600, allowPersistent = false) => {
    let count = 0;
    while (frames.size && count++ < limit) {
      advance(1000 / 60);
      const batch = [...frames.values()]; frames.clear();
      batch.forEach(callback => callback(now));
    }
    if (!allowPersistent) assert.equal(frames.size, 0, 'Animation failed to settle within 10 seconds');
    return count;
  };
  const fire = (name, options = {}) => listeners.get(name)?.({
    isPrimary: true, button: 0, pointerId: 1, clientX: 45, clientY: 200, detail: 1, ...options
  });
  return { context, rig, classes, rootClasses, motion, motionListeners, document, docListeners, windowListeners, canvas, draws, strokes: () => strokes, observers, frames, timers, advance, flushFrames, fire };
}

{
  const h = harness();
  assert.equal(h.frames.size, 1, 'Visible hero starts its star animation');
  h.document.hidden = true;
  h.docListeners.get('visibilitychange')();
  assert.equal(h.frames.size, 0, 'Background tab must stop the star animation');
}

{
  const h = harness();
  assert.equal(h.canvas.width, 390, 'Star canvas must use one pixel per CSS pixel');
  assert.equal(h.canvas.height, 844);
  assert.equal(h.frames.size, 1, 'The starfield must animate while the page is visible');
  h.context.window.scrollY = 90;
  h.windowListeners.get('scroll')();
  h.flushFrames(90, true);
  assert.ok(h.strokes() > 0, 'The perspective field must paint star trails');
  assert.equal(h.frames.size, 1, 'The ambient starfield remains active across sections');
  h.document.hidden = true;
  h.docListeners.get('visibilitychange')();
  assert.equal(h.frames.size, 0, 'Backgrounding must immediately stop the starfield');
  h.document.hidden = false;
  h.docListeners.get('visibilitychange')();
  assert.equal(h.frames.size, 1, 'Returning to the page restarts the live starfield');
  h.motion.matches = true;
  h.motionListeners.get('change')();
  assert.equal(h.frames.size, 0, 'Reduced motion must stop an active warp');
  h.context.window.scrollY = 360;
  h.windowListeners.get('scroll')();
  assert.equal(h.frames.size, 0, 'Reduced motion must ignore new scroll');
  console.log('Stars: full-page warp, one-pixel canvas, background pause and reduced motion passed.');
}

{
  const h = harness();
  let calls = 0;
  h.context.runtime.onApproach({}, () => { calls++; });
  const observer = h.observers.at(-1);
  observer.emit(false); assert.equal(calls, 0);
  observer.emit(true); observer.emit(true); assert.equal(calls, 1, 'Approach callback must load only once');
  assert.equal(observer.targets.size, 0);
  delete h.context.window.IntersectionObserver;
  h.context.runtime.onApproach({}, () => { calls++; });
  assert.equal(calls, 2, 'Missing observer must load immediately');
}

{
  const h = harness();
  h.context.fetch = async () => ({ ok: true, json: async () => ({ loaded: true }) });
  assert.equal((await h.context.runtime.fetchJSON('/ok')).loaded, true);
  assert.equal(h.timers.size, 0, 'Success must release timeout');
  h.context.fetch = async () => ({ ok: false, status: 503 });
  await assert.rejects(h.context.runtime.fetchJSON('/http-error'), /HTTP 503/);
  assert.equal(h.timers.size, 0, 'HTTP failure must release timeout');
  h.context.fetch = async () => { throw new Error('Network failed'); };
  await assert.rejects(h.context.runtime.fetchJSON('/network-error'), /Network failed/);
  assert.equal(h.timers.size, 0, 'Network failure must release timeout');
  h.context.fetch = async () => ({ ok: true, json: async () => { throw new SyntaxError('Bad JSON'); } });
  await assert.rejects(h.context.runtime.fetchJSON('/invalid-json'), /Bad JSON/);
  assert.equal(h.timers.size, 0, 'JSON failure must release timeout');
  let signal;
  h.context.fetch = (_url, options) => new Promise((_resolve, reject) => {
    signal = options.signal;
    signal.addEventListener('abort', () => reject(new Error('Request aborted')), { once: true });
  });
  const pending = h.context.runtime.fetchJSON('/slow');
  const rejected = assert.rejects(pending, /Request aborted/);
  h.advance(7999); assert.equal(signal.aborted, false);
  h.advance(1); await rejected;
  assert.equal(signal.aborted, true);
  assert.equal(h.timers.size, 0, 'Abort must release timeout');
}

{
  const h = harness({ background: true });
  vm.runInContext(bulb, h.context);
  const observer = h.observers.at(-1);
  observer.emit(true);
  const entranceFrames = h.flushFrames();
  h.fire('pointerdown'); h.advance(16); h.fire('pointermove', { clientX: 65 });
  const draggedAngle = Number(h.rig.style.transform.match(/rotate\((-?[\d.]+)rad\)/)?.[1]);
  assert.ok(draggedAngle < 0 && draggedAngle >= -0.23, 'Dragging right must move bulb right within its angle limit');
  const primaryTransform = h.rig.style.transform;
  h.fire('pointerdown', { isPrimary: false, pointerId: 2 });
  h.fire('pointermove', { isPrimary: false, pointerId: 2, clientX: 100 });
  h.fire('pointercancel', { isPrimary: false, pointerId: 2 });
  assert.equal(h.rig.style.transform, primaryTransform, 'Second finger must not change the first gesture');
  h.fire('pointercancel'); h.fire('click');
  assert.equal(h.classes.has('on'), true, 'Cancelled drag must not toggle');
  const releaseFrames = h.flushFrames();
  h.advance(400);
  h.fire('click'); assert.equal(h.classes.has('on'), false, 'Tap must toggle');
  h.fire('click', { detail: 0 }); assert.equal(h.classes.has('on'), true, 'Keyboard activation must toggle');
  h.fire('pointerdown'); h.advance(16); h.fire('pointermove', { clientY: 220 });
  h.flushFrames();
  assert.equal(h.rig.style.transform, undefined, 'Vertical scroll must not rotate the bulb');
  h.fire('pointerdown'); h.advance(16); h.fire('pointermove', { clientX: 65 }); h.fire('pointerup', { clientX: 65 });
  observer.emit(false);
  assert.equal(h.frames.size, 0, 'Offscreen bulb must cancel rendering');
  observer.emit(true);
  h.fire('pointerdown'); h.advance(16); h.fire('pointermove', { clientX: 65 }); h.fire('pointerup', { clientX: 65 });
  h.document.hidden = true; h.docListeners.get('visibilitychange')();
  assert.equal(h.frames.size, 0, 'Background tab must cancel rendering');
  h.document.hidden = false;
  h.fire('pointerdown'); h.advance(16); h.fire('pointermove', { clientX: 65 }); h.fire('pointerup', { clientX: 65 });
  h.motion.matches = true; h.motionListeners.get('change')();
  assert.equal(h.frames.size, 0, 'Preference change must cancel rendering');
  assert.equal(h.rig.style.transform, undefined);
  console.log(`Pendulum: direction, cancel, second finger, scroll, visibility and reduced motion passed (${entranceFrames}/${releaseFrames} frames to settle).`);
}

{
  const h = harness({ reduced: true, background: true });
  vm.runInContext(bulb, h.context);
  h.observers.at(-1).emit(true);
  h.fire('pointerdown'); h.fire('pointermove', { clientX: 65 }); h.fire('pointerup');
  assert.equal(h.frames.size, 0, 'Initial reduced-motion preference must disable physics');
  assert.equal(h.rig.style.transform, undefined);
  h.fire('click', { detail: 0 });
  assert.equal(h.classes.has('on'), false, 'Reduced motion must preserve the lamp toggle');
}

console.log('JSON: success, HTTP/network/parse failure, 8-second abort and timer cleanup passed. Approach callback: exactly one load passed.');

for (const option of [
  { memory: 2, cores: 8, saveData: false, reduced: false },
  { memory: 4, cores: 8, saveData: false, reduced: false },
  { memory: 8, cores: 8, saveData: true, reduced: false },
  { memory: 8, cores: 8, saveData: false, reduced: true }
]) {
  let contextRequests = 0;
  const canvas = { dataset: {}, closest: () => ({}), getContext: () => { contextRequests++; } };
  const context = vm.createContext({
    document: { getElementById: () => canvas },
    navigator: { deviceMemory: option.memory, hardwareConcurrency: option.cores, connection: { saveData: option.saveData } },
    matchMedia: () => ({ matches: true }),
    reducedMotion: { matches: option.reduced }
  });
  vm.runInContext(swirl, context);
  assert.equal(canvas.dataset.mode, 'static-low-power');
  assert.equal(contextRequests, 0, 'Low-power mode must not create a WebGL context');
}
console.log('Swirl: 2/4 GB phones, data saver and reduced motion stay on the static image without WebGL.');
