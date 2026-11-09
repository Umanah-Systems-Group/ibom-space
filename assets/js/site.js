// Ibom Space page behaviour: the 3D stage, scroll-driven shots, reveals, video loops.
document.documentElement.classList.add('js');

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const phone = () => matchMedia('(max-width: 760px)').matches;

/* ------------------------------------------------------------------ menu */
const menu = document.getElementById('menu');
const links = document.getElementById('links');
menu?.addEventListener('click', () => {
  const open = links.classList.toggle('open');
  menu.setAttribute('aria-expanded', String(open));
  menu.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
});
links?.addEventListener('click', (e) => { if (e.target.closest('a')) { links.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); } });

const bar = document.getElementById('bar');
const onScroll = () => bar.classList.toggle('solid', scrollY > 40);
addEventListener('scroll', onScroll, { passive: true }); onScroll();

/* --------------------------------------------------------------- reveals */
// Children of a section rise in turn; content is visible without script.
const groups = new Map();
document.querySelectorAll('[data-reveal]').forEach((el) => {
  const key = el.closest('section, article') || document.body;
  const n = groups.get(key) || 0; groups.set(key, n + 1);
  el.style.setProperty('--d', `${Math.min(n, 6) * 80}ms`);
});
const revealIO = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); revealIO.unobserve(e.target); }
}, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
document.querySelectorAll('[data-reveal]').forEach((el) => revealIO.observe(el));

/* ---------------------------------------------------------- video loops */
const vidIO = new IntersectionObserver((entries) => {
  for (const e of entries) {
    const v = e.target;
    if (e.isIntersecting) { if (v.preload === 'none') { v.preload = 'auto'; v.load(); } if (!reduced) v.play().catch(() => {}); }
    else v.pause();
  }
}, { threshold: 0.15 });
document.querySelectorAll('video.loop').forEach((v) => vidIO.observe(v));

/* ----------------------------------------------------------------- stage */
function webglOK() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}

async function startStage() {
  const canvas = document.getElementById('stage');
  if (!canvas || !webglOK()) { document.documentElement.classList.add('no-webgl'); return; }
  let stage;
  try {
    const { createStage } = await import('./stage.js');
    stage = createStage(canvas, { maxDpr: phone() ? 1.5 : 1.75, blend: reduced ? 0.01 : 1.8 });
  } catch (err) {
    console.warn('Stage unavailable', err);
    document.documentElement.classList.add('no-webgl');
    return;
  }
  const size = () => stage.resize(innerWidth, innerHeight);
  size(); addEventListener('resize', size);

  const shiftOf = (el) => {
    const raw = phone() ? el.dataset.shiftM : el.dataset.shift;
    const [x = 0, y = 0] = String(raw || '0').split(',').map(Number);
    return [x, y];
  };

  // The shot follows whichever marked block holds the middle of the screen.
  const marks = [...document.querySelectorAll('[data-shot]')];
  const chips = [...document.querySelectorAll('.step-index a')];
  let current = null;
  function pick() {
    const mid = innerHeight * 0.5;
    let best = null;
    for (const el of marks) {
      const r = el.getBoundingClientRect();
      if (r.top <= mid && r.bottom >= mid) { best = el; break; }
    }
    if (!best || best === current) return;
    current = best;
    stage.setShot(best.dataset.shot);
    const [x, y] = shiftOf(best); stage.setShift(x, y);
    const id = best.id;
    chips.forEach((a) => a.classList.toggle('on', a.getAttribute('href') === `#${id}`));
  }
  addEventListener('scroll', pick, { passive: true });
  addEventListener('resize', () => { current = null; pick(); });
  const first = marks[0]; const [x0, y0] = shiftOf(first); stage.setShift(x0, y0, true);
  pick();

  // Render only while a stage section is on screen.
  const visible = new Set();
  const stageIO = new IntersectionObserver((entries) => {
    for (const e of entries) e.isIntersecting ? visible.add(e.target) : visible.delete(e.target);
    if (visible.size && !document.hidden) stage.start(); else stage.stop();
  }, { threshold: 0 });
  document.querySelectorAll('[data-stage]').forEach((s) => stageIO.observe(s));
  document.addEventListener('visibilitychange', () => { if (document.hidden) stage.stop(); else if (visible.size) stage.start(); });
}
startStage();
