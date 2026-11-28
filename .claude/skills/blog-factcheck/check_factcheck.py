#!/usr/bin/env python3
"""blog-factcheck: 사실 대조 보고서 만들기·점검 (rules/blog-factcheck.md, D48)

대조 단위 = 초안의 사실 문장(표시 [S번호]가 붙은 문장·표 행) + 제목 + 메타 설명 + 표시 없는 사실 문장 후보(숫자·「」 이름, D103).
원문 페이지는 다시 열지 않는다 — 노트의 원어 원문 문장과 대조 (D103). 노트 확인일이 오래된 출처만 다시 연다.
판정(일치·고침·뺌·설명)은 에이전트가 원문을 읽고 적는다. 스크립트는 빠진 것·남은 것·형식만 본다.

사용법:
  python3 -I check_factcheck.py drafts/<slug>.md --init [--force]   보고서 뼈대 factcheck/<slug>.md 만들기
  python3 -I check_factcheck.py drafts/<slug>.md --urls-out FILE    다시 열 URL 목록 (fetch_page.py --urls 로)
  python3 -I check_factcheck.py drafts/<slug>.md --fill-titles INDEX  fetch_page.py의 index.json으로 제목·연 날 채우기
  python3 -I check_factcheck.py drafts/<slug>.md --write-sources    초안 SOURCES를 URL별 번호로 쓰기
  python3 -I check_factcheck.py drafts/<slug>.md                    점검 (초안 점검 check_draft.py 포함)
  python3 -I check_factcheck.py drafts/<slug>.md --recheck          다듬기 뒤: 달라진 사실 문장을 「재대조 대상」/「표현만 바뀜(생략)」으로 (D61)
  python3 -I check_factcheck.py drafts/<slug>.md --recheck --write-skips   표현만 바뀐 것을 재대조 기록에 근거 승계로 적기
종료 코드 0 = 통과, 1 = 오류
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "blog-draft"))
sys.path.insert(0, str(HERE.parent / "blog-outline"))
from check_outline import front, sections, table, norm  # noqa: E402
from check_draft import split_draft, sentences, note_facts, TAG_RE  # noqa: E402

JST = timezone(timedelta(hours=9))
S_RE = re.compile(r"S\d+")
SEP_RE = re.compile(r"^\|[\s\-|:]+\|$")
CORE_POS = ("제목", "메타", "리드", "3行まとめ")
# D77: 핵심(●) = 제목·메타·리드·3行まとめ·차별 포인트·H2 직답 + 날짜·시점이 든 문장.
# 숫자만 든 문장(판 번호·건수)은 핵심이 아니다 — 노트의 원어 원문 문장과 대조하는 것은 그대로
DATE_RE = re.compile(r"\d+月\d+日|\d{4}年|\d+月(?:時点|まで|から|末|中|上旬|中旬|下旬)|時点|\d{1,2}時")
OK_VERDICT = {"일치", "고침", "설명"}
ALL_VERDICT = OK_VERDICT | {"뺌", "불일치", "확인 불가"}
STALE_DAYS = 7
REPORT_SECTIONS = ["요약", "출처 다시 열기", "대조표", "실명 기업 문장", "쓰지 않을 것 확인", "고친 내용", "재대조 기록"]
SRC_HEAD = "| 번호 | 제목 | 발행처 | 발표일 | URL | S번호 | 등급 | 다시 열기 | 연 날 | 결과 |"
ROW_HEAD = "| # | 위치 | 문장 | 표시 | 핵심 | 판정 | 근거·조치 |"


# D61: 사실 표지 — 이것이 같으면 「표현만 바뀜」으로 보고 재대조를 생략한다
LIMIT_WORDS = ("だけ", "のみ", "すべて", "全て", "全部", "一部", "自分で", "必ず", "限る", "限り", "以上", "以下", "以前",
               "以降", "未満", "可能性", "おそれ", "恐れ", "まで", "から", "ほとんど", "多く", "少なくとも", "約", "ごろ", "頃")
NEG_RE = re.compile(r"(ない|ません|なく|ず[、。]|ぬ|不要|無効)")


def markers(t):
    """문장 → 사실 표지 (숫자·날짜·판 번호, S번호, 영문 고유명사, 가타카나 말, 한정·범위어, 부정, 주어)"""
    from collections import Counter
    d = display(t)
    m = Counter()
    for x in re.findall(r"\d+(?:[.,]\d+)*", d):
        m["num:" + x] += 1
    for x in S_RE.findall(t):
        m["src:" + x] += 1
    for x in re.findall(r"[A-Za-z][A-Za-z0-9.+\-]*", d):
        m["en:" + x.lower()] += 1
    for x in re.findall(r"[ァ-ヴー]{3,}", d):
        m["kana:" + x] += 1
    for w in LIMIT_WORDS:
        if w in d:
            m["lim:" + w] += d.count(w)
    m["neg"] = len(NEG_RE.findall(d))
    for w in ("求め", "呼びかけ", "勧め", "推奨", "必要", "義務", "禁止", "予定", "見込み", "確認でき"):   # 말한 쪽의 태도·강도
        if w in d:
            m["stance:" + w] += d.count(w)
    sub = re.match(r"^(.{1,24}?)(?:によると|は|が)", d)
    if sub:
        m["sub:" + re.sub(r"[「」、\s]", "", sub.group(1))] += 1
    return m


def bigram_sim(a, b):
    A = {a[i:i + 2] for i in range(len(a) - 1)}
    B = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(A & B) / max(1, len(A | B))


def display(s):
    """보고서에 적는 문장: 표시·링크 URL·굵게 빼고, 표의 | 는 ／ 로"""
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", s)
    s = TAG_RE.sub("", s).replace("**", "")
    s = s.replace("|", "／")
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    return norm(display(s)).replace("／", "/")


def units(text):
    """초안 → 대조 단위 [{pos, text, tags, core, tagged}]"""
    f = front(text)
    main, _, _ = split_draft(text)
    lines = main.splitlines()
    out = []

    def add(pos, raw, core=False, diff=False):
        d = display(raw)
        if not d:
            return
        tags = TAG_RE.findall(raw)
        tagged = bool(tags)
        cand = bool(re.search(r"\d|「[^」]{4,}」", d))   # D103: 사실 표지 = 숫자·날짜·「」 이름. 영문 제품명만 든 설명 문장은 대조 단위가 아니다
        if not tagged and not cand and pos not in ("제목", "메타"):
            return
        core = core or diff or pos.startswith(CORE_POS) or bool(DATE_RE.search(d))
        out.append({"pos": pos, "text": d, "tags": tags, "core": core, "tagged": tagged})

    for s in sentences(f.get("meta", "")):
        add("메타", s, core=True)
    pos, box, diff, lead_done, seen_h2 = "도입부", None, False, False, False
    answer_next = False  # D77: H2 바로 뒤 첫 문단의 굵은 문장 = 직답 → 핵심
    for i, l in enumerate(lines):
        st = l.strip()
        if not st:
            diff = False
            continue
        if st.startswith("<!--"):
            if re.match(r"^<!--\s*차별\s*\d+\s*-->$", st):
                diff = True
            continue
        if st.startswith("# "):
            add("제목", st[2:], core=True)
            continue
        if st.startswith("## "):
            pos, seen_h2, answer_next = st[3:].strip(), True, True
            if pos == "SOURCES":
                break
            add(pos + " (H2)", st[3:])
            continue
        if st.startswith("### "):
            add(pos + " (H3)", st[4:])
            continue
        if st.startswith(":::"):
            lab = st[3:].strip()
            if box is None:
                box = lab
            else:
                box = None
            continue
        if box and box.startswith(("cta", "trial")):   # trial = 사람 실습 자리 표시, 결과가 들어오면 --recheck (D79)
            continue
        here = box.split(None, 1)[-1] if box else pos
        if not seen_h2 and not box and not lead_done and not st.startswith(("|", ">")):
            here, lead_done = "리드", True
            for s in sentences(st.replace("**", "")):
                add(here, s, core=True)
            continue
        if SEP_RE.match(st):
            continue
        if st.startswith("|"):
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if SEP_RE.match(nxt) and not TAG_RE.search(st):
                continue  # 표 머리 행
            add(here, st.strip("|"), diff=diff)
            continue
        if st.startswith(">"):
            add(here, st.lstrip("> "), diff=diff)  # 인용은 한 줄 통째로
            continue
        is_answer = answer_next and not box and st.startswith("**")
        answer_next = False
        if is_answer:
            bold = re.match(r"^\*\*(.+?)\*\*", st)
            ans_keys = {key(display(s)) for s in sentences(bold.group(1))} if bold else set()
        body = re.sub(r"^\s*(-|\d+\.(?!\d))\s*", "", st).replace("**", "")
        for s in sentences(body):
            add(here, s, core=is_answer and key(display(s)) in ans_keys, diff=diff)
    return out


def used_order(units_):
    seen = []
    for u in units_:
        for t in u["tags"]:
            if t.startswith("S") and t not in seen:
                seen.append(t)
    return seen


def url_groups(order, facts):
    """S번호 순서 → URL별 묶음 (처음 나온 순서)"""
    groups = {}
    for s in order:
        r = facts.get(s)
        if not r:
            continue
        u = r[4]
        g = groups.setdefault(u, {"url": u, "sids": [], "pub": [], "dates": [], "grades": [], "checked": []})
        g["sids"].append(s)
        for k, v in (("pub", r[3]), ("dates", r[6]), ("grades", r[5]), ("checked", r[7])):
            if v not in g[k]:
                g[k].append(v)
        g["dates"].sort()
    return list(groups.values())


def need_reopen(route, groups, units_, today):
    core_s = {t for u in units_ if u["core"] for t in u["tags"] if t.startswith("S")}
    need = {}
    for g in groups:
        why = []
        if route == "속보" and "A" in g["grades"]:
            why.append("속보 A")
        # D103: 핵심 문장이라고 원문 페이지를 다시 열지 않는다 — 노트에 원어 원문 문장이 있다.
        #       노트 확인일이 오래된 출처만 다시 연다. 속보의 「발표가 바뀌었나」는 blog-publish 발행 직전 한 번
        for c in g["checked"]:
            try:
                d = datetime.strptime(c, "%Y-%m-%d").date()
            except ValueError:
                continue
            if (today - d).days > STALE_DAYS:
                why.append(f"{STALE_DAYS}일 지남")
                break
        # D61: 속보도 핵심 문장의 출처만 다시 연다 (A등급 전부 → 핵심). 나머지는 노트의 원어 원문 문장과 대조.
        #      발행 직전 공식 발표 재확인은 blog-publish가 한다
        need[g["url"]] = [w for w in why if w != "속보 A"]
    return need


def load(draft_path, root):
    text = draft_path.read_text()
    f = front(text)
    note = (root / f["research"]).read_text()
    facts, _ = note_facts(note)
    rp = root / "factcheck" / f"{f['slug']}.md"
    return text, f, facts, rp


def init(a, root):
    dp = Path(a.file)
    text, f, facts, rp = load(dp, root)
    if rp.exists() and not a.force:
        print(f"이미 있음: {rp} (덮어쓰려면 --force)")
        return 1
    us = units(text)
    groups = url_groups(used_order(us), facts)
    today = datetime.now(JST).date()
    need = need_reopen(f["route"], groups, us, today)
    title = next((u["text"] for u in us if u["pos"] == "제목"), "")
    src = [SRC_HEAD, "|---|---|---|---|---|---|---|---|---|---|"]
    for n, g in enumerate(groups, 1):
        why = " · ".join(need[g["url"]]) or "-"
        src.append(f"| {n} |  | {' / '.join(g['pub'])} | {', '.join(g['dates'])} | {g['url']} | "
                   f"{', '.join(g['sids'])} | {'/'.join(g['grades'])} | {why} |  |  |")
    rows = [ROW_HEAD, "|---|---|---|---|---|---|---|"]
    for n, u in enumerate(us, 1):
        tg = " ".join(u["tags"]) if u["tags"] else "-"
        rows.append(f"| {n} | {u['pos']} | {u['text']} | {tg} | {'●' if u['core'] else ''} |  |  |")
    body = f"""---
