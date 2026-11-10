// Usage: node tools/page.mjs <out-prefix> [scrollY,...]  Screenshots index.html at desktop and phone.
import { createRequire } from 'node:module';
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.json': 'application/json' };
function serve() {
  return new Promise((res) => { const s = http.createServer((q, r) => { let f = path.join(root, decodeURIComponent(q.url.split('?')[0])); if (f.endsWith('/')) f += 'index.html'; fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); }).listen(0, () => res(s)); });
}
const { chromium } = createRequire(import.meta.url)('playwright');
const [out, ys = '0', which = 'both'] = process.argv.slice(2);
const s = await serve(); const port = s.address().port;
const b = await chromium.launch();
const views = { d: { width: 1440, height: 900 }, m: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 1 } };
for (const [k, vp] of Object.entries(views)) {
  if (which !== 'both' && which !== k) continue;
  const pg = await b.newPage({ viewport: { width: vp.width, height: vp.height }, isMobile: vp.isMobile, hasTouch: vp.hasTouch });
  pg.on('pageerror', e => console.log('err:', e.message)); pg.on('console', m => { if (m.type() !== 'log') console.log(m.type(), m.text()); });
  await pg.goto(`http://localhost:${port}/${process.env.PAGE || 'index.html'}`); await pg.waitForTimeout(2500);
  for (const y of ys.split(',')) {
    await pg.evaluate((yy) => { const [sel, off = 0] = yy.split('+'); const el = isNaN(+sel) ? document.querySelector(sel) : null; window.scrollTo({ top: (el ? el.getBoundingClientRect().top + scrollY : +sel) + +off, behavior: 'instant' }); }, y);
    await pg.waitForTimeout(3200);
    await pg.screenshot({ path: `${out}-${k}-${y.replace(/[^a-z0-9]/gi, '')}.png` });
  }
  await pg.close();
}
await b.close(); s.close();
