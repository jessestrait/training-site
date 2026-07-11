#!/usr/bin/env python3
"""
restore_pdf.py — Restore phone-scanned spiral-bound training guides into
clean, searchable, compact PDFs.

Pipeline per page:
  1. Rasterize from source PDF at high res
  2. Detect the paper (bright region) vs. background (carpet/table)
  3. Perspective-correct so text is square to the page
  4. Auto-detect spiral-ring side (alternates page to page) and crop it
  5. Flatten illumination -> uniform white paper, boost print saturation
  6. Rebuild as letter-size PDF via img2pdf
  7. Add OCR text layer via ocrmypdf (--optimize 0; images pre-compressed)

Usage:
  python3 restore_pdf.py INPUT.pdf OUTPUT.pdf [--pages 1-4] [--dpi-px 2200]
      [--jpeg-quality 78] [--workdir /home/claude/restore_work] [--no-ocr]

  --pages 1-4     Pilot mode: process only these pages (e.g. "1-3,48")
  --dpi-px        Long-side pixel target for rasterization (default 2200)
  --jpeg-quality  Final page JPEG quality (default 78; 55 for max compression)

Dependencies (install if missing):
  pip install opencv-python-headless numpy img2pdf ocrmypdf --break-system-packages
  apt-get install -y pngquant   # ocrmypdf dep (no sudo in this env)
Known env gotchas: `time` and `sudo` are absent; phone scans may claim
huge physical page sizes (e.g. 23"x31") which breaks ocrmypdf's own
optimizer -- that is WHY this script compresses images itself and runs
ocrmypdf with --optimize 0.
"""
import argparse, glob, os, shutil, subprocess, sys

import cv2
import numpy as np


def parse_pages(spec, total):
    if not spec:
        return list(range(1, total + 1))
    pages = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    return sorted(set(p for p in pages if 1 <= p <= total))


def page_count(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[-1])
    raise RuntimeError("Could not read page count")


