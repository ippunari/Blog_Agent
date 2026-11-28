#!/usr/bin/env python3
"""blog-collect: 후보 파일 점검.

1. 머리(front matter)와 후보마다 필수 항목이 다 있는지
2. 파일 안의 URL이 모두 실제로 수집한 데이터(fetch.json) 또는 검색 결과 URL 목록에 있는지
   (URL을 짐작해서 쓰는 실수를 막는다)
3. 머리 counts가 본문과 맞는지 (D82)
4. 검색 출처를 하나도 빼지 않고 검색했는지 — search_done.txt (D82, last30days의 source_status)
5. 언어별 건수 줄이 본문과 맞는지 (D82, 정보용 — 0건이어도 된다)
   축별·언어별 건수 상한·하한은 점검하지 않는다 — 고르는 기준은 SKILL.md 5장 5번 「중요한 순서」 (D84)

사용법:
  python3 -I check_candidates.py candidates/2026-11-19-pm.md --fetch "$SP/fetch.json" \
      --search-urls "$SP/search_urls.txt" --search-done "$SP/search_done.txt"
종료 코드 0 = 통과, 1 = 문제 있음
"""
import argparse
import json
import re
import sys
from pathlib import Path

FRONT = ["collected_at", "slot", "range_from", "counts"]
FIELDS = ["수집 일시", "언어", "한국어 요약", "원문 URL", "출처명", "등급", "1차 출처",
          "발표 일시", "주제 축", "예상 글 종류", "일본어 보도", "참고 링크", "반응"]
GRADES = {"A", "B", "C"}
AXES = {"AI", "보안", "개발"}
TYPES = {"AI 속보", "AI 사용법", "AI 업무 활용", "AI 도입 가이드", "보안 사고 해설",
         "보안 대책 가이드", "개발 발주·견적 가이드"}
SENT_END = re.compile(r"[.。!?！？](?=\s|$)")
HANGUL = re.compile(r"[가-힣]")
URL_RE = re.compile(r"https?://[^\s)|]+")
LANGS = ["en", "ko", "ja", "zh"]


def norm(u):
    return re.split(r"[?&]utm_", u)[0].rstrip("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--fetch", required=True)
    ap.add_argument("--search-urls")
    ap.add_argument("--search-done", help="검색한 출처 기록 「id | 결과 수」 또는 「id | 실패: 이유」 (D82)")
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

    front = m.group(1) if m else ""
    blocks = re.split(r"^### (C\d+) ", text, flags=re.M)
    cands = list(zip(blocks[1::2], blocks[2::2]))
    if not cands:
        problems.append("후보(### C01 ...)가 없음")
    tally = []
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
        # D94: B·C 대표 출처인데 1차 출처가 있으면 발표 일시는 1차 출처 날짜로
        if (vals.get("등급", "").strip() in ("B", "C") and vals.get("1차 출처", "").strip().startswith("있음")
                and "1차 출처" not in vals.get("발표 일시", "")):
            problems.append(f"{cid}: 1차 출처가 있으면 발표 일시는 1차 출처의 공표 일시 + 「(JST, 1차 출처)」 "
                            f"— 시각이 없으면 「YYYY-MM-DD (1차 출처, 시각 미공개)」 (D94)")
        summ = vals.get("한국어 요약", "")
        if len(SENT_END.findall(summ)) > 2:
            problems.append(f"{cid}: 한국어 요약이 2문장을 넘음")
        if summ and not HANGUL.search(summ):
            problems.append(f"{cid}: 한국어 요약이 한국어가 아님")
        tally.append(vals)

    # 3. counts — 머리 숫자를 본문에서 다시 센다
    axes = {ax: sum(1 for v in tally if v.get("주제 축", "").strip() == ax) for ax in AXES}
    qsec = re.search(r"^## 질문 입구\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    q_rows = [l for l in (qsec.group(1).splitlines() if qsec else [])
              if l.startswith("|") and not re.match(r"^\|[\s|:-]+\|$", l)][1:]  # 머리줄 빼고
    actual = {"total": len(cands), **axes, "questions": len(q_rows)}
    cm = re.search(r"^counts:\s*\{(.*)\}", front, re.M)
    if cm:
        claimed = {k: int(v) for k, v in re.findall(r"([\w가-힣]+):\s*(\d+)", cm.group(1))}
        for k, v in actual.items():
            if claimed.get(k) != v:
                problems.append(f"counts {k}: 머리 {claimed.get(k)} ≠ 본문 {v}")

    # 5. 언어별 줄 — 본문과 맞는지만 본다 (D84: 0건이어도 됨)
    langs = {lg: sum(1 for v in tally if v.get("언어", "").strip() == lg) for lg in LANGS}
    lm = re.search(r"^- 언어별: (.*)$", text, re.M)
    if not lm:
        problems.append("「출처 수집 결과」에 「- 언어별: en N / ko N / ja N / zh N」 줄 없음")
    else:
        for lg, n in langs.items():
            if not re.search(rf"\b{lg} {n}\b", lm.group(1)):
                problems.append(f"언어별 줄의 {lg}가 본문({n}건)과 다름")

    fetched = json.loads(Path(a.fetch).read_text(encoding="utf-8"))
    known = {norm(i["url"]) for i in fetched["items"]}
    # Google 트렌드 급상승의 관련 뉴스 URL (「검색 트렌드」 절, D43)
    known |= {norm(n["url"]) for t in fetched.get("trends", []) for n in t.get("news", []) if n.get("url")}
    if a.search_urls and Path(a.search_urls).exists():
        known |= {norm(l.strip()) for l in Path(a.search_urls).read_text(encoding="utf-8").splitlines()
                  if l.strip().startswith("http")}
    # 4. 검색 출처를 다 검색했는지
    want = [x["id"] for x in fetched.get("search_sources", [])]
    if want:
        done = set()
        if a.search_done and Path(a.search_done).exists():
            done = {l.split("|")[0].strip() for l in Path(a.search_done).read_text(encoding="utf-8").splitlines()
                    if "|" in l}
        else:
            problems.append("search_done.txt 없음 — 검색한 출처마다 「id | 결과 수」를 적는다")
        missing = [i for i in want if i not in done]
        if done and missing:
            problems.append(f"검색 안 한 출처 {len(missing)}개: {', '.join(missing)}")

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
