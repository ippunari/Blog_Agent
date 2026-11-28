#!/usr/bin/env python3
"""blog-publish: 본문 이미지 찾기·등록 (D55). 사람은 ◆ 미리보기에서 남길지 뺄지만 정한다.

쓸 수 있는 이미지 (rules/blog-publish.md 「본문 이미지」):
  diagram  편집부가 노트 사실로 만든 그림 (SVG, 본문에 그대로 넣는다)
  commons  Wikimedia Commons — CC0·퍼블릭 도메인·CC BY·CC BY-SA만, 상표·초상 제한 표시가 없는 것
  usgov    미국 연방 기관 저작물 (17 U.S.C. §105, 퍼블릭 도메인) — 크레디트가 따로 붙은 사진은 제외
쓰지 않는 것: 뉴스·블로그 사진, 이미지 검색 결과, 이용 조건을 모르는 이미지, 타사 로고, 화면 캡처·프레스킷(확인 전)

사용법:
  python3 -I find_images.py search "server room" [--n 8]                 # Commons 후보 (라이선스 걸러서)
  python3 -I find_images.py add-commons "File:XXX.jpg" <slug> --section 2 --alt "..." --caption "..."
  python3 -I find_images.py add-diagram <svg파일> <slug> --section 1 [--slot N] --alt "..." --caption "...（出典：…）"
  python3 -I find_images.py add-usgov <이미지URL> <slug> --page <실린 페이지 URL> --agency CISA --section 3 --alt "..." --caption "..."
  python3 -I find_images.py list <slug>
  python3 -I find_images.py drop <slug> <번호>        # 사람이 「이미지 N 빼」라고 하면
등록하면 publish/<slug>/images.json 에 쌓이고, build_publish.py가 섹션 직답 바로 아래에 넣는다
"""
import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

JST = timezone(timedelta(hours=9))
UA = "BlogAgentPublish/1.0 (company blog image licensing check)"
API = "https://commons.wikimedia.org/w/api.php"
OK_LICENSE = re.compile(r"^(CC0|Public domain|PD\b|PD-|CC BY(-SA)? \d(\.\d)?)", re.I)
NG_LICENSE = re.compile(r"\b(NC|ND)\b|non-?commercial|no ?deriv|fair use", re.I)
# 라이선스가 깨끗해도 맥락이 부적절한 것 (사건 증거·범죄·정치·전쟁·재해·의료) — D55 시험에서 FBI 사건 증거 사진이 PD로 나왔다
NG_CONTEXT = re.compile(r"epstein|evidence|files released|arrest|crime|criminal|court|lawsuit|police|war\b|military|weapon|"
                        r"protest|election|politic|disaster|victim|death|hospital|patient|nazi|terror", re.I)
US_FEDERAL = ("cisa.gov", "nist.gov", "fbi.gov", "ic3.gov", "ftc.gov", "nasa.gov", "nsa.gov", "dhs.gov", "fcc.gov",
              "sec.gov", "usa.gov", "whitehouse.gov", "nih.gov", "cdc.gov", "noaa.gov", "usgs.gov", "energy.gov",
              "defense.gov", "army.mil", "navy.mil", "af.mil")


def get_json(url):
    p = subprocess.run(["curl", "-sS", "--max-time", "25", "-A", UA, "--", url], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def commons_info(titles=None, search=None, n=8):
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
         "iiurlwidth": "960"}
    if search:
        q.update({"generator": "search", "gsrnamespace": "6", "gsrsearch": search, "gsrlimit": str(n * 3)})
    else:
        q["titles"] = titles
    url = API + "?" + "&".join(f"{k}={quote(v)}" for k, v in q.items())
    pages = get_json(url).get("query", {}).get("pages", {})
    out = []
    for p in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata", {})
        g = lambda k: strip(m.get(k, {}).get("value", ""))
        lic = g("LicenseShortName")
        out.append({"title": p["title"], "license": lic, "license_url": g("LicenseUrl"), "artist": g("Artist") or g("Credit"),
                    "restrictions": g("Restrictions"), "width": ii.get("width", 0), "height": ii.get("height", 0),
                    "mime": ii.get("mime", ""), "thumb": ii.get("thumburl", ""), "page": ii.get("descriptionurl", ""),
                    "desc": g("ImageDescription")[:120],
                    "ok": bool(OK_LICENSE.search(lic)) and not NG_LICENSE.search(lic) and not g("Restrictions")
                    and not NG_CONTEXT.search(p["title"] + " " + g("ImageDescription") + " " + g("Categories"))
                    and ii.get("mime", "").startswith("image/") and ii.get("width", 0) >= 800})
    return out


