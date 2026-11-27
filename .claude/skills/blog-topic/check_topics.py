#!/usr/bin/env python3
"""blog-topic: 주제 후보 파일 점검.

1. 머리(front matter)와 후보마다 필수 항목
2. 점수 1~5 정수, 총점 = 가중합 재계산과 일치 (전환 25 / 자료부족 20 / 수요 35 / 경험 10 / 수명 10, D72)
8. 키워드 (D80): 「상위 구성 검색어」 = 메인 키워드 / 속보는 「사건어」가 있고 메인 키워드가 사건어로 시작 /
   깊이 글이 작은 사이트 0개 + 자료 판정 3 이하(이길 여지 문턱)인데 ○·☑면 오류 / 수요 5인데 질문형 3개 미만·트렌드 없음이면 경고
3. 서브 키워드 3~5개, 속보는 마감 필수
4. 순위표: 아침·저녁 모두 속보 / 깊이 새 글 (D72, D86).
   표마다 최대 5개, 축·경로 일치, 총점 내림차순, 상세와 값 일치
   D87: 메인 키워드가 「키워드 근거」에 그대로 있는가(깊이 오류·속보 경고) / 서브 키워드는 일본어, 질문형 깊이 3개·속보 2개 이상 /
   사건어가 회사·서비스 이름(+일반어)뿐이면 경고 / 수요 점수가 질문형 수로 정한 상한(0→1, 1→2, 2→3, 3+→4, 5는 知恵袋 반복·트렌드)을 넘으면 오류
6. 추천 ○: 속보 2개(급한 보안이 있으면 급한 보안 1 + 그 밖 1, D86) · 깊이 1개. 고른 뒤(☑ 있음)에는 경고만
7. 「실습」 값, ○ 행은 「추천」 이유 필수, 새 글 표에 「[更新]」 없음, 「이월」 칸 형식
10. 마감 (D88): 속보 「마감」은 「YYYY-MM-DD HH:MM」이고 업무 시간(평일 9~18시) 안이어야 한다 (deadline.py로 계산) /
    ○ 속보는 made_at부터 마감까지 남은 업무 시간이 3시간 이상
11. 사건어 (D90): 「사건어 근거」에 원문 제목 / 사건어가 자동완성에 없어 메인에 못 넣으면 「사건어: … (메인에 없음)」 — 이때는
    「메인이 사건어로 시작」 검사를 건너뛰고, 가제목에 사건어가 있는지 본다 / 수요 5 반복 근거에 질문 입구·note·Q&A
9. 속보 표의 보안 축 후보는 「급한 보안: 예 — 근거」 필수 (D86 — 급하지 않은 보안은 순위표에 넣지 않는다)
5. URL이 모두 후보 파일·검색 결과 URL 목록·기존 글 목록에 있는지 (짐작한 URL 방지)

사용법:
  python3 -I check_topics.py topics/2026-11-19-pm.md \
      --existing topics/existing_posts.json [--search-urls "$SP/topic_search_urls.txt"]
종료 코드 0 = 통과, 1 = 문제 있음 (경고만 있으면 0)
"""
import argparse
import datetime
import importlib.util
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
# (표 제목, 경로, 추천 ○ 수)
# 아침·저녁 같은 2표: 속보 2 (AI·개발 중심, 급한 보안만 1편까지 끼움, D86) · 깊이 새 글 1 (개편 없음, D72)
TABLES = [("## 속보 순위", "속보", 2), ("## 깊이 새 글 순위", "일반", 1)]
ROUTES = {"속보", "일반"}
AXES = {"AI", "보안", "개발"}
TYPES = {"AI 속보", "AI 사용법", "AI 업무 활용", "AI 도입 가이드", "보안 사고 해설",
         "보안 대책 가이드", "개발 발주·견적 가이드"}
