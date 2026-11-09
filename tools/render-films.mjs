// Renders the concept video loops used on the site: node tools/render-films.mjs [shot ...]
// Frames come from tools/film.html (the same 3D engine as the live page), then ffmpeg encodes H.264.
import { createRequire } from 'node:module'; import { serve } from './shoot.mjs';
import fs from 'node:fs'; import path from 'node:path'; import { execFileSync } from 'node:child_process'; import os from 'node:os';
const { chromium } = createRequire(import.meta.url)('playwright');
const FILMS = { hartwigg: { seconds: 10, w: 1280, h: 800 }, caelum: { seconds: 12, w: 1600, h: 900 }, hero: { seconds: 1, w: 1600, h: 1000, still: 'stage-poster' } };
const want = process.argv.slice(2).length ? process.argv.slice(2) : ['hartwigg', 'caelum'];
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const s = await serve(); const port = s.address().port;
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const name of want) {
  const f = FILMS[name]; const fps = 30; const n = f.still ? 1 : f.seconds * fps;
  const pg = await b.newPage({ viewport: { width: f.w, height: f.h } });
  await pg.goto(`http://localhost:${port}/tools/film.html`);
  await pg.waitForFunction(() => window.__ready, null, { timeout: 60000 });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `film-${name}-`));
  for (let i = 0; i < n; i++) {
    const data = await pg.evaluate(([nm, t]) => { window.__frame(nm, t); return document.getElementById('c').toDataURL('image/png'); }, [name, f.still ? 4 : i / fps]);
    fs.writeFileSync(path.join(dir, `f${String(i).padStart(4, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    if (i % 60 === 0) console.log(name, i, '/', n);
  }
  const out = path.join(root, 'assets/video');
  if (f.still) {
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', path.join(dir, 'f0000.png'), '-q:v', '4', path.join(out, `${f.still}.jpg`)]);
  } else {
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, 'f%04d.png'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', path.join(out, `${name}.mp4`)]);
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', path.join(dir, 'f0000.png'), '-q:v', '4', path.join(out, `${name}.jpg`)]);
  }
  fs.rmSync(dir, { recursive: true }); await pg.close(); console.log('done', name);
}
await b.close(); s.close();
