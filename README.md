# ibomspace.com

The Ibom Space website. A static site: no build step, no framework, no tracking.

- `index.html` — the home page. The hero and the tug mission run on real NASA footage, credited at the bottom of the page.
- `assets/film/` — NASA public-domain footage (Earth from the ISS, Landsat, Psyche, Europa Clipper array) cut from the Umanah Systems Group site reel, plus `landsat-track.json`, the satellite position measured frame by frame for the navigation overlay.
- `assets/js/site.js` — the tug film that changes per mission step, the navigation tracking overlay, reveals, video loops, menu.
- `assets/css/site.css` — all styles. On phones, headings, buttons and icons are centred.

## Run it locally

Any static server, for example `python3 -m http.server` in this folder, then open http://localhost:8000.


## Honesty rules for this site

Ibom Space has no flight hardware yet. All footage is NASA public domain, credited, and never presented as Ibom hardware. No customer logos, no TRL claims, no performance figures that are not NASA's own published numbers for a patent.