slug: {f['slug']}
draft: {dp.as_posix()}
research: {f['research']}
outline: {f['outline']}
route: {f['route']}
checked_at: {datetime.now(JST).strftime('%Y-%m-%dT%H:%M+09:00')}
result: 진행 중
rechecked_at: -
---

# 대조 보고서: {title}

## 요약
- 결과: (통과 | 멈춤 — 이유)
- 대조 단위 {len(us)}개 / 일치 · 고침 · 뺌 · 설명 (개수)
- 다시 연 출처: (개수, 바뀐 것)
- 고친 것: (짧게)

## 출처 다시 열기
- 다시 열기: {STALE_DAYS}일 지남 = 노트 확인일이 오래된 출처만 (D103 — 나머지는 노트의 원어 원문 문장과 대조, 속보 발표 변경은 발행 직전 blog-publish)
- 결과: 그대로 / 바뀜(영향 없음: …) / 바뀜(영향 있음: …) / 열리지 않음

{chr(10).join(src)}

## 대조표
- 판정: 일치 / 고침 / 뺌 / 설명(사실 아님) — 불일치·확인 불가는 고치거나 빼고 「고침」「뺌」으로 바꾼다
- 고친 행은 「문장」 칸을 고친 뒤의 문장으로 바꾸고, 전 문장은 「고친 내용」에
- 근거: S번호 + 노트 원어 원문 문장과의 대조 결과 (D103 — 원문 페이지는 다시 열지 않음). 대조 단위는 숫자·날짜·이름·범위·조건·누가 말했나가 든 문장만

