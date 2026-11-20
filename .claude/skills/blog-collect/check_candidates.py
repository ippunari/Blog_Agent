#!/usr/bin/env python3
"""blog-collect: 후보 파일 점검.

1. 머리(front matter)와 후보마다 필수 항목이 다 있는지
2. 파일 안의 URL이 모두 실제로 수집한 데이터(fetch.json) 또는 검색 결과 URL 목록에 있는지
   (URL을 짐작해서 쓰는 실수를 막는다)

사용법:
  python3 -I check_candidates.py candidates/2026-11-19-pm.md --fetch "$SP/fetch.json" \
      [--search-urls "$SP/search_urls.txt"]
종료 코드 0 = 통과, 1 = 문제 있음
"""
import argparse
import json
import re
import sys
from pathlib import Path

FRONT = ["collected_at", "slot", "range_from", "counts"]
FIELDS = ["수집 일시", "언어", "한국어 요약", "원문 URL", "출처명", "등급", "1차 출처",
          "발표 일시", "주제 축", "예상 글 종류", "일본어 보도", "참고 링크"]
GRADES = {"A", "B", "C"}
AXES = {"AI", "보안", "개발"}
TYPES = {"AI 속보", "AI 사용법", "AI 업무 활용", "AI 도입 가이드", "보안 사고 해설",
         "보안 대책 가이드", "개발 발주·견적 가이드"}
SENT_END = re.compile(r"[.。!?！？](?=\s|$)")
HANGUL = re.compile(r"[가-힣]")
URL_RE = re.compile(r"https?://[^\s)|]+")


def norm(u):
    return re.split(r"[?&]utm_", u)[0].rstrip("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--fetch", required=True)
    ap.add_argument("--search-urls")
    a = ap.parse_args()

    text = Path(a.file).read_text(encoding="utf-8")
    problems = []

    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        problems.append("머리(--- ... ---)가 없음")
    else:
        for k in FRONT:
            if not re.search(rf"^{k}:", m.group(1), re.M):
                problems.append(f"머리에 {k} 없음")

    blocks = re.split(r"^### (C\d+) ", text, flags=re.M)
    cands = list(zip(blocks[1::2], blocks[2::2]))
    if not cands:
        problems.append("후보(### C01 ...)가 없음")
    for cid, body in cands:
        body = body.split("\n## ")[0]
        vals = dict(re.findall(r"^- ([^:：]+): (.*)$", body, re.M))
        for f in FIELDS:
            if not vals.get(f, "").strip():
                problems.append(f"{cid}: {f} 없음")
        if vals.get("등급") and vals["등급"].strip() not in GRADES:
            problems.append(f"{cid}: 등급 '{vals['등급']}' (A/B/C만, D는 제외)")
        if vals.get("주제 축") and vals["주제 축"].strip() not in AXES:
            problems.append(f"{cid}: 주제 축 '{vals['주제 축']}'")
        if vals.get("예상 글 종류") and vals["예상 글 종류"].strip() not in TYPES:
            problems.append(f"{cid}: 예상 글 종류 '{vals['예상 글 종류']}'")
        summ = vals.get("한국어 요약", "")
        if len(SENT_END.findall(summ)) > 2:
            problems.append(f"{cid}: 한국어 요약이 2문장을 넘음")
        if summ and not HANGUL.search(summ):
            problems.append(f"{cid}: 한국어 요약이 한국어가 아님")

    fetched = json.loads(Path(a.fetch).read_text(encoding="utf-8"))
    known = {norm(i["url"]) for i in fetched["items"]}
    # Google 트렌드 급상승의 관련 뉴스 URL (「검색 트렌드」 절, D43)
    known |= {norm(n["url"]) for t in fetched.get("trends", []) for n in t.get("news", []) if n.get("url")}
    if a.search_urls and Path(a.search_urls).exists():
        known |= {norm(l.strip()) for l in Path(a.search_urls).read_text(encoding="utf-8").splitlines()
                  if l.strip().startswith("http")}
    for u in sorted(set(URL_RE.findall(text))):
        if norm(u) not in known:
            problems.append(f"수집 데이터에 없는 URL: {u}")

    print(f"후보 {len(cands)}건 점검")
    for p in problems:
        print("  ✗", p)
    print("통과" if not problems else f"문제 {len(problems)}건")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
