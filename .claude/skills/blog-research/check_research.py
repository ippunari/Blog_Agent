#!/usr/bin/env python3
"""blog-research: 조사 노트 점검.

1. 머리(front matter)와 필수 절이 다 있는지
2. 핵심 사실표의 행마다: S번호, 등급(A·B·C), 날짜 형식, URL이 실제로 가져온 페이지에 있는지
3. **원문 문장이 가져온 페이지 텍스트에 실제로 있는지** (공백 무시, 「…」로 나눈 조각마다)
   → 원문을 지어내거나 잘못 옮기는 실수를 막는다 (사실 대조의 증거)
4. 수치·날짜가 든 사실이 C등급이면 오류 (수치·날짜·인용은 A·B만). A등급이 없으면 경고
5. 일반 글은 「상위 글 분량」(경쟁 글 본문 글자 수 3개 이상 + 중앙값, D47)

사용법:
  python3 -I check_research.py research/<slug>.md --pages "$SP/pages" [--search-urls "$SP/research_search_urls.txt"]
종료 코드 0 = 통과, 1 = 문제 있음
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

FRONT = ["slug", "brief", "route", "type", "trial", "started_at", "finished_at"]
SECTIONS = ["요약", "대표 한마디", "핵심 사실", "수치표", "상위 10개 글 유형", "일본어 경쟁 글 분석",
            "짧은 인용 후보", "아직 확인하지 못한 사항", "직접 써 본 결과", "다른 사람의 검증"]
LINKS_MARK = "=== LINKS"
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}|-)$")
URL_RE = re.compile(r"https?://[^\s)|<>」]+")
DIGIT = re.compile(r"[0-9０-９]")
ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*")


def norm_url(u):
    return re.split(r"[?#]", u.strip())[0].rstrip("/")


def norm_text(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", "", s)


def load_pages(d):
    d = Path(d)
    pages = {}
    idx = json.loads((d / "index.json").read_text())
    for e in idx:
        if not e.get("file"):
            continue
        body = (d / e["file"]).read_text().split(LINKS_MARK)[0]
        body = body.split("\n\n", 1)[1] if "\n\n" in body else body
        t = norm_text(body)
        for u in (e["url"], e.get("final_url") or e["url"]):
            pages[norm_url(u)] = t
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--pages", required=True)
    ap.add_argument("--search-urls")
    a = ap.parse_args()

    text = Path(a.file).read_text()
    errs, warns = [], []

    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        errs.append("머리(front matter)가 없음")
        front = ""
    else:
        front = m.group(1)
    for k in FRONT:
        if not re.search(rf"^{k}:\s*\S", front, re.M):
            errs.append(f"머리에 `{k}:` 없음")
    route = re.search(r"^route:\s*(\S+)", front, re.M)
    route = route.group(1) if route else ""

    heads = re.findall(r"^##\s+(.+?)\s*$", text, re.M)
    for s in SECTIONS:
        if not any(h.startswith(s) for h in heads):
            errs.append(f"절 「## {s}」 없음")

    pages = load_pages(a.pages)
    search = set()
    if a.search_urls and Path(a.search_urls).exists():
        search = {norm_url(u) for u in Path(a.search_urls).read_text().split() if u.startswith("http")}

    # 핵심 사실표
    sec = re.search(r"^## 핵심 사실\s*\n(.*?)(?=^## )", text, re.S | re.M)
    rows = []
    if sec:
        for ln in sec.group(1).splitlines():
            if ln.startswith("|") and not re.match(r"^\|\s*(ID|-{2,})", ln):
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                rows.append(cells)
    if not rows:
        errs.append("핵심 사실표에 행이 없음")
    ids = set()
    has_a = False
    for c in rows:
        if len(c) != 8:
            errs.append(f"칸 수가 8이 아님 ({len(c)}): {c[0] if c else '?'} — 원문 문장 속 「|」는 「／」로 바꾼다")
            continue
        sid, fact, orig, src, url, grade, pub, chk = c
        tag = sid or "?"
        if not re.match(r"^S\d+$", sid):
            errs.append(f"{tag}: ID는 S번호")
        if sid in ids:
            errs.append(f"{tag}: ID 중복")
        ids.add(sid)
        if grade not in {"A", "B", "C"}:
            errs.append(f"{tag}: 등급은 A·B·C (D는 쓰지 않음)")
        if grade == "A":
            has_a = True
        if grade == "C" and DIGIT.search(fact):
            errs.append(f"{tag}: 수치·날짜가 든 사실은 A·B등급만 (C는 단서로만)")
        if not DATE.match(pub):
            errs.append(f"{tag}: 발표일 형식 YYYY-MM-DD 또는 -")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", chk):
            errs.append(f"{tag}: 확인일 형식 YYYY-MM-DD")
        if not fact or not src:
            errs.append(f"{tag}: 사실·출처명이 비어 있음")
        um = URL_RE.search(url)
        if not um:
            errs.append(f"{tag}: URL 없음")
            continue
        u = norm_url(um.group(0))
        if u not in pages:
            where = "검색 결과에만 있음" if u in search else "가져온 페이지에 없음"
            errs.append(f"{tag}: URL이 fetch_page.py로 가져온 페이지가 아님 ({where}) — 원문을 확인할 수 없다: {u}")
            continue
        if not orig or orig in {"-", "없음"}:
            errs.append(f"{tag}: 원문 문장이 비어 있음")
            continue
        body = pages[u]
        for frag in ELLIPSIS.split(orig):
            f = norm_text(frag)
            if f and f not in body:
                errs.append(f"{tag}: 원문 문장이 페이지에 없음 → 「{frag[:50]}」 (그대로 옮겼는지 확인)")

    if rows and not has_a:
        warns.append("A등급 출처가 하나도 없음 — 주장마다 A등급 1개 이상 (1차 출처를 찾아간다)")

    # 본문 다른 절의 S번호 참조가 표에 있는지
    for ref in sorted(set(re.findall(r"\bS\d+\b", text)) - ids):
        warns.append(f"표에 없는 사실 번호를 참조함: {ref}")

    # 속보가 아니면 경쟁 글 분석이 있어야 함
    comp = re.search(r"^## 일본어 경쟁 글 분석\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if route == "일반" and comp and (len(URL_RE.findall(comp.group(1))) < 3):
        errs.append("일반 글: 일본어 경쟁 글 분석에 URL 3개 이상 (상위 3~5개)")
    if route == "일반" and "차별 포인트" not in text:
        errs.append("일반 글: 「차별 포인트」 없음")
    # 상위 글 분량 (D47, D58): 모든 글 — 같은 유형 URL·글자 수 3개 이상 + 기준 유형 + 중앙값, 우리 사이트 글 제외
    vol = re.search(r"^## 상위 글 분량[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if True:
        if not vol:
            errs.append("「## 상위 글 분량」 절 없음 — body_chars.py로 같은 유형 상위 글 본문 글자 수와 중앙값 (D47, D58: 속보도)")
        else:
            rows_v = [l for l in vol.group(1).splitlines() if URL_RE.search(l) and re.search(r"\|\s*\d+\s*\|", l)]
            if len(rows_v) < 3:
                errs.append("「상위 글 분량」: URL | 글자 수 행이 3개 이상이어야 함")
            if not re.search(r"중앙값:\s*\d+", vol.group(1)):
                errs.append("「상위 글 분량」: 「중앙값: n자」 줄 없음")
            if not re.search(r"기준 유형:", vol.group(1)):
                errs.append("「상위 글 분량」: 「기준 유형: 뉴스 / 해설·가이드」 줄 없음 (D58)")
            if "atatakaidigital.com" in vol.group(1):
                errs.append("「상위 글 분량」에 우리 사이트 글이 있음 — 기준에서 뺀다 (D58)")

    print(f"사실 {len(rows)}행 / 가져온 페이지 {len(set(pages.values()))}개")
    for w in warns:
        print("경고:", w)
    for e in errs:
        print("오류:", e)
    print("통과" if not errs else f"문제 {len(errs)}개")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
