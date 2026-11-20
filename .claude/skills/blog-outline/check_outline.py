#!/usr/bin/env python3
"""blog-outline: 설계안 점검 (읽기 전용).

outlines/<slug>.md 를 읽어 rules/common.md 1·4·6장, rules/blog-outline.md 기준을 검사한다.
 1. 머리(front matter)·필수 절 (개편이면 「개편」 절, 속보면 「갱신 조건」 내용)
 2. 제목: 추천 1개, 전각 28~35자, 메인 키워드가 앞쪽, 기존 글과 같은 제목 아님(개편은 자기 글 제외)
 3. 메타 설명: 전각 80~120자, 메인 키워드 포함, 기존 글 메타와 같지 않음
 4. slug: 카드 slug와 같음, 형식, 개편이면 기존 글 목록에 있는 slug
 5. 목차: H2 4~8개, 키워드 H2 절반 이상, 직답 40~80자, 형식 칸, 사건 검색어는 「何が起きた」 H2에,
    「とは」 키워드면 「〇〇とは、」 정의 직답
 6. 쓸 사실 S번호가 조사 노트에 있는지 / 분량 합계가 범위 안인지
 7. 서브 키워드: 질문형 3개 이상 (속보: 사건 1~2 + 질문형 2 이상), 카드에 D43 키워드 절
 8. CTA: 주·보조가 카드와 같음, 버튼 문구·링크가 common.md 「CTA 버튼」 표와 같음, 속보는 글 끝만
 9. 내부 링크: 3~4개, 기둥 1개, 기존 글 URL, 「こちら」 금지, 다른 사건 이름 경고
10. 역링크: 기존 글 2개 이상, 기존 글 URL, 자기 글 아님
11. 검색 의도·겹침 구분·차별 포인트 배치·태그
12. FAQ: 근거 검색어가 카드에 기록된 것, 질문에 그 단어가 다 들어 있음
13. 판 번호가 조사 노트에 있는지, 「〇系以前」 같은 범위 넓힘 경고
14. 도입부에 메인 키워드(속보는 사건 검색어도)
15. 실습: trial 사람이고 노트에 결과가 없으면 「◆ 실습 대기」 행
16. SNS 포인트·대표 한마디·금지 표현

사용법:
  python3 -I check_outline.py outlines/<slug>.md [--root .] [--verify-links]
  (--verify-links: 역링크 대상 글을 가져와 「넣을 곳」의 H2가 실제로 있는지 확인. 설계를 마칠 때 꼭 붙인다)
종료 코드 0 = 통과(경고만 있을 수 있음), 1 = 오류
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

FRONT = ["slug", "brief", "research", "route", "kind", "type", "trial", "skeleton", "length", "main_keyword",
         "sub_keywords", "event_keywords", "cta_main", "cta_sub", "rep_comment", "created_at"]
SECTIONS = ["제목", "메타 설명", "slug", "검색 의도", "겹침 구분", "훅", "도입부", "목차", "차별 포인트 배치", "FAQ",
            "CTA", "내부 링크", "역링크", "태그", "SNS 포인트", "대표 한마디", "갱신 조건", "쓰지 않을 것", "초안에 넘길 메모"]
NON_BODY_H2 = ["3行まとめ", "FAQ", "よくある質問", "SOURCES", "代表ヤンのひとこと", "まとめ"]
QUESTION_WORDS = ["とは", "なぜ", "違い", "対策", "確認", "方法", "原因", "被害", "対応", "使い方", "無料",
                  "料金", "できること", "注意点", "費用", "相場", "期間", "流れ", "手順", "やり方", "何", "いつ",
                  "どう", "どこ", "いくら", "必要", "大丈夫", "?", "？"]
FORMATS = ("문단", "번호 목록", "목록", "표", "상자")
FORBIDDEN = ["絶対", "100%安全", "最強", "神ツール", "革命的", "いかがでしたか", "大変なことに", "ずさん"]
COMMON_EN = {"wordpress", "php", "ai", "chatgpt", "google", "web", "vps", "https", "html"}
STOPWORDS = {"a", "an", "the", "of", "and", "or", "to", "in", "for", "on", "with", "how", "what", "is"}
PENDING = "◆ 실습 대기"
S_RE = re.compile(r"S\d+")


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s)).lower()


def width(s):
    """전각 기준 길이: 전각 1, 반각 0.5"""
    s = re.sub(r"\[S\d+(?:[,，、]\s*S?\d+)*\]", "", s)
    return sum(1 if unicodedata.east_asian_width(c) in "WFA" else 0.5 for c in s.strip())


def has_kw(text, kw):
    t = norm(text)
    return all(norm(tok) in t for tok in kw.split() if tok)


def is_question(kw):
    return any(w in kw for w in QUESTION_WORDS)


def front(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            k, sep, v = ln.partition(":")
            if sep:
                out[k.strip()] = v.strip()
    return out


def sections(text):
    out, cur = {}, None
    for ln in text.splitlines():
        m = re.match(r"^## (.+?)\s*$", ln)
        if m:
            cur = m.group(1).split("(")[0].strip()
            out[cur] = []
        elif cur:
            out[cur].append(ln)
    return out


def table(lines):
    rows = []
    for ln in lines:
        if ln.startswith("|") and not re.match(r"^\|[\s\-|:]+\|$", ln):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows[1:] if rows else []  # 머리 행 제외


def bullets(lines):
    return [l.strip()[2:].strip() for l in lines if l.strip().startswith("- ")]


def cta_buttons(root):
    """rules/common.md 「CTA 버튼」 표 → {CTA 이름: (버튼 문구, 링크)}"""
    p = root / "rules/common.md"
    if not p.exists():
        return {}
    t = p.read_text()
    m = re.search(r"^### CTA 버튼.*?\n(.*?)(?=^### |^## )", t, re.S | re.M)
    out = {}
    if m:
        for r in table(m.group(1).splitlines()):
            if len(r) >= 4:
                out[r[0]] = (r[2], r[3].split()[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--root", default=".")
    ap.add_argument("--verify-links", action="store_true",
                    help="역링크 대상 글을 실제로 가져와 「넣을 곳」의 H2가 그 글에 있는지 확인 (네트워크)")
    a = ap.parse_args()
    root = Path(a.root)
    text = Path(a.file).read_text()
    errs, warns = [], []
    E, W = errs.append, warns.append

    f = front(text)
    for k in FRONT:
        if k not in f:
            E(f"머리에 `{k}:` 없음")
    sec = sections(text)
    for s in SECTIONS:
        if s not in sec:
            E(f"절 「## {s}」 없음")
    if f.get("kind") == "개편" and "개편" not in sec:
        E("개편 글인데 「## 개편」 절 없음")
    if errs:
        return report(errs, warns)

    route, kind = f["route"], f["kind"]
    main_kw = f["main_keyword"]
    subs = [s.strip() for s in f["sub_keywords"].split("/") if s.strip()]
    events = [s.strip() for s in f["event_keywords"].split("/") if s.strip() and s.strip() != "-"]
    own_url = f"https://atatakaidigital.com/ja/blog/{f['slug']}"

    # 카드
    card_p = root / f["brief"]
    card = card_p.read_text() if card_p.exists() else ""
    if not card:
        E(f"카드 없음: {f['brief']}")
    cf = front(card)
    card_lines = card.splitlines()
    if cf.get("slug") and cf["slug"] != f["slug"]:
        E(f"slug가 카드와 다름: 카드 {cf['slug']} / 설계 {f['slug']}")
    if card and "D43" not in card and "상위 구성" not in card:
        E("카드에 D43 키워드 절(「키워드 (D43 갱신)」 또는 「상위 구성」)이 없음 → 먼저 키워드를 D43으로 갱신")
    card_kind = "개편" if (cf.get("kind", "").startswith("개편") or "업데이트" in cf.get("status", "")) else "새 글"
    if kind != card_kind:
        E(f"kind가 카드와 다름: 카드 {card_kind} / 설계 {kind}")
    card_trial = (cf.get("trial", "없음").split("|")[0].strip() or "없음")
    if f["trial"] != card_trial:
        E(f"trial이 카드와 다름: 카드 {card_trial} / 설계 {f['trial']}")
    m = re.search(r"^- 메인 키워드:\s*(.+)$", card, re.M)
    if m and norm(m.group(1)) != norm(main_kw):
        W(f"메인 키워드가 카드와 다름: 카드 「{m.group(1).strip()}」 / 설계 「{main_kw}」 (바꿨다면 카드에도 이유를)")
    m = re.search(r"cta:\s*\{주:\s*([^,}]+),\s*보조:\s*([^}]+)\}", card)
    if m and (m.group(1).strip() != f["cta_main"] or m.group(2).strip() != f["cta_sub"]):
        E(f"CTA가 카드와 다름: 카드 주 {m.group(1).strip()} / 보조 {m.group(2).strip()}")
    rep = cf.get("rep_comment", "없음")

    # 서브 키워드
    allkw = subs + events
    q = [s for s in subs if is_question(s)]
    for s in subs:
        if not is_question(s):
            E(f"서브 키워드 「{s}」는 질문형이 아님 — 사건 검색어면 event_keywords로 (속보만)")
    if route == "속보":
        if not (1 <= len(events) <= 2):
            W(f"속보 사건 검색어 {len(events)}개 (규칙: 1~2)")
        if len(q) < 2:
            E(f"속보 질문형 서브 키워드 {len(q)}개 (규칙: 2개 이상)")
    else:
        if events:
            E("일반 글에 event_keywords가 있음 (사건 검색어는 속보만)")
        if len(q) < 3:
            E(f"질문형 서브 키워드 {len(q)}개 (규칙: 3개 이상)")
    if len(allkw) > 5:
        W(f"서브 키워드 {len(allkw)}개 (규칙: 3~5)")

    # 기존 글
    posts = json.loads((root / "topics/existing_posts.json").read_text())["posts"]
    by_url = {p["url"].rstrip("/"): p for p in posts}
    others = [p for p in posts if p["url"].rstrip("/") != own_url]
    other_titles = {norm(p["title"]) for p in others}
    other_descs = {norm(p.get("description", "")) for p in others}
    if kind == "개편" and own_url not in by_url:
        E(f"개편 글인데 기존 글 목록에 {own_url} 없음 (slug는 바꾸지 않는다)")

    # 제목
    rows = table(sec["제목"])
    rec = [r for r in rows if "추천" in r[0]]
    if len(rows) < 3:
        E(f"제목 후보 {len(rows)}개 (규칙: 3개)")
    if len(rec) != 1:
        E(f"추천 제목이 {len(rec)}개 (규칙: 1개, 첫 칸에 「추천」)")
    for r in rows:
        if len(r) < 2:
            continue
        t, tag = r[1], r[0]
        w = width(t)
        if not 28 <= w <= 35:
            (E if "추천" in tag else W)(f"제목 {tag} 「{t}」 전각 {w:g}자 (규칙: 28~35)")
        if not has_kw(t, main_kw):
            (E if "추천" in tag else W)(f"제목 {tag}에 메인 키워드 「{main_kw}」 없음")
        else:
            pos = norm(t).find(norm(main_kw.split()[0]))
            if pos > 12:
                W(f"제목 {tag}: 메인 키워드가 앞쪽이 아님 ({pos}번째 글자)")
        if t.count("【") > 1:
            E(f"제목 {tag}: 【】 2개 이상")
        if norm(t) in other_titles:
            E(f"제목 {tag}: 다른 기존 글과 같은 제목")
    if route == "속보" and rec and events and not any(has_kw(rec[0][1], e) for e in events):
        W("추천 제목에 사건 검색어가 없음 — 첫 문단·「何が起きた？」 H2에는 꼭 넣는다")
    if kind == "개편" and rec and own_url in by_url and norm(rec[0][1]) != norm(by_url[own_url]["title"]):
        if "바꾸는 이유" not in "\n".join(sec["제목"]):
            E("개편 글 제목을 바꾸는데 「바꾸는 이유:」가 없음 (이미 순위가 있는 제목일 수 있다)")

    # 메타
    meta = " ".join(l for l in sec["메타 설명"] if l.strip() and not l.startswith("-")).strip()
    w = width(meta)
    if not 80 <= w <= 120:
        E(f"메타 설명 전각 {w:g}자 (규칙: 80~120)")
    if not has_kw(meta, main_kw):
        E("메타 설명에 메인 키워드 없음")
    if norm(meta) in other_descs:
        E("메타 설명이 다른 기존 글의 메타와 같음 (글마다 고유)")

    # slug
    sl = f["slug"]
    parts = sl.split("-")
    if not re.fullmatch(r"[a-z0-9_]+(-[a-z0-9_]+)*", sl):
        E(f"slug 형식 오류: {sl}")
    if kind != "개편":
        if not 3 <= len(parts) <= 5:
            W(f"slug 단어 {len(parts)}개 (규칙: 3~5) — 파일 이름이 바뀌므로 바꾸려면 사람에게 묻는다")
        if any(re.fullmatch(r"(19|20)\d\d", p) for p in parts) or STOPWORDS & set(parts):
            W(f"slug에 연도·불용어: {sl}")

    # 검색 의도
    intent = "\n".join(sec["검색 의도"])
    if not re.search(r"글 형식\s*:", intent):
        E("검색 의도에 「글 형식:」 없음 (가이드/목록/뉴스·해설 등)")
    if not re.search(r"근거\s*:", intent):
        E("검색 의도에 「근거:」 없음 (노트 「상위 10개 글 유형」 또는 카드 「상위 구성」)")

    # 겹침 구분: 메인 키워드가 들어간 기존 글
    overl = [p for p in others if has_kw(p["title"], main_kw)]
    ov_txt = "\n".join(sec["겹침 구분"])
    for p in overl:
        if p["slug"] not in ov_txt:
            W(f"메인 키워드 「{main_kw}」가 기존 글 {p['slug']} 제목에도 있음 — 「겹침 구분」에 어떻게 구분하는지 적는다")
    if kind == "개편" and "역할" not in ov_txt:
        W("개편 글: 같은 키워드를 다투는 우리 글의 역할 나누기를 「겹침 구분」에 적는다")

    # 목차
    note_p = root / f["research"]
    note = note_p.read_text() if note_p.exists() else ""
    if not note:
        E(f"조사 노트 없음: {f['research']}")
    note_ids = set(re.findall(r"^\| (S\d+) \|", note, re.M))
    trial_sec = re.search(r"^## 직접 써 본 결과[^\n]*\n(.*?)(?=^## |\Z)", note, re.S | re.M)
    trial_pending = f["trial"] == "사람" and trial_sec and "◆" in trial_sec.group(1)
    toc = table(sec["목차"])
    # 칸: # | 라벨 | H2 | 키워드 | 직답 메모 | 쓸 사실 | 형식 | 분량
    h2s = [r for r in toc if len(r) >= 8 and "SOURCES" not in r[2]]
    body = [r for r in h2s if not any(n in r[2] for n in NON_BODY_H2)]
    if not 4 <= len(h2s) <= 8:
        E(f"H2 {len(h2s)}개 (SOURCES 제외, 규칙: 4~8)")
    used_s, total, with_kw = set(), 0, 0
    answers = []
    for r in toc:
        if len(r) < 8:
            E(f"목차 행 칸 수 부족 (8칸: #·라벨·H2·키워드·직답·쓸 사실·형식·분량): {r[:3]}")
            continue
        no, label, h2, kws, ans, facts, fmt, length = r[:8]
        pending = PENDING in ans or PENDING in facts
        if not re.search(r"[A-Za-z]", label):
            W(f"{no} 영어 라벨 없음")
        if "代表ヤン" in h2 and rep in ("없음", ""):
            E("대표 한마디가 없는데 「代表ヤンのひとこと」 칸이 있음 (철칙 1)")
        if "使ってみた" in h2 and f["trial"] == "없음":
            E(f"{no} 실습 기록이 없는 글(trial: 없음)에 「使ってみた」 칸 (철칙 1)")
        kl = [k.strip() for k in kws.split("/") if k.strip() and k.strip() != "-"]
        for k in kl:
            if k not in allkw and norm(k) != norm(main_kw):
                W(f"{no} 키워드 「{k}」가 설계 키워드 목록에 없음")
            if not has_kw(h2, k):
                E(f"{no} H2 「{h2}」에 키워드 「{k}」의 단어가 다 들어 있지 않음")
            if k in events and "何が起き" not in h2:
                W(f"{no} 사건 검색어 「{k}」는 「何が起きた？」 H2에 녹인다 (D44)")
        if r in body:
            if kl:
                with_kw += 1
            if not is_question(h2):
                W(f"{no} H2 「{h2}」가 질문형이 아님")
            if not any(x in fmt for x in FORMATS):
                E(f"{no} 형식 칸 「{fmt}」 — 문단/번호 목록/표/상자 중에서")
            if pending:
                pass
            elif ans in ("", "-"):
                E(f"{no} 직답 메모 없음")
            else:
                answers.append(ans)
                aw = width(ans)
                if not 40 <= aw <= 80:
                    E(f"{no} 직답 전각 {aw:g}자 (규칙: 40~80)")
        ids = set(S_RE.findall(facts))
        used_s |= ids
        for i in ids - note_ids:
            E(f"{no} 쓸 사실 {i}가 조사 노트에 없음")
        if r in body and not ids and not pending and "EXP" not in facts:
            E(f"{no} 쓸 사실이 없음 (S번호 또는 실습 기록)")
        mm = re.search(r"\d+", length.replace(",", ""))
        total += int(mm.group()) if mm else 0
    if body and with_kw * 2 < len(body):
        E(f"키워드가 든 본문 H2 {with_kw}/{len(body)} (규칙: 절반 이상)")
    rng = re.findall(r"\d+", f["length"].replace(",", ""))
    if len(rng) == 2 and not int(rng[0]) <= total <= int(rng[1]):
        E(f"분량 합계 {total}자가 범위 {f['length']} 밖")
    if events and not any(has_kw(r[2], ev) for ev in events for r in toc if len(r) >= 3):
        E("사건 검색어가 어느 H2에도 없음 (「何が起きた？」 H2에 녹인다, D44)")
    if route == "속보" and not any("3行まとめ" in r[2] for r in toc if len(r) >= 3):
        W("속보인데 「3行まとめ」 칸이 없음")
    # 「とは」 정의
    for k in [main_kw] + subs:
        if "とは" in k:
            term = k.replace("とは", "").strip().split()[0]
            if not any("とは、" in x for x in answers):
                E(f"「{k}」: 직답 메모 중 하나는 「{term}とは、〜です。」 정의 문장으로 (AEO)")
            break
    # 실습 대기
    if trial_pending:
        if not any(PENDING in " ".join(r) for r in toc):
            E(f"trial: 사람이고 노트에 실습 결과가 없음 → 「使ってみた」 행의 직답·쓸 사실에 「{PENDING}」")
        if cf.get("status", "").split("(")[0].strip() not in ("실습 대기", "설계 대기"):
            W("실습 결과가 없는데 카드가 「실습 대기」가 아님 — 설계 후 카드를 「실습 대기」로")
    elif any(PENDING in " ".join(r) for r in toc):
        E(f"노트에 실습 결과가 있는데 「{PENDING}」 행이 남아 있음 — 결과로 채운다")

    # 도입부
    intro = "\n".join(sec["도입부"])
    if "200" not in intro:
        W("도입부에 「첫 문단 200자 이내」 메모가 없음")
    if not has_kw(intro, main_kw):
        E(f"도입부 메모에 메인 키워드 「{main_kw}」 없음 (첫 문단 200자 이내에 넣는다)")
    for ev in events:
        if not has_kw(intro, ev) and not any(has_kw(intro, t) for t in ev.split()[-1:]):
            E(f"도입부 메모에 사건 검색어 「{ev}」 없음")

    # 차별 포인트 배치
    dm = re.search(r"^### 차별 포인트\s*\n(.*?)(?=^## |^### |\Z)", note, re.S | re.M)
    n_diff = len(re.findall(r"^\s*\d+\.", dm.group(1), re.M)) if dm else 0
    drows = table(sec["차별 포인트 배치"])
    if n_diff and len(drows) < n_diff:
        E(f"노트 차별 포인트 {n_diff}개 중 배치한 것 {len(drows)}개 — 모두 섹션 번호를 정한다 (안 쓰면 이유)")
    toc_nos = {r[0] for r in toc if r}
    for r in drows:
        if len(r) >= 2 and r[1] not in toc_nos and "안 씀" not in r[1]:
            E(f"차별 포인트 배치 「{r[0][:20]}」의 섹션 「{r[1]}」이 목차에 없음")
    if route != "속보" and "경쟁 글 공통 핵심" not in "\n".join(sec["차별 포인트 배치"]):
        W("일반 글: 「경쟁 글 공통 핵심:」(경쟁 글이 모두 다루는 것)이 목차에 있는지 적는다")

    # FAQ
    faq = table(sec["FAQ"])
    want = (2, 2) if route == "속보" else (3, 5)
    if not want[0] <= len(faq) <= want[1]:
        W(f"FAQ {len(faq)}개 (규칙: {want[0]}~{want[1]})")
    for r in faq:
        if len(r) >= 2:
            src = r[1].split("(")[0].strip()
            if not src or src == "-":
                E(f"FAQ 「{r[0]}」 근거 검색어 없음 (실제 검색 질문만)")
            else:
                if not any(has_kw(ln, src) for ln in card_lines):  # 카드는 「php 脆弱性 cve / パッチ」처럼 줄여 적음
                    E(f"FAQ 근거 검색어 「{src}」가 카드에 기록된 검색어가 아님 — 실제로 확인한 검색어만")
                if not has_kw(r[0], src):
                    E(f"FAQ 질문 「{r[0]}」에 근거 검색어 「{src}」의 단어가 다 들어 있지 않음 (검색 질문 그대로)")
        ids = set(S_RE.findall(" ".join(r)))
        used_s |= ids
        for i in ids - note_ids:
            E(f"FAQ 쓸 사실 {i}가 조사 노트에 없음")

    # CTA
    buttons = cta_buttons(root)
    cta = table(sec["CTA"])
    if not cta:
        E("CTA 행 없음")
    # 칸: 위치 | 종류 | 버튼 문구 | 링크 | 메모
    names = []
    for r in cta:
        if len(r) < 4:
            E(f"CTA 행 칸 수 부족 (위치·종류·버튼 문구·링크·메모): {r[:2]}")
            continue
        name = r[1].split("(")[0].strip()
        names.append(name)
        if name in buttons:
            btn, link = buttons[name]
            if r[2] != btn:
                E(f"CTA 「{name}」 버튼 문구가 common.md 표와 다름: 「{r[2]}」 → 「{btn}」")
            if link.startswith("http") and r[3].rstrip("/") != link.rstrip("/"):
                E(f"CTA 「{name}」 링크가 common.md 표와 다름: {r[3]} → {link}")
        elif buttons:
            E(f"CTA 「{name}」가 common.md 「CTA 버튼」 표에 없음")
    for need in (f["cta_main"], f["cta_sub"]):
        if need not in names:
            E(f"CTA 「{need}」가 CTA 표에 없음")
    if route == "속보" and any("끝" not in r[0] for r in cta):
        E("속보는 CTA를 글 끝에만 둔다")
    if route != "속보" and not any("중간" in r[0] for r in cta):
        W("일반 글인데 본문 중간 CTA가 없음 (판정표·체크리스트 직후)")

    # 내부 링크
    links = table(sec["내부 링크"])
    # 본문에 들어갈 칸만 (겹침 구분·쓰지 않을 것 등 메모 절은 빼고)
    text_n = norm(" ".join("\n".join(sec[k]) for k in ("제목", "메타 설명", "훅", "도입부", "목차", "FAQ")))
    if not 3 <= len(links) <= 4:
        W(f"내부 링크 {len(links)}개 (규칙: 같은 축 2~3 + 기둥 1)")
    if sum(1 for r in links if len(r) > 3 and "기둥" in r[3]) != 1:
        E("기둥 글이 1개가 아님 (넷째 칸에 「기둥」)")
    for r in links:
        if len(r) < 4:
            E(f"내부 링크 행 칸 수 부족: {r}")
            continue
        u = r[1].strip("<>").rstrip("/")
        if u == own_url:
            E("내부 링크에 자기 글")
        elif u not in by_url:
            E(f"내부 링크 URL이 기존 글 목록에 없음: {u}")
        else:
            pp = by_url[u]
            nm = {w_ for w_ in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", pp["title"] + " " + pp.get("description", ""))
                  if norm(w_) not in text_n and w_.lower() not in COMMON_EN}
            memo = r[4] if len(r) > 4 else ""
            if nm and "확인" not in memo:
                W(f"내부 링크 {u.rsplit('/', 1)[-1]}: 이 글에 없는 이름 {sorted(nm)} — 다른 사건용 글이면 앵커에 밝히거나 바꾼다. 맞으면 메모 칸에 「확인: …」")
        if "こちら" in r[2] or width(r[2]) < 6:
            E(f"앵커 텍스트가 내용을 드러내지 않음: 「{r[2]}」")

    # 역링크 (발행 후 기존 글에서 새 글로)
    back = table(sec["역링크"])
    # 칸: 기존 글 URL | 넣을 곳 | 앵커 텍스트
    if len(back) < 2:
        E(f"역링크 {len(back)}개 (규칙: 기존 관련 글 2개 이상에서 이 글로)")
    for r in back:
        if len(r) < 3:
            E(f"역링크 행 칸 수 부족 (기존 글 URL·넣을 곳·앵커): {r}")
            continue
        u = r[0].strip("<>").rstrip("/")
        if u == own_url:
            E("역링크에 자기 글")
        elif u not in by_url:
            E(f"역링크 URL이 기존 글 목록에 없음: {u}")
        if "こちら" in r[2] or width(r[2]) < 6:
            E(f"역링크 앵커 텍스트가 내용을 드러내지 않음: 「{r[2]}」")

    if a.verify_links and back:
        verify_backlinks(back, root, E)

    # 태그
    tags = "\n".join(sec["태그"])
    axis = cf.get("axis", "")
    m = re.search(r"기본\s*:\s*(\S+)", tags)
    if not m or (axis and m.group(1) != axis):
        E(f"태그 「기본: {axis or '(주제 축)'}」 — 기본 태그는 카드의 주제 축")
    m = re.search(r"보조\s*:\s*(.+)", tags)
    if not m or m.group(1).strip() != f["type"]:
        E(f"태그 「보조: {f['type']}」 — 보조 태그는 글 종류")

    # 갱신 조건
    upd = bullets(sec["갱신 조건"])
    if route == "속보" and not [u for u in upd if u != "-"]:
        E("속보인데 「갱신 조건」이 비어 있음 — 노트 「아직 확인하지 못한 사항」 중 나오면 고칠 것")

    # 개편
    if kind == "개편":
        ch = table(sec["개편"])
        if not any("바뀜" in " ".join(r) or "고침" in " ".join(r) for r in ch):
            E("개편 표에 「바뀜」 행이 없음 (바뀌는 섹션 / 그대로 두는 섹션)")
        if "업데이트일" not in "\n".join(sec["개편"]):
            E("개편 절에 「업데이트일」 메모 없음 (의미 있는 수정이면 갱신)")
        if "기존 글에서 낡은 사실" in note and not re.search(r"S\d+", "\n".join(sec["개편"])):
            W("개편: 노트 「기존 글에서 낡은 사실」의 S번호를 개편 표에 연결한다")

    # SNS
    sns = "\n".join(sec["SNS 포인트"])
    for k in ("수치", "의견", "질문"):
        if not re.search(rf"^- {k}\s*:", sns, re.M):
            E(f"SNS 포인트 「{k}」 없음")
    m = re.search(r"^- 수치\s*:(.+)$", sns, re.M)
    if m and not S_RE.search(m.group(1)) and PENDING not in m.group(1):
        E("SNS 수치에 S번호 없음")
    m = re.search(r"^- 의견\s*:(.+)$", sns, re.M)
    if m and rep in ("없음", "") and ("ヤン" in m.group(1) or "대표" in m.group(1)):
        E("대표 한마디가 없는데 SNS 의견이 대표 의견 (철칙 1)")

    # 대표 한마디
    if rep in ("없음", "") and "없음" not in "\n".join(sec["대표 한마디"]):
        E("카드 rep_comment가 없음인데 설계안 「대표 한마디」 절이 「없음」이 아님")

    # 노트의 미확인 사항 → 쓰지 않을 것
    if "아직 확인하지 못한 사항" in note and not bullets(sec["쓰지 않을 것"]):
        W("「쓰지 않을 것」이 비어 있음 — 노트 「아직 확인하지 못한 사항」을 옮긴다")

    # 판 번호·범위
    memo = "\n".join(sec["초안에 넘길 메모"])
    jp_fields = ([r[1] for r in rows if len(r) > 1] + [meta] + [r[2] + " " + r[4] for r in toc if len(r) >= 5]
                 + [" ".join(r) for r in faq] + [sns])
    scope_txt = " ".join(jp_fields + [memo])
    note_n = unicodedata.normalize("NFKC", note)
    for v in sorted(set(re.findall(r"(?<![\d.])\d+\.\d+(?:\.\d+)?(?![\d.])", unicodedata.normalize("NFKC", scope_txt)))):
        if v not in note_n:
            E(f"판 번호 「{v}」가 조사 노트에 없음")
    for mm in re.finditer(r"\d+(?:\.\d+)*\s*系?(以前|以降|未満|より古い|すべて)", scope_txt):
        W(f"범위 표현 「{mm.group(0)}」 — S번호 원문의 범위와 같은지 확인 (예: 노트가 8.1만 말하면 「8.1系以前」은 넓힘)")

    # 금지 표현 (일본어 칸)
    jp = " ".join(jp_fields)
    for w_ in FORBIDDEN:
        if w_ in jp:
            E(f"금지 표현 「{w_}」")
    for w_, n in (("と言えるでしょう", 2), ("することが重要です", 2), ("さまざまな", 3)):
        if jp.count(w_) >= n:
            W(f"「{w_}」 {jp.count(w_)}회 반복")

    print(f"쓸 사실 {len(used_s)}개 / 노트 사실 {len(note_ids)}개 / H2 {len(h2s)}개 / 분량 합계 {total}자 / 역링크 {len(back)}개")
    return report(errs, warns)


def verify_backlinks(back, root, E):
    """역링크 「넣을 곳」에 적은 「H2」가 대상 글에 실제로 있는지 — fetch_page.py로 가져와 본문에서 찾는다"""
    import subprocess
    import tempfile
    urls = [r[0].strip("<>") for r in back if len(r) >= 3]
    with tempfile.TemporaryDirectory() as d:
        fp = root / ".claude/skills/blog-research/fetch_page.py"
        subprocess.run([sys.executable, "-I", str(fp), "--out-dir", d] + urls, capture_output=True, timeout=180)
        idx = json.loads((Path(d) / "index.json").read_text()) if (Path(d) / "index.json").exists() else []
        pages = {}
        for e_ in idx:
            if e_.get("file"):
                body = (Path(d) / e_["file"]).read_text().split("=== LINKS")[0]
                pages[e_["url"].rstrip("/")] = {norm(ln) for ln in body.splitlines() if ln.strip()}  # 줄 단위 (소제목은 한 줄)
    for r in back:
        if len(r) < 3:
            continue
        u = r[0].strip("<>").rstrip("/")
        heads = re.findall(r"「([^」]+)」", r[1])
        if u not in pages:
            E(f"역링크 대상 글을 가져오지 못함: {u}")
        elif not heads:
            E(f"역링크 {u.rsplit('/', 1)[-1]}: 넣을 곳에 실제 H2를 「」로 적는다")
        else:
            for h in heads:
                if norm(h) not in pages[u]:
                    E(f"역링크 {u.rsplit('/', 1)[-1]}: 「{h}」와 같은 소제목 줄이 그 글에 없음 (짐작한 위치이거나 글이 바뀜) — H2를 한 줄 그대로 적는다")


def report(errs, warns):
    for e in errs:
        print("❌ " + e)
    for w in warns:
        print("⚠ " + w)
    print("통과" if not errs else f"오류 {len(errs)}건")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
