#!/usr/bin/env python3
"""blog-publish 발행 후: 사람이 Ghost에서 발행·예약한 뒤 실행한다 (rules/blog-publish.md 「발행 후」).

1. URL이 https://atatakaidigital.com/ja/blog/<slug> 인지 (slug를 바꾸지 않았는지)
2. 공개 글 점검 (예약이면 건너뜀 → 공개 뒤 --verify-live):
   200 / 제목 / SOURCES / 남은 초안 표시 없음 / FAQPage 구조화 데이터가 정확히 1개 / og:image
3. 역링크: check_outline.py --verify-links 로 넣을 곳을 다시 확인 → publish/<slug>/backlinks.md (사람이 붙일 HTML 조각)
4. 카드에 published_at·url, status: 발행 완료
5. 카드·research·outlines·drafts·factcheck·publish/<slug> 를 각 폴더 done/YYYY-MM/ 로 옮긴다 (D40·D44)
점검 오류가 있으면 2에서 멈춘다 (옮기지 않음). 역링크 위치 오류는 backlinks.md에 적고 사람에게 묻는다

사용법:
  python3 -I after_publish.py <slug> <URL> [--scheduled "2026-11-23 08:00"] [--root .]
  python3 -I after_publish.py <slug> --verify-live [--root .]     # 예약 글이 공개된 뒤
"""
import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SITE = "https://atatakaidigital.com"
UA = "Mozilla/5.0 (compatible; BlogAgentPublish/1.0)"
HERE = Path(__file__).resolve().parent


def front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            k, sep, v = ln.partition(":")
            if sep and re.match(r"^[a-z_]+$", k.strip()):
                out[k.strip()] = v.strip()
    return out


def set_front(path, items):
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    lines = m.group(1).splitlines()
    for k, v in items.items():
        for i, ln in enumerate(lines):
            if ln.startswith(k + ":"):
                lines[i] = f"{k}: {v}"
                break
        else:
            lines.append(f"{k}: {v}")
    path.write_text("---\n" + "\n".join(lines) + "\n---\n" + text[m.end():])


def fetch(url):
    p = subprocess.run(["curl", "-sSL", "--compressed", "--max-time", "20", "-A", UA,
                        "-w", "\n%{http_code}", "--", url], capture_output=True)
    out = p.stdout.decode("utf-8", "replace")
    body, _, code = out.rpartition("\n")
    return code.strip(), body


def live_check(url, title, card2):
    errs = []
    code, page = fetch(url)
    if code != "200":
        return [f"글이 열리지 않음: HTTP {code}"]
    if title.split("｜")[0] not in page:
        errs.append("페이지에 제목이 없음")
    if 'class="cs-src"' not in page:
        errs.append("SOURCES(cs-src)가 없음 — 카드 2가 빠졌나")
    for pat in (r"\[S\d+\]", r"\[(EXP|OP|\?)\]", r"^:::", r"<!-- *차별"):
        if re.search(pat, page, re.M):
            errs.append(f"초안 표시가 남음: {pat}")
    want = 1 if '"FAQPage"' in card2 else 0
    got = page.count('"@type":"FAQPage"') + page.count('"@type": "FAQPage"')
    if got != want:
        errs.append(f"FAQPage 구조화 데이터 {got}개 (기대 {want}) — 사이트가 따로 만들면 카드 2 끝 script를 지운다")
    if 'property="og:image"' not in page:
        errs.append("og:image 없음 — 대표 이미지를 넣었나")
    return errs