def restore_page(src_path, out_path, jpeg_quality):
    """Returns dict of QC metrics. Raises on failure."""
    img = cv2.imread(src_path)
    if img is None:
        raise RuntimeError(f"unreadable image {src_path}")
    h, w = img.shape[:2]

    # 1. Find paper (bright region)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (21, 21), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = np.ones((25, 25), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError("no page contour found")
    page = max(cnts, key=cv2.contourArea)
    area_frac = cv2.contourArea(page) / (w * h)
    if area_frac < 0.35:  # page detection likely failed
        raise RuntimeError(f"page contour too small ({area_frac:.2f} of frame)")

    # 2. Perspective correction
    rect = cv2.minAreaRect(page)
    box = cv2.boxPoints(rect)
    s = box.sum(axis=1)
    d = np.diff(box, axis=1).ravel()
    tl, br = box[np.argmin(s)], box[np.argmax(s)]
    tr, bl = box[np.argmin(d)], box[np.argmax(d)]
    quad = np.array([tl, tr, br, bl], dtype=np.float32)
    W = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    H = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    warped = cv2.warpPerspective(img, M, (W, H))

    # 3. Ring crop — self-healing: rings alternate sides page to page, and
    # some pages have residue on BOTH edges. Crop, re-measure, repeat.
    wg = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    strip = int(W * 0.10)
    left_dark = float((wg[:, :strip] < 100).mean())
    right_dark = float((wg[:, -strip:] < 100).mean())
    crop_l, crop_r = int(W * 0.015), int(W * 0.015)
    if left_dark > 0.02:
        crop_l = int(W * 0.045)
    if right_dark > 0.02:
        crop_r = int(W * 0.045)
    warped = warped[int(H * 0.008):H - int(H * 0.008), crop_l:W - crop_r]
    for _ in range(4):  # heal leftover fragments, max ~8% extra per side
        g2 = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gw = g2.shape[1]
        e = int(gw * 0.02)
        ld = float((g2[:, :e] < 100).mean())
        rd = float((g2[:, -e:] < 100).mean())
        if ld <= 0.01 and rd <= 0.01:
            break
        cl = int(gw * 0.02) if ld > 0.01 else 0
        cr = int(gw * 0.02) if rd > 0.01 else 0
        warped = warped[:, cl:gw - cr]
    ring_side = ("L" if left_dark > 0.02 else "") + ("R" if right_dark > 0.02 else "") or "-"

    # 4. Flatten illumination, then "A++ max" tone curve (Jesse-approved):
    # deep black point, steep gamma, strong saturation — kills scan fade.
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    bg = cv2.medianBlur(L, 61)
    bg = cv2.GaussianBlur(bg, (0, 0), 25)
    Lf = cv2.divide(L, bg, scale=255)
    lo = np.percentile(Lf, 5.0)
    hi = np.percentile(Lf, 96.0)
    Ls = np.clip((Lf.astype(np.float32) - lo) * (255.0 / max(hi - lo, 1)), 0, 255)
    Ls = (255.0 * np.power(Ls / 255.0, 1.30)).astype(np.uint8)
    out = cv2.cvtColor(cv2.merge([Ls, A, B]), cv2.COLOR_LAB2BGR)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.40, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    cv2.imwrite(out_path, out, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

    # 5. QC metrics: residual ring fragments + background whiteness
    g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    gh, gw = g.shape
    edge_dark = max(
        float((g[:, :int(gw * 0.03)] < 100).mean()),
        float((g[:, -int(gw * 0.03):] < 100).mean()),
    )
    corner_white = min(
        g[:150, :150].mean(), g[:150, -150:].mean(),
        g[-150:, :150].mean(), g[-150:, -150:].mean(),
    )
    return {"edge_dark": edge_dark, "corner_white": float(corner_white),
            "ring_side": ring_side}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--dpi-px", type=int, default=2200)
    ap.add_argument("--jpeg-quality", type=int, default=78)
    ap.add_argument("--workdir", default="/home/claude/restore_work")
    ap.add_argument("--no-ocr", action="store_true")
    args = ap.parse_args()

    total = page_count(args.input)
    pages = parse_pages(args.pages, total)
    os.makedirs(args.workdir, exist_ok=True)
    raw_dir = os.path.join(args.workdir, "raw")
    fin_dir = os.path.join(args.workdir, "restored")
    shutil.rmtree(raw_dir, ignore_errors=True)
    shutil.rmtree(fin_dir, ignore_errors=True)
    os.makedirs(raw_dir); os.makedirs(fin_dir)

    flagged = []
    for i, p in enumerate(pages, 1):
        subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", "quality=92",
                        "-scale-to", str(args.dpi_px), "-f", str(p), "-l", str(p),
                        args.input, os.path.join(raw_dir, "pg")], check=True)
        src = sorted(glob.glob(os.path.join(raw_dir, "pg-*.jpg")))[-1]
        dst = os.path.join(fin_dir, f"page-{p:03d}.jpg")
        try:
            m = restore_page(src, dst, args.jpeg_quality)
            note = ""
            # Thresholds calibrated for the A++ max curve (gamma darkens near-whites)
            if m["edge_dark"] > 0.02 or m["corner_white"] < 195:
                note = "  <-- REVIEW (possible ring residue or shading)"
                flagged.append(p)
            print(f"[{i}/{len(pages)}] page {p}: rings={m['ring_side']} "
                  f"edge_dark={m['edge_dark']:.4f} white={m['corner_white']:.0f}{note}",
                  flush=True)
        except Exception as e:
            # Fallback: use raw page uncropped rather than losing content
            shutil.copy(src, dst)
            flagged.append(p)
            print(f"[{i}/{len(pages)}] page {p}: RESTORE FAILED ({e}) - kept raw  <-- REVIEW",
                  flush=True)
        os.remove(src)

    imgs = sorted(glob.glob(os.path.join(fin_dir, "page-*.jpg")))
    tmp_pdf = os.path.join(args.workdir, "rebuilt.pdf")
    subprocess.run(["img2pdf", *imgs, "--pagesize", "Letter", "--fit", "into",
                    "-o", tmp_pdf], check=True)

    if args.no_ocr:
        shutil.copy(tmp_pdf, args.output)
    else:
        subprocess.run(["ocrmypdf", "--optimize", "0", "--output-type", "pdf",
                        "-l", "eng", tmp_pdf, args.output], check=True)

    size_mb = os.path.getsize(args.output) / 1e6
    print(f"\nDONE: {args.output} | {len(imgs)} pages | {size_mb:.1f} MB")
    if flagged:
        print(f"PAGES NEEDING VISUAL REVIEW: {flagged}")
    else:
        print("All pages passed QC thresholds.")


if __name__ == "__main__":
    main()
