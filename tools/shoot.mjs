// Usage: node tools/shoot.mjs <shot> <t> <out.png> [w h]
import { createRequire } from 'node:module'; const { chromium } = createRequire(import.meta.url)(process.env.PW || 'playwright');
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.webp': 'image/webp', '.svg': 'image/svg+xml' };
export function serve() {
  return new Promise((res) => { const s = http.createServer((q, r) => { let f = path.join(root, decodeURIComponent(q.url.split('?')[0])); if (f.endsWith('/')) f += 'index.html'; fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); }).listen(0, () => res(s)); });
}
if (process.argv[1].endsWith('shoot.mjs')) {
  const [shot, t, out, w = 1280, h = 720] = process.argv.slice(2);
  const s = await serve(); const port = s.address().port;
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const pg = await b.newPage({ viewport: { width: +w, height: +h } });
  pg.on('console', m => console.log('console:', m.text())); pg.on('pageerror', e => console.log('err:', e.message));
  await pg.goto(`http://localhost:${port}/tools/film.html`);
  await pg.waitForFunction(() => window.__ready, null, { timeout: 60000 });
  await pg.evaluate(([n, tt]) => window.__frame(n, tt), [shot, +t]);
  await pg.screenshot({ path: out });
  await b.close(); s.close();
}
