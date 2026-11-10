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
links?.addEventListener('click', (e) => { if (e.target.closest('a')) { links.classList.remove('open'); menu?.setAttribute('aria-expanded', 'false'); } });

const bar = document.getElementById('bar');
const onScroll = () => bar && bar.classList.toggle('solid', scrollY > 40);
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

/* ------------------------------------------------------ tug mission film */
// One sticky film beside the steps; the clip changes with the step in view.
const films = [...document.querySelectorAll('.tug-film .tf')];
const credit = document.getElementById('tug-credit');
const marks = [...document.querySelectorAll('[data-film]')];
const chips = [...document.querySelectorAll('.step-index a')];
let front = 0, currentFilm = null, currentMark = null, tugVisible = false;
function showFilm(name) {
  if (!films.length || name === currentFilm) return;
  currentFilm = name;
  const next = films[1 - front];
  next.src = `assets/film/${name}.mp4`;
  next.poster = `assets/film/${name}.jpg`;
  const swap = () => {
    next.classList.add('on'); films[front].classList.remove('on');
    const old = films[front]; setTimeout(() => old.pause(), 1300);
    front = 1 - front;
  };
  if (tugVisible && !reduced) next.play().then(swap).catch(swap); else swap();
}
function pickStep() {
  const mid = innerHeight * 0.5;
  for (const el of marks) {
    const r = el.getBoundingClientRect();
    if (r.top <= mid && r.bottom >= mid) {
      if (el === currentMark) return;
      currentMark = el;
      showFilm(el.dataset.film);
      if (credit) credit.textContent = el.dataset.credit;
      chips.forEach((a) => a.classList.toggle('on', a.getAttribute('href') === `#${el.id}`));
      return;
    }
  }
}
if (films.length) {
  addEventListener('scroll', pickStep, { passive: true });
  new IntersectionObserver((es) => {
    tugVisible = es[0].isIntersecting;
    const v = films[front];
    if (tugVisible && !reduced) v.play().catch(() => {}); else v.pause();
  }).observe(document.getElementById('tug'));
  showFilm(marks[0].dataset.film);
  pickStep();
}

/* ------------------------------------------------- how the tug sees */
// The tracking box follows the launch ring in the concept render (track exported from the Blender scene).
// The readout numbers are a simulated approach, labelled as such on the page.
const navFilm = document.getElementById('nav-film');
const track = document.getElementById('track');
if (navFilm && track) {
  let boxes = null, fps = 10;
  fetch(navFilm.dataset.track || 'assets/film/landsat-track.json').then((r) => r.json()).then((d) => { boxes = d.boxes; fps = d.fps; }).catch(() => {});
  const range = document.getElementById('ro-range'), speed = document.getElementById('ro-speed'), spin = document.getElementById('ro-spin');
  let t0 = performance.now();
  const frame = () => {
    if (boxes && navFilm.readyState >= 2) {
      const f = Math.min(boxes.length - 1, navFilm.currentTime * fps);
      const i = Math.floor(f), k = f - i, a = boxes[i], b = boxes[Math.min(i + 1, boxes.length - 1)];
      const box = a.map((v, j) => v + (b[j] - v) * k);
      // video uses object-fit: cover; map normalised film coords into the frame
      const fw = navFilm.clientWidth, fh = navFilm.clientHeight, vw = navFilm.videoWidth || 1280, vh = navFilm.videoHeight || 720;
      const sc = Math.max(fw / vw, fh / vh), ox = (fw - vw * sc) * (getComputedStyle(navFilm).objectPosition.startsWith('30%') ? 0.3 : 0.5), oy = (fh - vh * sc) / 2;
      const pad = 10;
      track.style.transform = `translate(${ox + box[0] * vw * sc - pad}px, ${oy + box[1] * vh * sc - pad}px)`;
      track.style.width = `${(box[2] - box[0]) * vw * sc + pad * 2}px`;
      track.style.height = `${(box[3] - box[1]) * vh * sc + pad * 2}px`;
      track.classList.add('live');
      const s = ((performance.now() - t0) / 1000) % 40;
      range.textContent = `${(35 - s * 0.6).toFixed(1)} m`;
      speed.textContent = `${(2.4 - s * 0.02).toFixed(1)} cm/s`;
      spin.textContent = `${(0.21 + 0.02 * Math.sin(s * 0.9)).toFixed(2)} °/s`;
    }
    if (!navFilm.paused) requestAnimationFrame(frame);
  };
  navFilm.addEventListener('play', () => requestAnimationFrame(frame));
  new IntersectionObserver((es) => {
    if (es[0].isIntersecting) { if (navFilm.preload === 'none') { navFilm.preload = 'auto'; navFilm.load(); } if (!reduced) navFilm.play().catch(() => {}); else { navFilm.addEventListener('loadeddata', () => requestAnimationFrame(frame), { once: true }); } }
    else navFilm.pause();
  }, { threshold: 0.2 }).observe(navFilm);
}