def load(slug, root):
    p = root / "publish" / slug / "images.json"
    return p, (json.loads(p.read_text()) if p.exists() else [])


def save(p, items):
    p.parent.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(items, 1):
        it["n"] = i
    p.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")


def check_text(a):
    if len(a.alt.strip()) < 10:
        sys.exit("❌ alt가 너무 짧음 — 무엇이 보이는지 일본어로 (10자 이상)")
    if not a.caption.strip():
        sys.exit("❌ caption(일본어 설명)이 없음")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("q"); s.add_argument("--n", type=int, default=8)
    for name in ("add-commons", "add-diagram", "add-usgov"):
        x = sub.add_parser(name)
        x.add_argument("src"); x.add_argument("slug")
        x.add_argument("--section", type=int, required=True, help="몇 번째 본문 H2 아래에 (1부터)")
        x.add_argument("--alt", required=True); x.add_argument("--caption", required=True)
        x.add_argument("--slot", type=int, help="설계안 그림 자리 N번째 행 — 초안의 <!-- 그림 N --> 자리에 넣는다 (D97)")
        if name == "add-usgov":
            x.add_argument("--page", required=True); x.add_argument("--agency", required=True)
    l = sub.add_parser("list"); l.add_argument("slug")
    d = sub.add_parser("drop"); d.add_argument("slug"); d.add_argument("n", type=int)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    today = datetime.now(JST).strftime("%Y-%m-%d")

    if a.cmd == "search":
        res = [r for r in commons_info(search=a.q, n=a.n)]
        ok = [r for r in res if r["ok"]][:a.n]
        print(f"후보 {len(ok)}개 (라이선스·크기·상표 제한으로 거름, 전체 {len(res)}개)")
        for r in ok:
            print(f"- {r['title']} | {r['license']} | {r['artist'][:40]} | {r['width']}×{r['height']} | {r['desc']}\n  {r['thumb']}")
        return
    if a.cmd == "list":
        _, items = load(a.slug, root)
        for it in items:
            print(f"{it['n']}. [{'남김' if it.get('keep', True) else '뺌'}] {it['kind']} 섹션{it['section']}{' 그림' + str(it['slot']) if it.get('slot') else ''} {it['license']} — {it['caption'][:40]}")
        return
    if a.cmd == "drop":
        p, items = load(a.slug, root)
        for it in items:
            if it["n"] == a.n:
                it["keep"] = False
        save(p, items)
        print(f"이미지 {a.n} 뺌 — build_publish.py를 다시 돌린다")
        return

    check_text(a)
    p, items = load(a.slug, root)
    base = {"section": a.section, "alt": a.alt.strip(), "caption": a.caption.strip(), "checked": today, "keep": True}
    if a.slot:
        base["slot"] = a.slot
    if a.cmd == "add-commons":
        r = commons_info(titles=a.src)
        if not r:
            sys.exit("❌ Commons에서 찾지 못함")
        r = r[0]
        if not r["ok"]:
            sys.exit(f"❌ 쓸 수 없는 이미지: 라이선스 「{r['license']}」 제한 「{r['restrictions']}」 크기 {r['width']}")
        items.append({**base, "kind": "commons", "src": r["thumb"], "page": r["page"], "license": r["license"],
                      "license_url": r["license_url"], "credit": r["artist"] or "不明"})
    elif a.cmd == "add-diagram":
        svg = Path(a.src).read_text()
        if "<svg" not in svg or re.search(r"<script|on\w+=|href=\"http", svg, re.I):
            sys.exit("❌ SVG가 아니거나 스크립트·외부 링크가 들어 있음")
        dst = root / "publish" / a.slug / "img" / Path(a.src).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if Path(a.src).resolve() != dst.resolve():
            dst.write_text(svg)
        if "出典" not in a.caption:
            sys.exit("❌ 직접 만든 그림의 caption에 데이터 출처(「出典：…」)가 없음 (rules/blog-publish.md)")
        items.append({**base, "kind": "diagram", "src": f"img/{dst.name}", "license": "編集部作成", "credit": "編集部"})
    elif a.cmd == "add-usgov":
        host = urlparse(a.page).netloc.lower()
        if not any(host == d or host.endswith("." + d) for d in US_FEDERAL):
            sys.exit(f"❌ {host}는 미국 연방 기관 목록에 없음 — 주 정부·민간 사이트는 퍼블릭 도메인이 아니다")
        items.append({**base, "kind": "usgov", "src": a.src, "page": a.page, "credit": a.agency,
                      "license": "Public domain (17 U.S.C. §105)", "license_url": "https://www.copyright.gov/title17/92chap1.html#105"})
    save(p, items)
    print(f"등록 {len(items)}번 — publish/{a.slug}/images.json")


if __name__ == "__main__":
    main()
