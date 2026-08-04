# Store 9337 Training Site

Static site of Domino's trainer guides, one directory per guide. No build step,
no dependencies. See README.md for architecture and the page-image pipelines.

## Analytics

Every HTML page in this repo must include the GoatCounter tracking script right before `</body>`:

```html
<script data-goatcounter="https://jesserstrait.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

This applies to any new page added to this repo. All of jessestrait's sites (jessestrait.com, training.jessestrait.com, archetype-atlas, modal-keyboard, yt-recs-wordcloud) report to this single GoatCounter site (`jesserstrait`) — don't create a different site code without asking first.

## Adding a guide

1. Render pages into `<slug>/pages/` as `p01.jpg`, `p02.jpg`, …
   - Clean digital PDF → `python3 source/render_pdf_pages.py <slug>/pages FILE.pdf`
     (needs `pip3 install --user pymupdf`). Pass several PDFs to combine them into
     one guide.
   - Phone scan of a spiral-bound book → `source/restore_pdf.py`. Written for a
     Linux container with opencv/img2pdf/ocrmypdf; it does not run on this Mac.
     Never run it on a clean digital PDF — its repair work only degrades one.
2. Copy an existing `<slug>/index.html` as the viewer template. Change the title,
   logo, `alt` text, the page count in the `P` loop, and the sidebar.
3. Add a card to the root `index.html` grid. Thumbnail is `<slug>/pages/p01.jpg`;
   the `.bar` accent colors cycle red → blue → yellow.
4. Update the guide table in `README.md`.

## Page images

- A US Letter page renders to **exactly 657×850 px**. Every page image on the site
  is at that density. `ZOOM` in `render_pdf_pages.py` is tuned to land it on both
  axes; changing it means re-rendering all nine guides.
- Landscape and card-size originals keep their native aspect ratio at that same
  density. Don't pad them into a portrait frame — the viewer sizes pages by width,
  so wide pages display correctly as-is.
- Blank pages in a source PDF are skipped rather than rendered.

## The sidebar index is the point

Each viewer's sidebar is hand-built, never generated: `.grp` section headings over
`.item` entries calling `jump(idx)`. **`idx` is 0-based** into `P`, so `jump(2)` is
page 3 — the counter displays 1-based, so they don't match.

Building one means reading the actual pages and mapping each topic to the page it
starts on. Digital PDFs give exact text; scans need the OCR in `source/`. A generic
"Page 1, Page 2" list would defeat the purpose — this index is what makes a booklet
usable on a phone mid-shift, and it's the part worth spending real time on.

## Local preview

```bash
python3 -m http.server 8791 --directory .
```

## Deploy

GitHub Pages from `master`; custom domain via `CNAME`. Pushing image-heavy commits
over HTTPS can fail with `RPC failed; HTTP 400` — this repo has
`http.postBuffer=524288000` set locally to prevent it.