/* ---------------------------------------------------------- mission clock */
const clock = document.getElementById('clock');
if (clock) {
  const tick = () => { const d = new Date(); clock.textContent = `UTC ${d.toISOString().slice(11, 19)}`; };
  tick(); setInterval(tick, 1000);
}

/* --------------------------------------------- hero: film inside the letters */
const heroFilm = document.getElementById('hero-film');
const heroType = document.getElementById('hero-type');
const heroH = document.getElementById('hero-h');
if (heroFilm && heroType && heroH && heroType.getContext) {
  const ctx = heroType.getContext('2d');
  let W = 0, H = 0, dpr = 1, running = false;
  const size = () => {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = heroType.clientWidth; H = heroType.clientHeight;
    heroType.width = Math.round(W * dpr); heroType.height = Math.round(H * dpr);
  };
  const draw = () => {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const cs = getComputedStyle(heroH);
    ctx.font = `${cs.fontWeight} ${cs.fontSize} Archivo, system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    if ('letterSpacing' in ctx) ctx.letterSpacing = cs.letterSpacing;
    ctx.fillStyle = '#fff';
    // place each word exactly where the (invisible) heading puts it
    const box = heroType.getBoundingClientRect();
    for (const span of heroH.querySelectorAll('span')) {
      const r = span.getBoundingClientRect();
      ctx.fillText(span.textContent, r.left - box.left + r.width / 2, r.top - box.top + r.height / 2 + parseFloat(cs.fontSize) * 0.03);
    }
    // the film shows through the letters, a little brighter than the background
    ctx.globalCompositeOperation = 'source-in';
    const vw = heroFilm.videoWidth || 1280, vh = heroFilm.videoHeight || 720;
    const sc = Math.max(W / vw, H / vh), dw = vw * sc, dh = vh * sc;
    if (heroFilm.readyState >= 2) ctx.drawImage(heroFilm, (W - dw) / 2, (H - dh) / 2, dw, dh);
    // silver sheen so the words always read
    ctx.globalCompositeOperation = 'source-atop';
    const g = ctx.createLinearGradient(0, H * 0.3, 0, H * 0.7);
    g.addColorStop(0, 'rgba(255,255,255,.62)'); g.addColorStop(.5, 'rgba(225,230,238,.38)'); g.addColorStop(1, 'rgba(255,255,255,.55)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';
  };
  const loop = () => { draw(); if (running) requestAnimationFrame(loop); };
  const start = () => { if (!running) { running = true; document.body.classList.add('type-live'); requestAnimationFrame(loop); } };
  size(); addEventListener('resize', () => { size(); draw(); });
  document.fonts?.ready.then(() => { size(); draw(); });
  heroFilm.addEventListener('loadeddata', () => { document.body.classList.add('type-live'); draw(); });
  heroFilm.addEventListener('playing', start);
  heroFilm.addEventListener('pause', () => { running = false; });
  if (reduced) { heroFilm.pause(); heroFilm.addEventListener('loadeddata', draw, { once: true }); }
  new IntersectionObserver((es) => {
    if (es[0].isIntersecting) { if (!reduced) heroFilm.play().catch(() => {}); } else { heroFilm.pause(); }
  }).observe(heroType);
}

/* ------------------------------------------- statement: words light up */
const big = document.querySelector('[data-words]');
if (big) {
  big.innerHTML = big.textContent.trim().split(/\s+/).map((w) => `<span class="w">${w}</span>`).join(' ');
  const words = [...big.querySelectorAll('.w')];
  const lightWords = () => {
    const r = big.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, (innerHeight * 0.85 - r.top) / (r.height + innerHeight * 0.35)));
    const n = reduced ? words.length : Math.round(p * words.length);
    words.forEach((w, i) => w.classList.toggle('on', i < n));
  };
  addEventListener('scroll', lightWords, { passive: true }); lightWords();
}

/* ------------------------------------------------------------ rail */
const rail = document.getElementById('rail');
document.querySelectorAll('[data-rail]').forEach((b) => b.addEventListener('click', () => {
  const card = rail.querySelector('.k-card');
  rail.scrollBy({ left: Number(b.dataset.rail) * (card.getBoundingClientRect().width + 14), behavior: reduced ? 'auto' : 'smooth' });
}));

/* ------------------------------------------- shared: progress through a tall section */
const progress = (el) => {
  const r = el.getBoundingClientRect();
  return Math.min(1, Math.max(0, -r.top / (r.height - innerHeight)));
};

/* --------------------------------------------- pinned sections that step */
const stepper = (el, n, onStep) => {
  let cur = -1;
  const run = () => {
    const i = Math.min(n - 1, Math.floor(progress(el) * n * 0.999));
    if (i !== cur) { cur = i; el.dataset.step = String(i); onStep(i); }
  };
  addEventListener('scroll', run, { passive: true }); addEventListener('resize', run); run();
};

/* jobs: one diagram per job */
const jobs = document.getElementById('jobs');
if (jobs) {
  const items = [...jobs.querySelectorAll('.k-jobs-list li')];
  stepper(jobs, items.length, (i) => items.forEach((li, k) => li.classList.toggle('on', k === i)));
}

/* cutaway: draw the tug, then light one system at a time */
const cut = document.getElementById('cutaway');
if (cut) {
  cut.querySelectorAll('.ln').forEach((e) => e.setAttribute('pathLength', '1'));
  const items = [...cut.querySelectorAll('.cut-list li')];
  const dots = document.createElement('div'); dots.className = 'cut-dots'; dots.setAttribute('aria-hidden', 'true');
  dots.innerHTML = items.map(() => '<i></i>').join(''); cut.querySelector('.cut-pin').append(dots);
  const ds = [...dots.children];
  new IntersectionObserver((es) => { if (es[0].isIntersecting) cut.classList.add('drawn'); }, { threshold: 0.05 }).observe(cut);
  if (reduced) cut.classList.add('drawn');
  stepper(cut, items.length, (i) => {
    items.forEach((li, k) => li.classList.toggle('on', k === i));
    ds.forEach((d, k) => d.classList.toggle('on', k === i));
  });
  const zoom = () => { const p = progress(cut); cut.style.setProperty('--cz', (1.06 - p * 0.08).toFixed(3)); };
  if (!reduced) { addEventListener('scroll', zoom, { passive: true }); zoom(); }
}

/* wipes: screens slide open */
// observe the parent: a clipped element never counts as intersecting
const wipeIO = new IntersectionObserver((es) => { for (const e of es) if (e.isIntersecting) { e.target.querySelectorAll('[data-wipe]').forEach((w) => w.classList.add('in')); wipeIO.unobserve(e.target); } }, { threshold: 0.15 });
document.querySelectorAll('[data-wipe]').forEach((el, i) => { el.style.transitionDelay = `${(i % 3) * 160}ms`; if (reduced) el.classList.add('in'); });
if (!reduced) new Set([...document.querySelectorAll('[data-wipe]')].map((el) => el.parentElement)).forEach((p) => wipeIO.observe(p));

/* question: the launch ring draws itself */
const q = document.querySelector('.k-question');
if (q) {
  const onQ = () => { const r = q.getBoundingClientRect(); const p = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight + r.height * 0.4))); q.style.setProperty('--rp', reduced ? 1 : p.toFixed(3)); };
  addEventListener('scroll', onQ, { passive: true }); onQ();
}

/* footer: the name rises into place */
const giant = document.querySelector('.foot-giant');
if (giant) {
  const onG = () => { const r = giant.getBoundingClientRect(); const p = Math.min(1, Math.max(0, (innerHeight - r.top) / (r.height * 2.2))); giant.style.setProperty('--gy', `${(30 - p * 30).toFixed(1)}%`); giant.style.setProperty('--go', (0.3 + p * 0.7).toFixed(2)); };
  if (reduced) { giant.style.setProperty('--gy', '0%'); giant.style.setProperty('--go', '1'); } else { addEventListener('scroll', onG, { passive: true }); onG(); }
}

/* ------------------------------------------- scroll film: the clip follows the scroll
   <section class="scrub" style="--len: 400vh"><div class="scrub-pin"><video class="scrub-film" muted playsinline preload="auto" src="...">
   <div class="scrub-notes"><p data-at="0.1-0.35">...</p></div></div></section>
   Clips must be encoded all-intra or with a short GOP (ffmpeg -g 4) so seeking is smooth. */
document.querySelectorAll('.scrub').forEach((sec) => {
  const v = sec.querySelector('.scrub-film');
  const notes = [...sec.querySelectorAll('[data-at]')].map((n) => { const [a, b] = n.dataset.at.split('-').map(Number); return { n, a, b }; });
  let want = 0, raf = 0;
  const seek = () => { raf = 0; if (v.readyState >= 1 && v.duration) { const t = want * (v.duration - 0.05); if (Math.abs(v.currentTime - t) > 0.02) v.currentTime = t; } };
  const onS = () => {
    want = progress(sec);
    notes.forEach(({ n, a, b }) => n.classList.toggle('on', want >= a && want < b));
    if (!raf) raf = requestAnimationFrame(seek);
  };
  v.addEventListener('loadedmetadata', onS);
  addEventListener('scroll', onS, { passive: true }); onS();
});
