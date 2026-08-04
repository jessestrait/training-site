#!/usr/bin/env python3
"""
render_pdf_pages.py — Rasterize digital-native training PDFs into site pages.

Companion to restore_pdf.py. That script rehabilitates phone-scanned
spiral-bound guides (deskew, ring crop, illumination flattening, OCR); this
one handles clean vector PDFs straight from Domino's, where none of that is
needed and any "restoration" would only degrade the source.

Density matches the site's existing page images exactly: 657 px across a
612 pt (US Letter) page = 77.3 DPI. Landscape and card-size sources keep
their native aspect ratio at that same density rather than being padded into
a portrait frame -- the viewer sizes pages by width, so tall and wide pages
both display correctly.

Usage:
  python3 render_pdf_pages.py OUTDIR SPEC [SPEC ...] [--quality 78]

  SPEC is a PDF path, optionally suffixed with a 1-based page range:
      "guide.pdf"        all pages
      "guide.pdf:2-4"    pages 2 through 4
      "guide.pdf:3"      page 3 only

  Pages are written to OUTDIR as p01.jpg, p02.jpg, ... numbered sequentially
  across every SPEC, so several PDFs can be combined into one guide in a
  single run (that is how domino-ordering/ and domino-job-aids/ were built).

Dependencies:
  pip3 install --user pymupdf
"""
import argparse
import os
import sys

import fitz  # PyMuPDF

# The density every page image on the site was produced at: a 612x792 pt
# (US Letter) page lands on exactly 657x850 px. PyMuPDF rounds the pixmap
# rect outward, so the naive 657/612 overshoots height by a pixel (851);
# 1.0730 is inside the window that lands both axes exactly.
# Do not change without re-rendering all existing guides.
ZOOM = 1.0730


def parse_spec(spec):
    """'file.pdf:2-4' -> ('file.pdf', [2, 3, 4]); no range -> (path, None)."""
    path, sep, rng = spec.rpartition(":")
    if not sep or not path or os.path.exists(spec):
        return spec, None
    if "-" in rng:
        a, b = rng.split("-")
        return path, list(range(int(a), int(b) + 1))
    return path, [int(rng)]


def render(specs, outdir, quality):
    os.makedirs(outdir, exist_ok=True)
    matrix = fitz.Matrix(ZOOM, ZOOM)
    n = 0
    for spec in specs:
        path, pages = parse_spec(spec)
        doc = fitz.open(path)
        if pages is None:
            pages = range(1, doc.page_count + 1)
        for p in pages:
            if not 1 <= p <= doc.page_count:
                raise SystemExit(f"{path}: page {p} out of range "
                                 f"(1-{doc.page_count})")
            pix = doc[p - 1].get_pixmap(matrix=matrix)
            n += 1
            out = os.path.join(outdir, f"p{n:02d}.jpg")
            pix.save(out, jpg_quality=quality)
            kb = os.path.getsize(out) / 1024
            print(f"p{n:02d}.jpg  {pix.width}x{pix.height}  {kb:6.1f} KB"
                  f"   <- {os.path.basename(path)} p{p}", flush=True)
        doc.close()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--quality", type=int, default=78,
                    help="JPEG quality (default 78; existing pages sit "
                         "around 55-70 KB each)")
    args = ap.parse_args()

    n = render(args.specs, args.outdir, args.quality)
    total = sum(os.path.getsize(os.path.join(args.outdir, f))
                for f in os.listdir(args.outdir) if f.endswith(".jpg"))
    print(f"\nDONE: {n} pages -> {args.outdir} | {total / 1024:.0f} KB total")


if __name__ == "__main__":
    sys.exit(main())
