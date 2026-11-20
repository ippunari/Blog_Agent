#!/usr/bin/env python3
"""blog-publish: 사람이 만든 대표 이미지 원본을 규격(1200×630 WebP 200KB 이하)으로 바꾼다.

- 가운데 기준으로 1200:630 비율로 자르고 줄인다. 메타데이터(EXIF 등)는 넣지 않는다
- 품질을 낮춰 가며 200KB 이하가 될 때까지 저장 (최저 품질 50에서도 넘으면 오류)
- 파일명은 publish/<slug>/<slug>_hero.webp (내용을 설명하는 영어 = slug), alt는 hero_alt.txt
- 원본 파일은 바꾸지 않는다

사용법:
  python3 -I make_hero.py <원본 이미지> <slug> --alt "画像の内容の説明" [--root .]
"""
import argparse
import io
import sys
from pathlib import Path

from PIL import Image

W, H, MAX_KB = 1200, 630, 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("slug")
    ap.add_argument("--alt", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    if len(a.alt.strip()) < 10:
        sys.exit("❌ alt가 너무 짧음 — 이미지에 무엇이 보이는지 일본어로 (10자 이상)")
    im = Image.open(a.src)
    im = im.convert("RGB")
    sw, sh = im.size
    if sw < W or sh < H:
        print(f"⚠ 원본이 작다 {sw}×{sh} — 늘려서 흐려질 수 있음")
    r = W / H
    if sw / sh > r:
        nw = round(sh * r)
        im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        nh = round(sw / r)
        im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
    im = im.resize((W, H), Image.LANCZOS)
    out = Path(a.root) / "publish" / a.slug
    out.mkdir(parents=True, exist_ok=True)
    for q in range(85, 49, -5):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        kb = buf.tell() / 1024
        if kb <= MAX_KB:
            dst = out / f"{a.slug}_hero.webp"
            dst.write_bytes(buf.getvalue())
            (out / "hero_alt.txt").write_text(a.alt.strip() + "\n")
            print(f"통과 — {dst} {W}×{H} WebP 품질 {q} {kb:.0f}KB / alt: {a.alt.strip()}")
            return
    sys.exit(f"❌ 품질 50에서도 {kb:.0f}KB > {MAX_KB}KB — 원본을 단순하게 다시 만든다")


if __name__ == "__main__":
    main()