URL_RE = re.compile(r"https?://[^\s)|<>」]+")
SCORE_RE = re.compile(r"전환\s*(\d)\s*/\s*자료부족\s*(\d)\s*/\s*수요\s*(\d)\s*/\s*경험\s*(\d)\s*/\s*수명\s*(\d)"
                      r"\s*→\s*총점\s*(\d+)")
JA = re.compile(r"[぀-ヿ一-鿿]")
# 질문형 검색어 = 이 말이 들어간 일본어 검색어 (D87 — rules/blog-topic.md 「질문형의 뜻」과 같은 목록)
Q_TAILS = (
    "とは", "意味", "違い", "比較", "なぜ", "いつ", "どう", "？", "?",                       # 뜻·비교·질문 문장
    "方法", "やり方", "手順", "使い方", "コツ", "設定", "解除", "始め", "作り", "プロンプト",  # 방법 (〜方도, 아래 Q_KATA)
    "できない", "使えない", "されない", "表示されない", "原因", "エラー", "危険", "安全", "注意点", "禁止",
    "被害", "されたら", "対策", "確認", "対応",                                              # 문제·위험·대응
    "費用", "料金", "相場", "無料", "内訳", "見積", "補助金",                                 # 비용
    "例", "事例", "サンプル", "テンプレート", "チェックリスト", "ガイドライン", "ステップ", "流れ", "期間",  # 자료·진행
    "できること")
Q_KATA = re.compile(r"\S方(\s|$)")   # 消し方·書き方 같은 「〜方」
# 사건어가 이것(+ GENERIC_NOUNS)뿐이면 사건어가 아니다 — 제품명+버전·모델명·고유 기능명·회사+사고·CVE (D87)
GENERIC_NAMES = {"google", "chatgpt", "openai", "gemini", "claude", "anthropic", "copilot", "microsoft", "wordpress",
                 "php", "apple", "meta", "aws", "amazon", "生成ai", "ai"}
GENERIC_NOUNS = {"検索", "ai", "アプリ", "新機能", "機能", "アップデート", "脆弱性", "情報漏洩", "公式", "最新", "モデル"}


def is_question(k):
    return any(t in k for t in Q_TAILS) or bool(Q_KATA.search(k))


def demand_cap(q, basis):
    """질문형 서브 키워드 수 → 수요 상한 (D87). 5는 질문형 3+에 반복 근거 하나(D90): 知恵袋 2건+ /
    note·Q&A에 같은 질문 / 질문 입구에 같은 질문 2회+ / 트렌드 급상승"""
    if "트렌드" in basis:
        return 5
    ch = [int(n) for n in re.findall(r"知恵袋[^;／/]{0,20}?(\d+)\s*건", basis)]
    qi = [int(n) for n in re.findall(r"질문 입구[^;／/]{0,20}?(\d+)\s*회", basis)]
    repeat = (max(ch, default=0) >= 2 or max(qi, default=0) >= 2
              or bool(re.search(r"知恵袋[^;／/]{0,20}반복", basis))
              or bool(re.search(r"반복 근거[^;]{0,10}(note|Q&A)", basis)))
    if q >= 3:
        return 5 if repeat else 4
    return {2: 3, 1: 2}.get(q, 1)


_spec = importlib.util.spec_from_file_location("deadline", Path(__file__).resolve().parent / "deadline.py")
DL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DL)   # 마감 계산은 deadline.py 한 곳에서 (D88)
NOT_IN_MAIN = "(메인에 없음)"


