#!/usr/bin/env python3
"""blog-publish: 대표 이미지 원본을 규격(1800×945 WebP 200KB 이하 — 사이트 기존 대표 이미지와 같은 크기, OG 1.91:1)으로 바꾼다.

- 사이트 표시 미리보기도 만든다 (D64): 글 머리는 21:9(휴대폰 16:9)로 **위·왼쪽 기준** 자르고, 아래쪽은 본문 카드가 겹친다
  → hero_site_preview.png (데스크톱·휴대폰, 가려지는 곳은 어둡게). 주제 장치·키워드 글자가 밝은 곳에 있어야 한다

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

W, H, MAX_KB = 1800, 945, 200
CARD = 0.16   # 데스크톱 글 머리 21:9 중 아래 16%는 본문 카드가 겹친다 (2026-11-21 사이트 화면에서 잼)


def site_preview(im, out):
    """사이트 글 머리처럼 자른 그림: 데스크톱 21:9 위·왼쪽 기준 + 아래 카드 겹침, 휴대폰 16:9"""
    from PIL import ImageDraw
    dh = round(W * 9 / 21)                       # 21:9 → 위에서부터
    desk = im.crop((0, 0, W, dh)).convert("RGBA")
    shade = Image.new("RGBA", desk.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle((0, round(dh * (1 - CARD)), W, dh), fill=(255, 255, 255, 190))
    desk = Image.alpha_composite(desk, shade).convert("RGB")
    mw = round(H * 16 / 9)                       # 16:9 → 왼쪽부터
    mob = im.crop((0, 0, mw, H)).resize((round(mw * 0.5), round(H * 0.5)))
    canvas = Image.new("RGB", (W, dh + mob.size[1] + 30), (240, 240, 240))
    canvas.paste(desk, (0, 0)); canvas.paste(mob, (0, dh + 30))
    p = out / "hero_site_preview.png"
    canvas.save(p)
    print(f"사이트 표시 미리보기 — {p} (위: 데스크톱 21:9, 흰 띠 = 본문 카드에 가려짐 / 아래: 휴대폰 16:9) → 직접 열어 본다")


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
    if sw < W * 0.9 or sh < H * 0.9:   # 생성 도구 출력(약 1,730px)은 조금 늘려도 괜찮다
        print(f"⚠ 원본이 작다 {sw}×{sh} — 늘려서 흐려질 수 있음")
    r = W / H
    if sw / sh > r:
        nw = round(sh * r)
        im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        nh = round(sw / r)
        im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
    base = im
    out = Path(a.root) / "publish" / a.slug
    out.mkdir(parents=True, exist_ok=True)
    for w in (W, 1600, 1440, 1200):                  # 같은 1.905:1 — 세밀한 그림이면 조금 작게
        h = round(w * H / W)
        im = base.resize((w, h), Image.LANCZOS)
        for q in range(85, 59, -5):
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=q, method=6)
            kb = buf.tell() / 1024
            if kb <= MAX_KB:
                dst = out / f"{a.slug}_hero.webp"
                dst.write_bytes(buf.getvalue())
                (out / "hero_alt.txt").write_text(a.alt.strip() + "\n")
                print(f"통과 — {dst} {w}×{h} WebP 품질 {q} {kb:.0f}KB / alt: {a.alt.strip()}"
                      + ("" if w == W else f" (⚠ {W}px로는 {MAX_KB}KB를 넘어 {w}px — 다음엔 프롬프트를 더 매끈하게)"))
                site_preview(im.resize((W, H), Image.LANCZOS), out)
                return
    sys.exit(f"❌ 1200px·품질 60에서도 {kb:.0f}KB > {MAX_KB}KB — 종이 질감·잔무늬 없이 매끈하게 다시 만든다")


if __name__ == "__main__":
    main()
