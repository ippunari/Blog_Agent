#!/usr/bin/env python3
"""후보 파일(md)을 Google 문서로 올릴 '보기용 사본' md로 바꾼다.

- 맨 위에 "보기용 사본" 안내 한 줄을 넣는다
- 머리의 YAML 블록(---)은 Google 문서로 바꿀 때 깨지므로 「수집 정보」 목록으로 바꾼다
- 나머지 본문은 그대로 둔다 (원본은 로컬 candidates/*.md)

사용: python3 -I export_doc.py candidates/2026-11-20-am.md --out "$SP/candidates_doc.md"
"""
import argparse
import sys

NOTE = ("> **보기용 사본** — 원본은 BlogAgent 로컬 `candidates/{name}`입니다. "
        "이 문서를 고쳐도 다음 단계에 반영되지 않습니다. 의견은 댓글로 남겨 주세요.")

LABELS = {
    "collected_at": "수집 일시",
    "slot": "회차",
    "range_from": "수집 범위 시작",
    "counts": "건수",
}


def convert(text: str, name: str) -> str:
    lines = text.splitlines()
    meta, body = [], lines
    if lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1)
        except ValueError:
            end = -1
        if end > 0:
            meta, body = lines[1:end], lines[end + 1:]

    out = [NOTE.format(name=name), ""]
    # 본문 첫 H1을 먼저, 그 아래 수집 정보
    while body and not body[0].strip():
        body = body[1:]
    if body and body[0].startswith("# "):
        out += [body[0], ""]
        body = body[1:]
    if meta:
        out.append("**수집 정보**")
        out.append("")
        for m in meta:
            if ":" not in m:
                continue
            k, v = m.split(":", 1)
            out.append(f"- {LABELS.get(k.strip(), k.strip())}: {v.strip()}")
        out.append("")
    out += body
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.src, encoding="utf-8") as f:
        text = f.read()
    name = a.src.replace("\\", "/").split("/")[-1]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(convert(text, name))
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