def backlinks(root, slug, outline_path):
    rows = []
    text = outline_path.read_text()
    m = re.search(r"^## 역링크\n(.*?)(?=^## )", text, re.S | re.M)
    for ln in (m.group(1).splitlines() if m else []):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 3 and c[0].startswith("http"):
            rows.append(c)
    p = subprocess.run([sys.executable, "-I", str(HERE.parent / "blog-outline" / "check_outline.py"),
                        str(outline_path), "--root", str(root), "--verify-links"], capture_output=True, text=True)
    verify = (p.stdout + p.stderr).strip().splitlines()
    ok = p.returncode == 0
    out = [f"# 역링크: {slug}", "",
           "> 기존 글 HTML 카드(본문 카드)를 열어, 「넣을 곳」 섹션 끝 — 그 섹션의 まとめ 말풍선(`hta-say`) **바로 위**에 조각을 붙인다. "
           "공개된 뒤에 붙인다 (예약 글이면 공개 시각 뒤)", "",
           f"- 넣을 곳 다시 확인 (check_outline.py --verify-links): {'통과' if ok else '⚠ 문제 있음 — 아래, 사람에게 비슷한 위치를 묻는다'}"]
    if not ok:
        out += ["```", *verify[-10:], "```"]
    out += [""]
    for i, (url, where, anchor) in enumerate(rows, 1):
        out += [f"## {i}. {url}", f"- 넣을 곳: {where}", "```html",
                f'<p>あわせて読みたい：<a href="/ja/blog/{slug}">{anchor}</a></p>', "```",
                "- [ ] 붙임 / [ ] 기존 글 다시 열어 링크 확인", ""]
    if len(rows) < 2:
        out.append("⚠ 역링크가 2개 미만 (common.md 6장 7) — 설계안 「역링크」를 보충한다")
    return "\n".join(out) + "\n", ok, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("url", nargs="?")
    ap.add_argument("--scheduled")
    ap.add_argument("--verify-live", action="store_true")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    slug = a.slug

    if a.verify_live:
        cards = sorted((root / "briefs" / "done").glob(f"*/{slug}.md"))
        if not cards:
            sys.exit("❌ done 폴더에 카드가 없음")
        c = front(cards[-1].read_text())
        month = cards[-1].parent.name
        card2 = (root / "publish" / "done" / month / slug / "card2-body.html").read_text()
        title = re.search(r"^# (.+)$", (root / "drafts" / "done" / month / f"{slug}.md").read_text(), re.M).group(1)
        errs = live_check(c["url"], title, card2)
        for e in errs:
            print("❌", e)
        print("불통과" if errs else f"통과 — 공개 확인 {c['url']}")
        sys.exit(1 if errs else 0)

    want = f"{SITE}/ja/blog/{slug}"
    if not a.url or a.url.rstrip("/") != want:
        sys.exit(f"❌ URL이 {want} 가 아님 (slug는 바꾸지 않는다): {a.url}")
    card_p = root / "briefs" / f"{slug}.md"
    pub = root / "publish" / slug
    if not card_p.exists() or not (pub / "card2-body.html").exists():
        sys.exit("❌ 카드 또는 publish 파일이 없음 — build_publish.py부터")
    card = front(card_p.read_text())
    if card.get("status") != "발행 준비":
        sys.exit(f"❌ 카드 상태가 「발행 준비」가 아님: {card.get('status')}")
    now = datetime.now(JST)
    title = re.search(r"^# (.+)$", (root / "drafts" / f"{slug}.md").read_text(), re.M).group(1)

    if a.scheduled:
        when = datetime.strptime(a.scheduled, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if when <= now:
            sys.exit("❌ 예약 시각이 지났음 — 공개된 글이면 --scheduled 없이")
        if card.get("route") == "속보":
            print("⚠ 속보인데 예약 — 속보는 확인 즉시 발행 (rules/blog-publish.md 「발행 시간」)")
        print(f"예약 {when:%Y-%m-%d %H:%M} — 공개 점검은 공개 뒤 --verify-live")
    else:
        when = now
        errs = live_check(a.url, title, (pub / "card2-body.html").read_text())
        if errs:
            for e in errs:
                print("❌", e)
            sys.exit("불통과 — Ghost에서 고친 뒤 다시 실행 (아무 파일도 옮기지 않음)")
        print("공개 글 점검 통과")

    bl, bl_ok, n = backlinks(root, slug, root / "outlines" / f"{slug}.md")
    (pub / "backlinks.md").write_text(bl)
    print(f"역링크 {n}개 → publish/{slug}/backlinks.md ({'위치 확인 통과' if bl_ok else '⚠ 위치 문제 — 사람에게'})")

    set_front(card_p, {"status": "발행 완료", "published_at": when.strftime("%Y-%m-%dT%H:%M+09:00") + (" (예약)" if a.scheduled else ""),
                       "url": a.url.rstrip("/")})
    month = when.strftime("%Y-%m")
    moved = []
    for folder, name in (("briefs", f"{slug}.md"), ("research", f"{slug}.md"), ("outlines", f"{slug}.md"),
                         ("drafts", f"{slug}.md"), ("factcheck", f"{slug}.md"), ("publish", slug)):
        src = root / folder / name
        if src.exists():
            dst = root / folder / "done" / month
            dst.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst / name))
            moved.append(f"{folder}/done/{month}/{name}")
    print("옮김:", ", ".join(moved))
    print("남은 일: 역링크 붙이기(backlinks.md) / Search Console 색인 요청 (연결 뒤) / 다음 단계 blog-distribute")


if __name__ == "__main__":
    main()
