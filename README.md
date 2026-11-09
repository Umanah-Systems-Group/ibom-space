# ibomspace.com

The Ibom Space website. A static site: no build step, no framework, no tracking.

- `index.html` — the home page. The hero and the tug mission are told over a live 3D stage.
- `assets/js/stage.js` — the 3D engine (three.js). Every spacecraft is drawn in code: tug, customer satellite, Hartwigg kit, Caelum showcase spacecraft, Earth.
- `assets/js/site.js` — scroll-driven camera shots, reveals, video loops, menu.
- `assets/css/site.css` — all styles. On phones, headings, buttons and icons are centred.
- `assets/video/` — concept video loops and posters rendered from the same engine.
- `assets/js/vendor/` — three.js r170 (MIT, see `THREE-LICENSE`). `assets/fonts/archivo.woff2` — Archivo (SIL OFL).

## Run it locally

Any static server, for example `python3 -m http.server` in this folder, then open http://localhost:8000.

## Re-render the video loops

Needs Node, Playwright and ffmpeg:

```
node tools/render-films.mjs            # hartwigg and caelum loops
node tools/render-films.mjs hero       # still used when WebGL is unavailable
```

`tools/shoot.mjs <shot> <t> <out.png>` renders a single frame; `tools/page.mjs` screenshots the page at desktop and phone sizes.

## Honesty rules for this site

Ibom Space has no flight hardware yet. Every picture is a concept render and is labelled as one. No customer logos, no TRL claims, no performance figures that are not NASA's own published numbers for a patent.