{chr(10).join(rows)}

## 실명 기업 문장
- (문장 · 공식 발표 표현 범위 안인지) — 없으면 「-」

## 쓰지 않을 것 확인
- (설계안 「쓰지 않을 것」 항목마다 본문에 없음 / 있음→뺌)

## 고친 내용
- -

## 재대조 기록
{ROW_HEAD.replace('| # |', '| 날짜 |')}
|---|---|---|---|---|---|---|
"""
    rp.write_text(body)
    print(f"[뼈대] {rp} — 대조 단위 {len(us)}개, 출처 URL {len(groups)}개 (다시 열기 필요 {sum(1 for v in need.values() if v)}개)")
    return 0


def report_rows(sec, name):
    out = []
    for r in table(sec.get(name, [])):
        if len(r) >= 7:
            out.append({"no": r[0], "pos": r[1], "text": r[2], "tags": r[3], "core": r[4], "verdict": r[5], "basis": r[6]})
    return out


def src_rows(sec):
    out = {}
    for r in table(sec.get("출처 다시 열기", [])):
        if len(r) >= 10:
            out[r[4]] = {"no": r[0], "title": r[1], "pub": r[2], "dates": r[3], "url": r[4], "sids": r[5],
                         "grade": r[6], "why": r[7], "opened": r[8], "result": r[9]}
    return out


def sources_lines(groups, srcs):
    lines = []
    for n, g in enumerate(groups, 1):
        s = srcs.get(g["url"], {})
        checked = s.get("opened") or max(g["checked"])
        lines.append(f"{n}. {s.get('title', '')} | {' / '.join(g['pub'])} | 発表日 {', '.join(g['dates'])} | "
                     f"{g['url']} | 確認日 {checked} | {', '.join(g['sids'])}")
    return lines


def fill_titles(a, root):
    text, f, facts, rp = load(Path(a.file), root)
    idx = json.loads(Path(a.fill_titles).read_text())
    by = {}
    for e in idx:
        for u in (e.get("url"), e.get("final_url")):
            if u:
                by[u.rstrip("/")] = e
    lines = rp.read_text().splitlines()
    n_ok = 0
    for i, l in enumerate(lines):
        if not l.startswith("|") or SEP_RE.match(l.strip()):
            continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if len(c) != 10 or not c[4].startswith("http"):
            continue
        e = by.get(c[4].rstrip("/"))
        if not e:
            continue
        if e.get("error"):
            c[8] = e.get("fetched_at", "")[:10]
            c[9] = c[9] or f"열리지 않음({e['error'][:40]})"
        else:
            c[1] = c[1] or e.get("title", "").replace("|", "／").strip()
            c[8] = e.get("fetched_at", "")[:10]
            n_ok += 1
        lines[i] = "| " + " | ".join(c) + " |"
    rp.write_text("\n".join(lines) + "\n")
    print(f"[제목·연 날] {n_ok}개 채움 — 「결과」 칸은 원문을 읽고 적는다")
    return 0


def write_sources(a, root):
    dp = Path(a.file)
    text, f, facts, rp = load(dp, root)
    sec = sections(rp.read_text())
    srcs = src_rows(sec)
    us = units(text)
    groups = url_groups(used_order(us), facts)
    miss = [g["url"] for g in groups if g["url"] not in srcs or not srcs[g["url"]]["title"]]
    if miss:
        print("❌ 출처 다시 열기 표에 없거나 제목이 빈 URL: " + ", ".join(miss))
        return 1
    new = "\n".join(sources_lines(groups, srcs))
    text2 = re.sub(r"(^## SOURCES\s*\n)(.*?)(?=^## 초안 메모|\Z)", lambda m: m.group(1).rstrip() + "\n\n" + new + "\n\n",
                   text, count=1, flags=re.S | re.M)
    dp.write_text(text2)
    print(f"[SOURCES] URL {len(groups)}개로 씀")
    return 0


def check(a, root, recheck=False):
    errs, warns = [], []
    E, W = errs.append, warns.append
    dp = Path(a.file)
    text, f, facts, rp = load(dp, root)
    if not rp.exists():
        print(f"❌ 보고서 없음: {rp} — --init 으로 만든다")
        return 1
    rtext = rp.read_text()
    rf, sec = front(rtext), sections(rtext)
    for s in REPORT_SECTIONS:
        if s not in sec:
            E(f"보고서에 「## {s}」 절이 없음")
    us = units(text)
    rows = report_rows(sec, "대조표")
    rech = report_rows(sec, "재대조 기록")
    base = {}
    for r in rows + rech:
        base[key(r["text"])] = r  # 재대조 기록이 뒤에 오므로 같은 문장이면 재대조 판정이 이긴다
    cur_keys = {key(u["text"]) for u in us}

    # 1. 초안의 모든 단위가 대조됐는지
    missing = [u for u in us if key(u["text"]) not in base]
    if recheck:
        today = datetime.now(JST).strftime("%Y-%m-%d")
        # D61: 달라진 단위마다 원래 대조 행(같은 위치·가장 비슷한 문장)을 찾아 사실 표지를 비교한다
        pool = [r for r in rows + rech if r["verdict"] in OK_VERDICT and key(r["text"]) not in cur_keys]
        todo, skip = [], []
        for u in missing:
            cand = sorted(((bigram_sim(key(u["text"]), key(r["text"])), r) for r in pool
                           if r["pos"].split("(")[0] == u["pos"].split("(")[0]), key=lambda x: -x[0])
            if cand and cand[0][0] >= 0.35 and markers(cand[0][1]["text"]) == markers(u["text"]) \
                    and set(S_RE.findall(" ".join(u["tags"]))) <= set(S_RE.findall(cand[0][1]["tags"] + cand[0][1]["basis"])):
                skip.append((u, cand[0][1]))
                pool.remove(cand[0][1])
            else:
                todo.append((u, cand[0][1] if cand else None))
        if todo:
            print(f"재대조 대상 {len(todo)}개 — 사실 표지(숫자·날짜·고유명사·S번호·한정어·부정·주어)가 바뀌었거나 새 문장. 원문과 다시 대조해 「재대조 기록」에:")
            for u, r in todo:
                tg = " ".join(u["tags"]) if u["tags"] else "-"
                if r:
                    a_, b_ = markers(r["text"]), markers(u["text"])
                    diff = sorted(set((a_ - b_) | (b_ - a_)))
                    print(f"  ↳ 원래 #{r['no']}: {r['text'][:60]} / 바뀐 표지: {', '.join(diff)[:120]}")
                print(f"| {today} | {u['pos']} | {u['text']} | {tg} | {'●' if u['core'] else ''} |  |  |")
        if skip:
            print(f"표현만 바뀜 {len(skip)}개 — 사실 표지가 같아 재대조 생략 (--write-skips 로 재대조 기록에 근거 승계):")
            for u, r in skip:
                print(f"  - [{u['pos']}] #{r['no']} → {u['text'][:60]}")
        if a.write_skips and skip:
            rtxt = rp.read_text()
            add = "".join(f"| {today} | {u['pos']} | {u['text']} | {' '.join(u['tags']) if u['tags'] else '-'} | {'●' if u['core'] else ''} "
                          f"| {r['verdict']} | 표현만 바뀜(사실 표지 같음, D61) — #{r['no']} 근거 승계: {r['basis']} |\n" for u, r in skip)
            i = rtxt.index("## 재대조 기록")
            j = rtxt.find("\n## ", i + 5)
            j = len(rtxt) if j < 0 else j
            body = rtxt[i:j].rstrip("\n") + "\n" + add
            rp.write_text(rtxt[:i] + body + ("\n" + rtxt[j:].lstrip("\n") if j < len(rtxt) else ""))
            print(f"재대조 기록에 {len(skip)}행 적음 (근거 승계)")
        print(f"재대조 대상 {len(todo)}개 / 생략 {len(skip)}개")
        missing = [u for u, _ in todo]
        gone = [r for r in rows if r["verdict"] in ("일치", "고침") and key(r["text"]) not in cur_keys]
        if gone:
            print(f"대조표에 있었는데 초안에서 사라진 사실 문장 {len(gone)}개 (다듬기에서 지웠거나 바꿈):")
            for r in gone:
                print(f"  - [{r['pos']}] {r['text'][:50]}")
        if not missing:
            print("달라진 사실 문장 없음")
        return 1 if missing else 0
    for u in missing:
        E(f"대조표에 없는 단위 [{u['pos']}] 「{u['text'][:40]}」 — 대조해서 행을 더한다 (고쳤으면 그 행의 문장 칸도)")
    # 2. 판정
    for r in rows + rech:
        v = r["verdict"]
        if not v:
            E(f"#{r['no']} [{r['pos']}] 판정이 비어 있음")
        elif v not in ALL_VERDICT:
            E(f"#{r['no']} 판정 「{v}」 — {sorted(ALL_VERDICT)} 중 하나")
        elif v in ("불일치", "확인 불가"):
            E(f"#{r['no']} 「{v}」가 남아 있음 — 원문대로 고치거나(고침) 빼고(뺌) 판정을 바꾼다")
        elif v == "뺌":
            if key(r["text"]) in cur_keys:
                E(f"#{r['no']} 판정 「뺌」인데 초안에 그 문장이 남아 있음")
        elif v in ("일치", "고침"):
            tg = set(S_RE.findall(r["tags"]))
            if r["pos"] in ("제목", "메타") and not S_RE.search(r["basis"]):
                E(f"#{r['no']} {r['pos']}: 근거에 S번호가 없음 (제목·메타도 원문과 대조, D47 보강)")
            if tg and not (tg & set(S_RE.findall(r["basis"]))):
                E(f"#{r['no']} 근거에 S번호가 없음 ({', '.join(sorted(tg))})")
            if not r["basis"]:
                E(f"#{r['no']} 근거가 비어 있음")
            if v == "일치" and r["tags"] in ("-", "") and r["pos"] not in ("제목", "메타") and "(H" not in r["pos"]:
                W(f"#{r['no']} 표시 없는 문장이 「일치」 — 사실이면 초안에 [S번호]를 붙이고, 아니면 「설명」")
        if v == "설명" and S_RE.search(r["tags"]):
            E(f"#{r['no']} [S번호]가 붙은 문장은 「설명」일 수 없다 — 일치 또는 고침")
        if v in OK_VERDICT and key(r["text"]) not in cur_keys and r in rows and rf.get("rechecked_at", "-") == "-":
            E(f"#{r['no']} 대조표 문장이 초안에 없음 — 초안을 고쳤으면 대조표 문장 칸도 같게")
    if "[?]" in text.split("## SOURCES")[0]:
        E("초안에 [?]가 남아 있음 — 출처 추가 / 의견 표현 / 삭제 중 하나 (통과 기준)")

    # 3. 출처 다시 열기
    srcs = src_rows(sec)
    groups = url_groups(used_order(us), facts)
    today = datetime.now(JST).date()
    need = need_reopen(f["route"], groups, us, today)
    for g in groups:
        s = srcs.get(g["url"])
        if not s:
            E(f"출처 다시 열기 표에 URL이 없음: {g['url']}")
            continue
        if not s["title"]:
            E(f"출처 {s['no']} 제목이 비어 있음 (원문 페이지 제목) — --fill-titles")
        res = s["result"]
        if need[g["url"]]:
            if not s["opened"]:
                E(f"출처 {s['no']} 다시 열어야 함({' · '.join(need[g['url']])})인데 「연 날」이 비어 있음")
            if not res:
                E(f"출처 {s['no']} 「결과」가 비어 있음")
        if res.startswith("바뀜(영향 있음") or res.startswith("열리지 않음"):
            E(f"출처 {s['no']} {res[:30]} — 멈추고 blog-research로 (노트 보충 뒤 다시 대조)")
        elif res and not res.startswith(("그대로", "바뀜(영향 없음", "-")):
            E(f"출처 {s['no']} 결과 「{res[:20]}」 — 그대로 / 바뀜(영향 없음: …) / 바뀜(영향 있음: …) / 열리지 않음")
    extra = set(srcs) - {g["url"] for g in groups}
    if extra:
        W(f"본문에서 안 쓰는 출처가 표에 있음: {', '.join(sorted(extra))}")

    # 4. SOURCES
    want = sources_lines(groups, srcs)
    _, src_txt, _ = split_draft(text)
    got = [l.strip() for l in src_txt.splitlines() if re.match(r"^\d+\.\s", l.strip())]
    if got != want:
        E("초안 SOURCES가 출처 표와 다름 — --write-sources 로 쓴다 (URL별 번호, D48)")

    # 5. 그 밖의 절
    for name in ("실명 기업 문장", "쓰지 않을 것 확인", "고친 내용"):
        if not [l for l in sec.get(name, []) if l.strip().startswith("- ")]:
            E(f"「{name}」에 항목이 없음 (없으면 「- -」)")
    ol = (root / f["outline"]).read_text() if (root / f["outline"]).exists() else ""
    no_write = [l for l in sections(ol).get("쓰지 않을 것", []) if l.strip().startswith("- ")]
    got_nw = [l for l in sec.get("쓰지 않을 것 확인", []) if l.strip().startswith("- ") and "(설계안" not in l]
    if len(got_nw) < len(no_write):
        E(f"쓰지 않을 것 확인 {len(got_nw)}개 — 설계안 항목 {len(no_write)}개를 하나씩")

    # 6. 초안 점검 다시 (고치다가 키워드·H2·분량을 망가뜨리지 않았는지)
    cd = HERE.parent / "blog-draft" / "check_draft.py"
    p = subprocess.run([sys.executable, "-I", str(cd), str(dp), "--root", str(root)], capture_output=True, text=True)
    if p.returncode != 0:
        E("초안 점검(check_draft.py) 불통과 — 분량 하한 미달·차별 포인트 0이면 늘려 쓰지 말고 멈춘다 (D48):\n   "
          + "\n   ".join(l for l in p.stdout.splitlines() if l.startswith("❌")))

    n_v = {}
    for r in rows + rech:
        n_v[r["verdict"]] = n_v.get(r["verdict"], 0) + 1
    print(f"대조 단위 {len(us)}개 / 판정 " + " · ".join(f"{k} {v}" for k, v in n_v.items() if k)
          + f" / 출처 URL {len(groups)}개 (다시 열기 필요 {sum(1 for v in need.values() if v)}개)")
    if not errs and rf.get("result") != "통과":
        W("보고서 머리 `result:`를 「통과」로")
    for e in errs:
        print("❌ " + e)
    for w in warns:
        print("⚠ " + w)
    print("통과" if not errs else f"오류 {len(errs)}건")
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--root", default=".")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--urls-out")
    ap.add_argument("--fill-titles")
    ap.add_argument("--write-sources", action="store_true")
    ap.add_argument("--recheck", action="store_true")
    ap.add_argument("--write-skips", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    if a.init:
        return init(a, root)
    if a.urls_out:
        text, f, facts, _ = load(Path(a.file), root)
        groups = url_groups(used_order(units(text)), facts)
        Path(a.urls_out).write_text("\n".join(g["url"] for g in groups) + "\n")
        print(f"[URL] {len(groups)}개 → {a.urls_out}")
        return 0
    if a.fill_titles:
        return fill_titles(a, root)
    if a.write_sources:
        return write_sources(a, root)
    return check(a, root, recheck=a.recheck)


if __name__ == "__main__":
    sys.exit(main())
