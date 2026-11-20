#!/usr/bin/env python3
"""blog-topic: 회사 블로그의 기존 글 목록(제목·메타 설명)을 만든다. 1키워드 1글 점검용.

- 사이트맵(https://atatakaidigital.com/sitemap.xml)에서 /ja/blog/<slug>를 찾고, 각 글의 <title>과
  meta description을 가져온다
- 이미 목록에 있는 글은 다시 가져오지 않는다 (--refresh로 전부 다시). 동시 접속 2, 요청 사이 0.3초
- 사이트맵의 lastmod(마지막 수정일)는 매번 갱신한다 → existing_posts.stale.txt에 오래된 순 목록 (개편 후보 찾기용)
- Python 표준 라이브러리 + curl만 쓴다

사용법:
  python3 -I list_posts.py --out topics/existing_posts.json [--refresh]
"""
import argparse
import concurrent.futures as cf
import html
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SITEMAP = "https://atatakaidigital.com/sitemap.xml"
PREFIX = "https://atatakaidigital.com/ja/blog/"
CATEGORY_SLUGS = {"howtoai", "dev", "security", "ai", "news", "tag", "author"}
UA = "Mozilla/5.0 (compatible; BlogAgentTopic/1.0)"
TIMEOUT = 15
SITE_SUFFIX = re.compile(r"\s*[—|-]\s*あたたかいデジタル\s*$")


def fetch(url):
    p = subprocess.run(["curl", "-sSL", "--fail", "--compressed", "--max-time", str(TIMEOUT),
                        "-A", UA, "--", url], capture_output=True, timeout=TIMEOUT + 5)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace").strip()[:120] or f"curl exit {p.returncode}")
    return p.stdout.decode("utf-8", "replace")


def meta(page):
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    d = re.search(r'<meta name="description" content="([^"]*)"', page)
    title = SITE_SUFFIX.sub("", html.unescape(t.group(1)).strip()) if t else ""
    return title, html.unescape(d.group(1)).strip() if d else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    old = {}
    if out.exists() and not a.refresh:
        old = {p["slug"]: p for p in json.loads(out.read_text(encoding="utf-8")).get("posts", [])}

    sm = fetch(SITEMAP)
    urls = []
    for block in re.findall(r"<url>(.*?)</url>", sm, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        if not loc or not loc.group(1).startswith(PREFIX):
            continue
        slug = loc.group(1)[len(PREFIX):].strip("/")
        if not slug or "/" in slug or slug in CATEGORY_SLUGS:
            continue
        lm = re.search(r"<lastmod>(.*?)</lastmod>", block)
        urls.append((slug, loc.group(1), lm.group(1) if lm else ""))

    todo = [u for u in urls if u[0] not in old or not old[u[0]].get("title")]
    errors = []

    def run(u):
        slug, url, lastmod = u
        time.sleep(0.3)
        try:
            title, desc = meta(fetch(url))
            return {"slug": slug, "url": url, "lastmod": lastmod, "title": title, "description": desc}
        except Exception as e:  # noqa: BLE001
            errors.append(f"{slug}: {type(e).__name__}")
            return {"slug": slug, "url": url, "lastmod": lastmod, "title": "", "description": ""}

    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        for r in ex.map(run, todo):
            old[r["slug"]] = r
    for slug, _, lastmod in urls:  # 수정일은 이미 있는 글도 갱신
        if slug in old:
            old[slug]["lastmod"] = lastmod

    live = {u[0] for u in urls}
    posts = sorted((p for s, p in old.items() if s in live), key=lambda p: p["slug"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "updated_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00"),
        "source": SITEMAP,
        "_note": "회사 블로그 공개 글의 제목·메타 설명. 1키워드 1글 점검용",
        "posts": posts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"posts={len(posts)} fetched={len(todo)} errors={len(errors)}")
    for e in errors:
        print("  실패:", e)
    # 한 줄 목록 (컨텍스트 절약용)
    lines = [f"{p['slug']}\t{p['title']}" for p in posts]
    out.with_suffix(".titles.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 오래 고치지 않은 순 (개편 후보 찾기용)
    stale = sorted(posts, key=lambda p: p.get("lastmod") or "")
    out.with_suffix(".stale.txt").write_text(
        "\n".join(f"{(p.get('lastmod') or '-')[:10]}\t{p['slug']}\t{p['title']}" for p in stale) + "\n",
        encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
