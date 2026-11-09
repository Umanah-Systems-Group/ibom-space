// Usage: node tools/page.mjs <out-prefix> [scrollY,...]  Screenshots index.html at desktop and phone.
import { createRequire } from 'node:module'; import { serve } from './shoot.mjs';
const { chromium } = createRequire(import.meta.url)('playwright');
const [out, ys = '0', which = 'both'] = process.argv.slice(2);
const s = await serve(); const port = s.address().port;
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const views = { d: { width: 1440, height: 900 }, m: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 1 } };
for (const [k, vp] of Object.entries(views)) {
  if (which !== 'both' && which !== k) continue;
  const pg = await b.newPage({ viewport: { width: vp.width, height: vp.height }, isMobile: vp.isMobile, hasTouch: vp.hasTouch });
  pg.on('pageerror', e => console.log('err:', e.message)); pg.on('console', m => { if (m.type() !== 'log') console.log(m.type(), m.text()); });
  await pg.goto(`http://localhost:${port}/index.html`); await pg.waitForTimeout(2500);
  for (const y of ys.split(',')) {
    await pg.evaluate((yy) => { const el = isNaN(+yy) ? document.querySelector(yy) : null; window.scrollTo({ top: el ? el.getBoundingClientRect().top + scrollY : +yy, behavior: 'instant' }); }, y);
    await pg.waitForTimeout(3200);
    await pg.screenshot({ path: `${out}-${k}-${y.replace(/[^a-z0-9]/gi, '')}.png` });
  }
  await pg.close();
}
await b.close(); s.close();
