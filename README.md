# Store 9337 Training

Digital training site for Domino's Store 9337 (Rainbow Pizza franchise), built
from scanned trainer guides and the printed materials that ship in launch kits.
Owner: Jesse Strait, GM.

**Live:** [training.jessestrait.com](https://training.jessestrait.com)

## What's here

- `index.html` — the landing grid: one card per guide
- One directory per guide, each holding its own `index.html` viewer and a
  `pages/` folder of page images (`tutorial/` is the exception — it holds a
  video and its poster frame instead):

  | Directory | Guide | Pages |
  | --- | --- | --- |
  | `playbook/` | Domino™ In-Store Training Playbook | 11 |
  | `tutorial/` | Domino™ Product Tutorial Video | video, 4:30 |
  | `domino-job-aids/` | Domino™ Job Aids & Cards | 6 |
  | `domino-ordering/` | Domino™ Ordering Guides | 3 |
  | `essentials/` | In-Store Training Essentials | 54 |
  | `activities/` | Activities Guide | 40 |
  | `csr/` | CSR Certification | 12 |
  | `delivery-expert/` | Delivery Expert Certification | 8 |
  | `operations-guide/` | Operations Assessment Guidelines | 19 |
  | `operations-form/` | Operations Assessment Form | 3 |

- `source/` — OCR text (`TrainerGuide_9337_MAXCrisp_KB.md`) and the two
  page-image pipelines

## Architecture

Static HTML, no framework and no build step — works on any static host
(currently GitHub Pages). Every guide viewer is the same self-contained page:

- `P` = array of image paths, in guide page order
- The sidebar is a hand-built index: `.grp` section headings over `.item`
  entries that call `jump(idx)` to land on the page covering that topic, then
  close the drawer. This is the part worth the care — it is what makes a
  scanned booklet usable on a phone mid-shift.
- `step(±1)` = Previous/Next

## Page images

Two pipelines in `source/`, picked by what the original is:

- **`restore_pdf.py`** — for phone-scanned spiral-bound guides. Perspective
  correction, spiral-ring cropping, illumination flattening, and an OCR text
  layer. Used for `essentials/`, `activities/`, `csr/`, `delivery-expert/`,
  `operations-guide/`, `operations-form/`. Written to run in a Linux container
  with opencv/img2pdf/ocrmypdf, not on the Mac.

- **`render_pdf_pages.py`** — for clean digital PDFs that need no repair, just
  rasterizing. Used for `playbook/`, `domino-job-aids/`, `domino-ordering/`.
  Runs locally; needs only `pip3 install --user pymupdf`.

Both emit page images at the same density: a US Letter page lands on exactly
657×850 px. Landscape and card-size originals keep their native aspect ratio at
that same density rather than being padded into a portrait frame — the viewer
sizes pages by width, so both display correctly.

Several PDFs can be combined into one guide by passing more than one spec:

```bash
python3 source/render_pdf_pages.py domino-ordering/pages \
  "~/Downloads/DOMINO/Domino Dough Ordering Guide _NON DOC.pdf" \
  "~/Downloads/DOMINO/Domino Additional Ordering Guide.pdf" \
  "~/Downloads/DOMINO/Domino Dough Ordering Guide _ DOC.pdf"
```

Source PDFs are not committed; only the rendered pages are.

## Deployment

GitHub Pages, custom domain via `CNAME` → `training.jessestrait.com`.
