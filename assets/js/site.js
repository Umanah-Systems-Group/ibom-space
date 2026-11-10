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
