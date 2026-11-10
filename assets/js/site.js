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
// The tracking box follows the satellite in the NASA clip (track measured from the film's frames).
// The readout numbers are a simulated approach, labelled as such on the page.
const navFilm = document.getElementById('nav-film');
const track = document.getElementById('track');
if (navFilm && track) {
  let boxes = null, fps = 10;
  fetch('assets/film/landsat-track.json').then((r) => r.json()).then((d) => { boxes = d.boxes; fps = d.fps; }).catch(() => {});
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

/* ------------------------------------------------- jobs: one film, four jobs */
const jobs = document.getElementById('jobs');
if (jobs) {
  const vids = [...jobs.querySelectorAll('.k-jobs-film')];
  const items = [...jobs.querySelectorAll('.k-jobs-list li')];
  let cur = -1, front = 0, inView = false;
  const setJob = (i) => {
    if (i === cur) return; cur = i;
    items.forEach((li, k) => li.classList.toggle('on', k === i));
    const name = items[i].dataset.film, next = vids[1 - front];
    next.src = `assets/film/${name}.mp4`; next.poster = `assets/film/${name}.jpg`;
    const swap = () => { next.classList.add('on'); vids[front].classList.remove('on'); const old = vids[front]; setTimeout(() => old.pause(), 1200); front = 1 - front; };
    if (inView && !reduced) next.play().then(swap).catch(swap); else swap();
  };
  const onJobs = () => {
    const p = progress(jobs);
    setJob(Math.min(items.length - 1, Math.floor(p * items.length * 0.999)));
    jobs.style.setProperty('--z', (1.12 - p * 0.1).toFixed(3));
    vids.forEach((v) => v.style.setProperty('--z', (1.12 - p * 0.1).toFixed(3)));
  };
  new IntersectionObserver((es) => { inView = es[0].isIntersecting; const v = vids[front]; if (inView && !reduced) v.play().catch(() => {}); else v.pause(); }).observe(jobs);
  addEventListener('scroll', onJobs, { passive: true }); onJobs();
}

/* ---------------------------------------- orbits: Earth comes in, orbits draw */
const orbits = document.getElementById('orbits');
if (orbits) {
  const globe = document.getElementById('globe');
  const tabs = [...orbits.querySelectorAll('[role=tab]')];
  const select = (name) => {
    orbits.dataset.orbit = name;
    tabs.forEach((t) => { const on = t.dataset.orbit === name; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; document.getElementById(t.getAttribute('aria-controls')).hidden = !on; });
  };
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => { userPicked = true; select(t.dataset.orbit); });
    t.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { const n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); n.click(); } });
  });
  let userPicked = false;
  select('leo');
  const ease = (x) => 1 - Math.pow(1 - x, 3);
  const onOrbits = () => {
    const p = progress(orbits);
    const a = ease(Math.min(1, p / 0.45));            // Earth rises and shrinks to a globe
    const gs = 2.3 - a * 1.6, gy = 52 - a * 102;     // scale, vertical offset (% of own size)
    globe.style.setProperty('--gs', gs.toFixed(3));
    globe.style.setProperty('--gy', `${gy.toFixed(1)}%`);
    const o = Math.min(1, Math.max(0, (p - 0.42) / 0.12));
    orbits.style.setProperty('--o', o.toFixed(2));
    orbits.style.setProperty('--p2', Math.min(1, Math.max(0, (p - 0.3) / 0.3)).toFixed(2));
    orbits.classList.toggle('show-tabs', o > 0.5);
    if (!userPicked && o > 0.5) select(p < 0.68 ? 'leo' : p < 0.84 ? 'meo' : 'geo');
  };
  addEventListener('scroll', onOrbits, { passive: true }); addEventListener('resize', onOrbits); onOrbits();
}

/* ------------------------------------------------ question: slow push-in */
const q = document.querySelector('.k-question');
if (q && !reduced) {
  const onQ = () => { const r = q.getBoundingClientRect(); const p = Math.min(1, Math.max(0, 1 - (r.top + r.height) / (innerHeight + r.height))); q.querySelector('.k-q-film').style.setProperty('--qz', (1.18 - p * 0.14).toFixed(3)); };
  addEventListener('scroll', onQ, { passive: true }); onQ();
}
