# Store 9337 Training

Digital training site for Domino's Store 9337 (Rainbow Pizza franchise), built
from scanned trainer guides. Owner: Jesse Strait, GM.

**Live:** [training.jessestrait.com](https://training.jessestrait.com)

## What's here

- `index.html` — the whole app: dark-mode sidebar + pager, vanilla JS, no
  framework, no build step
- `pages/` — restored page images for guide 1, "In-Store Training Essentials"
  (54 pages, `p01.jpg`–`p54.jpg`)
- `source/` — OCR text (`TrainerGuide_9337_MAXCrisp_KB.md`) and the PDF
  restoration pipeline (`restore_pdf.py`) used to produce the page images

This is guide 1 of 5. Four more scanned guides still need processing with
`restore_pdf.py` and adding as additional sidebar sections in `index.html`
(see comments in `source/restore_pdf.py` for the pipeline).

## Architecture

Single static `index.html`, images in a sibling `pages/` folder. No build
step, no dependencies — works on any static host (currently GitHub Pages).

- `P` = array of image paths, in guide page order
- Sidebar items call `jump(idx)` to jump to a page and close the drawer
- `step(±1)` = Previous/Next

## Deployment

GitHub Pages, custom domain via `CNAME` → `training.jessestrait.com`.
