#!/usr/bin/env python3
"""blog-topic: 주제 후보 파일 점검.

1. 머리(front matter)와 후보마다 필수 항목
2. 점수 1~5 정수, 총점 = 가중합 재계산과 일치 (전환 35 / 자료부족 20 / 수요 20 / 경험 15 / 수명 10)
3. 서브 키워드 3~5개, 속보는 마감 필수
4. 순위표: 아침·저녁 모두 속보 AI / 속보 보안·개발 / 깊이 새 글 (D72).
   표마다 최대 5개, 축·경로 일치, 총점 내림차순, 상세와 값 일치
6. 추천 ○: 표마다 1개 (속보는 한쪽 표가 비면 다른 쪽 2개). 고른 뒤(☑ 있음)에는 경고만
7. 「실습」 값, ○ 행은 「추천」 이유 필수, 개편 표는 「[更新]」 가제목만, 「이월」 칸 형식
5. URL이 모두 후보 파일·검색 결과 URL 목록·기존 글 목록에 있는지 (짐작한 URL 방지)

사용법:
  python3 -I check_topics.py topics/2026-11-19-pm.md \
      --existing topics/existing_posts.json [--search-urls "$SP/topic_search_urls.txt"]
종료 코드 0 = 통과, 1 = 문제 있음 (경고만 있으면 0)
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

WEIGHTS = {"전환": 25, "자료부족": 20, "수요": 35, "경험": 10, "수명": 10}   # 키워드(수요) 우선 (D72)
FRONT = ["made_at", "slot", "candidates", "counts"]
FIELDS = ["경로", "원 후보", "주제 축", "글 종류", "가제목", "메인 키워드", "서브 키워드", "키워드 근거",
          "점수", "점수 근거", "일본어 상위 결과", "1키워드1글", "마감", "원문 URL", "실습"]
TRIALS = {"에이전트 가능", "사람 필요", "해당 없음"}
MARKS = {"☐", "○", "☑"}
# (표 제목, 경로, AI 축이어야 하나(None=상관없음), 개편 표인가)
# 아침·저녁 같은 3표: 속보 AI 1 · 속보 보안·개발 1 · 깊이 새 글 1 (개편 없음, D72)
TABLES_AM = [("## 속보 순위 — AI", "속보", True, False), ("## 속보 순위 — 보안·개발", "속보", False, False),
             ("## 깊이 새 글 순위", "일반", None, False)]
TABLES_PM = TABLES_AM
ROUTES = {"속보", "일반"}
AXES = {"AI", "보안", "개발"}
TYPES = {"AI 속보", "AI 사용법", "AI 업무 활용", "AI 도입 가이드", "보안 사고 해설",
         "보안 대책 가이드", "개발 발주·견적 가이드"}
URL_RE = re.compile(r"https?://[^\s)|<>」]+")
SCORE_RE = re.compile(r"전환\s*(\d)\s*/\s*자료부족\s*(\d)\s*/\s*수요\s*(\d)\s*/\s*경험\s*(\d)\s*/\s*수명\s*(\d)"
                      r"\s*→\s*총점\s*(\d+)")
JA = re.compile(r"[぀-ヿ一-鿿]")


def norm(u):
    return re.split(r"[?&]utm_", u.rstrip(".,、。"))[0].rstrip("/")


def total(s):
    return round(sum(s[k] * w for k, w in WEIGHTS.items()) / 5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--existing", required=True)
    ap.add_argument("--search-urls")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8")
    errs, warns = [], []

    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    front = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M)) if m else {}
    for k in FRONT:
        if k not in front:
            errs.append(f"머리: {k} 없음")

    # 허용 URL 모으기
    known = set()
    for c in re.findall(r"candidates/[\w.-]+\.md", front.get("candidates", "")):
        p = Path(c)
        if p.exists():
            known |= {norm(u) for u in URL_RE.findall(p.read_text(encoding="utf-8"))}
        else:
            errs.append(f"머리: 후보 파일 {c} 없음")
    ex = json.loads(Path(a.existing).read_text(encoding="utf-8"))
    known |= {norm(p["url"]) for p in ex.get("posts", [])}
    known.add(norm("https://atatakaidigital.com/ja/blog"))
    if a.search_urls and Path(a.search_urls).exists():
        known |= {norm(l.strip()) for l in Path(a.search_urls).read_text(encoding="utf-8").splitlines() if l.strip()}

    # 순위표에서 이월 후보 (이월 칸이 「-」가 아닌 행)
    carried = set()
    for ln in text.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.startswith("|") and len(cells) >= 10 and re.match(r"^T\d+$", cells[2]) and cells[-1] not in ("-", ""):
            carried.add(cells[2])

    # 상세
    details = {}
    for sec in re.split(r"\n(?=### T\d+)", text)[1:]:
        head = sec.splitlines()[0]
        tid = re.match(r"### (T\d+)", head).group(1)
        f = dict(re.findall(r"^- ([^:\n]+?):\s*(.*)$", sec.split("\n## ")[0], re.M))
        for k in FIELDS:
            if not f.get(k, "").strip():
                errs.append(f"{tid}: {k} 없음")
        if f.get("경로") and f["경로"] not in ROUTES:
            errs.append(f"{tid}: 경로 값 '{f['경로']}'")
        if f.get("주제 축") and f["주제 축"] not in AXES:
            errs.append(f"{tid}: 주제 축 값 '{f['주제 축']}'")
        if f.get("글 종류") and f["글 종류"] not in TYPES:
            errs.append(f"{tid}: 글 종류 값 '{f['글 종류']}'")
        # 상위 결과 구성 (이길 여지 판단, D43). 새 후보는 필수, 이월 후보(예전 형식)는 경고만
        comp = f.get("상위 구성", "").strip()
        if not comp:
            (warns if tid in carried else errs).append(
                f"{tid}: 상위 구성 없음 — 「상위 구성: 대형 n / 전문 n / 작은 사이트 n (작은: 도메인…)」")
        elif not re.search(r"대형\s*\d+\s*/\s*전문\s*\d+\s*/\s*작은 사이트\s*\d+", comp):
            errs.append(f"{tid}: 상위 구성 형식 「대형 n / 전문 n / 작은 사이트 n」")
        # 깊이 글은 실제 검색 근거가 있는 키워드만 (D72): 「추정」 금지
        if f.get("경로") == "일반" and "추정" in f.get("키워드 근거", ""):
            errs.append(f"{tid}: 깊이 글 키워드 근거에 「추정」 — 자동완성·知恵袋·트렌드에서 확인한 키워드만 (D72)")
        subs = [s for s in re.split(r"\s+/\s+", f.get("서브 키워드", "")) if s.strip()]
        if not 3 <= len(subs) <= 5:
            errs.append(f"{tid}: 서브 키워드 {len(subs)}개 (3~5개)")
        mk = f.get("메인 키워드", "")
        if mk and not JA.search(mk):
            warns.append(f"{tid}: 메인 키워드에 일본어가 없음 '{mk}'")
        tt = f.get("가제목", "")
        if tt and not JA.search(tt):
            errs.append(f"{tid}: 가제목은 일본어로")
        if tt and mk and mk.split()[0].lower() not in tt.lower():
            warns.append(f"{tid}: 가제목에 메인 키워드 첫 단어 '{mk.split()[0]}'가 없음")
        if tt and not 15 <= len(tt) <= 40:
            warns.append(f"{tid}: 가제목 {len(tt)}자 (최종 제목은 전각 28~35자)")
        sm = SCORE_RE.search(f.get("점수", ""))
        tot = None
        if not sm:
            errs.append(f"{tid}: 점수 형식 「전환 n / 자료부족 n / 수요 n / 경험 n / 수명 n → 총점 N」")
        else:
            s = dict(zip(WEIGHTS, map(int, sm.groups()[:5])))
            if any(not 1 <= v <= 5 for v in s.values()):
                errs.append(f"{tid}: 점수는 1~5")
            tot = total(s)
            if tot != int(sm.group(6)):
                errs.append(f"{tid}: 총점 {sm.group(6)} ≠ 계산값 {tot}")
        if f.get("경로") == "속보" and not re.search(r"\d{4}-\d{2}-\d{2}", f.get("마감", "")):
            errs.append(f"{tid}: 속보는 마감 날짜 필요 (발표 + 72시간)")
        if f.get("실습") and not any(f["실습"].startswith(t) for t in TRIALS):
            errs.append(f"{tid}: 실습 값 '{f['실습']}' (에이전트 가능 / 사람 필요 / 해당 없음 으로 시작)")
        details[tid] = {"axis": f.get("주제 축"), "route": f.get("경로"), "total": tot, "title": tt,
                        "type": f.get("글 종류"), "rec": f.get("추천", "").strip(),
                        "trial": f.get("실습", "")}

    # 순위표
    tables = TABLES_PM if front.get("slot") == "pm" else TABLES_AM
    picked = "☑" in text
    marks = {}
    for title, route, ai, upd in tables:
        mm = re.search(re.escape(title) + r"[^\n]*\n((?:\|.*\n)+)", text)
        if not mm:
            errs.append(f"순위표 없음: {title}")
            continue
        rows = [r for r in mm.group(1).splitlines()[2:] if r.strip()]
        if len(rows) > 5:
            errs.append(f"{title}: {len(rows)}개 (최대 5개)")
        prev = 999
        marks[title] = 0
        for r in rows:
            c = [x.strip() for x in r.strip().strip("|").split("|")]
            if len(c) < 10:
                errs.append(f"{title}: 칸 수 부족(10칸: …1키워드1글 | 이월) '{r[:40]}'")
                continue
            mark, tid, tot, carry = c[0], c[2], c[6], c[9]
            if mark not in MARKS:
                errs.append(f"{title}: {tid} 선택 값 '{mark}' (☐ ○ ☑)")
            if mark in ("○", "☑"):
                marks[title] += 1
            if carry != "-" and not re.match(r"topics/[\w.-]+\.md T\d+$", carry):
                errs.append(f"{title}: {tid} 이월 칸 형식 '{carry}' (- 또는 'topics/파일.md T03')")
            d = details.get(tid)
            if not d:
                errs.append(f"{title}: {tid} 상세 없음")
                continue
            if mark == "○" and not d["rec"]:
                errs.append(f"{title}: {tid}는 ○인데 상세에 「추천:」 이유가 없음")
            if d["route"] != route:
                errs.append(f"{title}: {tid}의 경로는 {d['route']}")
            if ai is not None and (d["axis"] == "AI") != ai:
                errs.append(f"{title}: {tid}의 주제 축은 {d['axis']}")
            if upd != d["title"].startswith("[更新]"):
                errs.append(f"{title}: {tid} — 개편 표에는 「[更新]」 글만, 새 글 표에는 새 글만")
            if str(d["total"]) != tot:
                errs.append(f"{title}: {tid} 총점 {tot} ≠ 상세 {d['total']}")
            if c[3] != d["title"]:
                errs.append(f"{title}: {tid} 가제목이 상세와 다름")
            if tot.isdigit():
                if int(tot) > prev:
                    errs.append(f"{title}: 총점 내림차순이 아님 ({tid})")
                prev = int(tot)
        marks[title] = (marks[title], len(rows))
    # 깊이 새 글 몫 (D72): 화·금 저녁 = 개발, 그 밖(주 8회) = AI. 후보가 없을 수 있어 경고
    dm = re.search(r"(\d{4})-(\d{2})-(\d{2})-(am|pm)", Path(a.file).name)
    if dm:
        wd = datetime.date(*map(int, dm.groups()[:3])).weekday()
        want_axis = "개발" if (dm.group(4) == "pm" and wd in (1, 4)) else "AI"
        mm = re.search(r"## 깊이 새 글 순위[^\n]*\n((?:\|.*\n)+)", text)
        for r in (mm.group(1).splitlines()[2:] if mm else []):
            c = [x.strip() for x in r.strip().strip("|").split("|")]
            d = details.get(c[2]) if len(c) > 2 else None
            if d and d["axis"] != want_axis:
                warns.append(f"깊이 새 글 표({want_axis} 몫)에 {d['axis']} 후보 {c[2]} — {want_axis} 후보가 없거나 검색 수요 5일 때만 (추천에 이유)")
    # 추천 ○ 개수: 표마다 1개, 속보는 한쪽이 비면 다른 쪽 2개
    names = [t[0] for t in tables]
    for i, title in enumerate(names):
        if title not in marks:
            continue
        n, rows = marks[title]
        want = 1 if rows else 0
        if i < 2:
            other = marks.get(names[1 - i], (0, 0))
            if rows and other[1] == 0:
                want = 2 if rows >= 2 else 1
        if n != want:
            msg = f"{title}: 추천 ○ {n}개 (기대 {want}개)"
            (warns if picked else errs).append(msg)

    # URL
    for u in sorted(set(URL_RE.findall(text))):
        if norm(u) not in known:
            errs.append(f"수집·검색 데이터에 없는 URL: {u}")

    for w in warns:
        print("경고:", w)
    for e in errs:
        print("문제:", e)
    print("통과" if not errs else f"문제 {len(errs)}건")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