def kw_norm(k):
    return re.sub(r"\s+", " ", k.replace("\u3000", " ")).strip().casefold()


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
        sm_small = re.search(r"작은 사이트\s*(\d+)", comp)
        small = int(sm_small.group(1)) if sm_small else None
        # D80: 상위 구성은 메인 키워드로 센다
        cq = f.get("상위 구성 검색어", "").strip()
        new = tid not in carried
        if not cq:
            (errs if new else warns).append(f"{tid}: 상위 구성 검색어 없음 — 메인 키워드로 검색해서 센다 (D80)")
        elif kw_norm(cq) != kw_norm(f.get("메인 키워드", "")):
            errs.append(f"{tid}: 상위 구성 검색어 「{cq}」 ≠ 메인 키워드 — 메인 키워드로 다시 센다 (D80)")
        # D80: 속보 메인 키워드 = 사건어로 시작
        if f.get("경로") == "속보":
            ev_raw = f.get("사건어", "").strip()
            not_in_main = NOT_IN_MAIN in ev_raw
            ev = ev_raw.replace(NOT_IN_MAIN, "").strip()
            if not ev:
                (errs if new else warns).append(f"{tid}: 속보는 「사건어:」(제품명·버전·사건명) 필요 (D80)")
            elif not_in_main:
                # D90: 사건어가 자동완성에 없어 메인 키워드에 못 넣었다 → 제목·첫 문단·「何が起きた？」에 넣는다
                if not all(w in kw_norm(f.get("가제목", "")) for w in kw_norm(ev).split()):
                    warns.append(f"{tid}: 사건어 「{ev}」가 메인에 없음 — 가제목에는 넣는다 (D90)")
            elif not kw_norm(f.get("메인 키워드", "")).startswith(kw_norm(ev)):
                errs.append(f"{tid}: 속보 메인 키워드는 사건어 「{ev}」로 시작 — 사건어가 자동완성에 없으면 "
                            f"「사건어: {ev} {NOT_IN_MAIN}」 (D80, D90)")
            # D90: 사건어는 원문에서 먼저 뽑는다
            if ev and "원문 제목" not in f.get("사건어 근거", ""):
                (errs if new else warns).append(f"{tid}: 「사건어 근거: 원문 제목 「…」」 필요 — 사건어는 원문의 고유한 말에서 (D90)")
            if ev:
                rest = [w for w in kw_norm(ev).split() if w not in GENERIC_NAMES and w not in GENERIC_NOUNS]
                if not rest and not re.search(r"\d", ev):
                    warns.append(f"{tid}: 사건어 「{ev}」가 회사·서비스 이름뿐 — 제품명+버전·모델명·고유 기능명·회사+사고·CVE로 (D87)")
        # D80: 이길 여지 문턱 (깊이 글) — 작은 사이트 0개 + 자료 판정 3 이하면 그 키워드로 추천하지 않는다
        jm = re.search(r"자료\s*(\d)\s*\+\s*경쟁\s*(\d)", f.get("점수 근거", ""))
        jaryo = int(jm.group(1)) if jm else None
        if f.get("경로") == "일반" and jm is None and new:
            errs.append(f"{tid}: 점수 근거에 「자료부족 n = (자료 n + 경쟁 n)÷2」 없음 (D43, D80 문턱 판정)")
        gate_fail = f.get("경로") == "일반" and small == 0 and jaryo is not None and jaryo <= 3
        # 깊이 글은 실제 검색 근거가 있는 키워드만 (D72): 「추정」 금지
        if f.get("경로") == "일반" and "추정" in f.get("키워드 근거", ""):
            errs.append(f"{tid}: 깊이 글 키워드 근거에 「추정」 — 자동완성·知恵袋·트렌드에서 확인한 키워드만 (D72)")
        subs = [s for s in re.split(r"\s+/\s+", f.get("서브 키워드", "")) if s.strip()]
        if not 3 <= len(subs) <= 5:
            errs.append(f"{tid}: 서브 키워드 {len(subs)}개 (3~5개)")
        # D87: 서브 키워드 = 일본 독자가 쓰는 일본어 질문형
        bad = (errs if new else warns)
        for x in subs:
            if not JA.search(x):
                bad.append(f"{tid}: 서브 키워드 「{x}」에 일본어가 없음 — 일본어 검색어만 (D87)")
        q = sum(1 for x in subs if JA.search(x) and is_question(x))
        need_q = 2 if f.get("경로") == "속보" else 3
        if q < need_q:
            bad.append(f"{tid}: 질문형 서브 키워드 {q}개 ({f.get('경로')} {need_q}개 이상 — 〜とは·使い方·費用·対策 등, D87)")
        mk = f.get("메인 키워드", "")
        # D87: 메인 키워드 = 실제로 확인한 말 (키워드 근거에 그대로)
        basis_kw = f.get("키워드 근거", "")
        if mk and kw_norm(mk) not in kw_norm(basis_kw):
            if f.get("경로") == "일반" and new:
                errs.append(f"{tid}: 메인 키워드 「{mk}」가 키워드 근거에 없음 — 자동완성·知恵袋에서 확인한 말만 메인으로 (D87)")
            elif "원문 제목" not in basis_kw:
                warns.append(f"{tid}: 메인 키워드 「{mk}」가 키워드 근거에 없음 — 새 이름이라 자동완성이 없으면 근거에 「원문 제목」 (D87)")
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
            # D87: 수요 = 질문형 서브 키워드 수로 한 칸씩 (0→1, 1→2, 2→3, 3+→4, 5 = 3+ + 知恵袋 반복 또는 트렌드)
            cap = demand_cap(q, basis_kw + f.get("점수 근거", ""))
            if s["수요"] > cap:
                (errs if new else warns).append(
                    f"{tid}: 수요 {s['수요']} > 질문형 {q}개의 상한 {cap} — 수요 점수표대로 (D87)")
        dl = None
        if f.get("경로") == "속보":
            dm_ = re.search(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?", f.get("마감", ""))
            if not dm_:
                errs.append(f"{tid}: 속보는 마감 필요 — deadline.py로 계산 (발표 + 72시간, 업무 시간 밖이면 다음 업무일 12:00, D88)")
            else:
                dl = DL.parse(dm_.group(0))
                if not re.search(r"\d{1,2}:\d{2}", dm_.group(0)):
                    (errs if new else warns).append(f"{tid}: 마감에 시각이 없음 — 「YYYY-MM-DD HH:MM」 (D88)")
                elif not DL.in_work_hours(dl):
                    (errs if new else warns).append(
                        f"{tid}: 마감 {dm_.group(0)}이 업무 시간(평일 9~18시) 밖 — deadline.py로 다음 업무일 12:00 (D88)")
        # D86: 속보의 보안 축은 급한 보안만 (실제 악용 중인 취약점·일본 중소기업 경로의 사고)
        urgent = f.get("급한 보안", "").strip().startswith("예")
        if f.get("경로") == "속보" and f.get("주제 축") == "보안" and not urgent:
            errs.append(f"{tid}: 보안 속보는 「급한 보안: 예 — 근거」가 있어야 순위표에 — 급하지 않으면 「1차에서 빠진 후보」로 (D86)")
        if f.get("실습") and not any(f["실습"].startswith(t) for t in TRIALS):
            errs.append(f"{tid}: 실습 값 '{f['실습']}' (에이전트 가능 / 사람 필요 / 해당 없음 으로 시작)")
        details[tid] = {"axis": f.get("주제 축"), "route": f.get("경로"), "total": tot, "title": tt,
                        "type": f.get("글 종류"), "rec": f.get("추천", "").strip(),
                        "trial": f.get("실습", ""), "gate_fail": gate_fail, "main_kw": f.get("메인 키워드", ""),
                        "urgent": urgent and f.get("주제 축") == "보안", "deadline": dl}

    # 순위표
    tables = TABLES
    picked = "☑" in text
    marks = {}
    for title, route, _ in tables:
        mm = re.search(re.escape(title) + r"[^\n]*\n((?:\|.*\n)+)", text)
        if not mm:
            errs.append(f"순위표 없음: {title}")
            continue
        rows = [r for r in mm.group(1).splitlines()[2:] if r.strip()]
        if len(rows) > 5:
            errs.append(f"{title}: {len(rows)}개 (최대 5개)")
        prev = 999
        marks[title] = []
        urgent_rows = []
        for r in rows:
            c = [x.strip() for x in r.strip().strip("|").split("|")]
            if len(c) < 10:
                errs.append(f"{title}: 칸 수 부족(10칸: …1키워드1글 | 이월) '{r[:40]}'")
                continue
            mark, tid, tot, carry = c[0], c[2], c[6], c[9]
            if mark not in MARKS:
                errs.append(f"{title}: {tid} 선택 값 '{mark}' (☐ ○ ☑)")
            if carry != "-" and not re.match(r"topics/[\w.-]+\.md T\d+$", carry):
                errs.append(f"{title}: {tid} 이월 칸 형식 '{carry}' (- 또는 'topics/파일.md T03')")
            d = details.get(tid)
            if not d:
                errs.append(f"{title}: {tid} 상세 없음")
                continue
            urgent_rows.append(d["urgent"])
            if mark in ("○", "☑"):
                marks[title].append(d["urgent"])
            if mark in ("○", "☑") and d.get("gate_fail"):
                errs.append(f"{title}: {tid} 「{d['main_kw']}」는 이길 여지 문턱 미달(작은 사이트 0 + 자료 판정 3 이하) — "
                            f"더 구체적인 말을 메인으로 다시 세거나 추천에서 건너뛴다 (D80)")
            # D88: ○ 속보는 남은 업무 시간이 NEED_HOURS 이상 (6시간 규칙을 바꿈)
            if mark == "○" and d.get("deadline") and front.get("made_at"):
                try:
                    left = DL.work_hours_left(DL.parse(front["made_at"]), d["deadline"])
                except ValueError:
                    left = None
                if left is not None and left < DL.NEED_HOURS:
                    errs.append(f"{title}: {tid} 마감까지 업무 시간 {left:.1f}시간 — {DL.NEED_HOURS}시간 미만은 추천하지 않는다 (D88)")
            if mark == "○" and not d["rec"]:
                errs.append(f"{title}: {tid}는 ○인데 상세에 「추천:」 이유가 없음")
            if d["route"] != route:
                errs.append(f"{title}: {tid}의 경로는 {d['route']}")
            if d["title"].startswith("[更新]"):
                errs.append(f"{title}: {tid} — 개편은 회차 몫에 없다. 「1차에서 빠진 후보」에 업데이트 제안으로 (D72)")
            if str(d["total"]) != tot:
                errs.append(f"{title}: {tid} 총점 {tot} ≠ 상세 {d['total']}")
            if c[3] != d["title"]:
                errs.append(f"{title}: {tid} 가제목이 상세와 다름")
            if tot.isdigit():
                if int(tot) > prev:
                    errs.append(f"{title}: 총점 내림차순이 아님 ({tid})")
                prev = int(tot)
        marks[title] = (marks[title], urgent_rows)
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
    # 추천 ○ 개수: 속보 2 · 깊이 1. 속보에 급한 보안이 있으면 ○ 중 급한 보안 1개 + 그 밖 1개 (D86)
    for title, _, want_n in tables:
        if title not in marks:
            continue
        chosen, rows = marks[title]
        want = min(want_n, len(rows))
        msgs = []
        if len(chosen) != want:
            msgs.append(f"{title}: 추천 ○ {len(chosen)}개 (기대 {want}개)")
        if want_n == 2 and any(rows) and not all(rows) and len(chosen) == 2 and sum(chosen) != 1:
            msgs.append(f"{title}: 급한 보안이 있으면 ○는 급한 보안 1 + 그 밖 1 (지금 급한 보안 {sum(chosen)}개, D86)")
        (warns if picked else errs).extend(msgs)

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
