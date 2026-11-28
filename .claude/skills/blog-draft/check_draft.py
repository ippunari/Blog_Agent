#!/usr/bin/env python3
"""blog-draft: 초안 점검 (기본은 읽기 전용).

drafts/<slug>.md 를 설계안·조사 노트·규칙과 맞춰 본다.
 1. 머리(front matter), 필자 ヒカリちゃん, 제목·메타가 설계안과 같은지
 2. H2가 설계안 목차와 같은 순서·같은 문구인지, H2 바로 뒤 굵은 직답(40~80자)
 3. 표시: [S번호]가 노트에 있는지 / 섹션의 「쓸 사실」 밖이면 경고 / [EXP]·[OP]는 근거가 있을 때만 / [?] 목록
 4. 철칙 1: 실습 기록 없이 「試しました」 등, 대표 한마디 없이 대표 의견·「代表ヤンのひとこと」
    사람 실습 결과 전(trial: 사람 + 노트 「◆」)이면 「使ってみた」 섹션은 :::trial 자리 표시 상자 하나 (D79)
 5. 금지 표현 (common.md 4장, voice-hikari.md 5장)
 6. 표기: 전각 숫자, 날짜 형식, 판 번호·날짜가 노트에 있는지, 「〇系以前」 범위 넓힘
 7. 첫 문단 200자 안에 메인 키워드(속보는 사건 검색어도), 「とは」 정의 문장
 8. CTA 버튼 문구·링크, 내부 링크 URL·앵커가 설계안 그대로, FAQ 질문이 H3로 있는지
 9. 분량: 하한 이상·상한 90% 이하 (표시·Markdown 기호·SOURCES·초안 메모 제외), 부품 분량
14. 글 뼈대 순서·필수 상자, 차별 포인트 필수, 문단 독립성, 대책 없는 경고 문단, 용어집에 없는 전문어 수 (D47)
15. 그림 표시 <!-- 그림 N --> 가 설계안 「그림 자리」 N번째 행의 섹션·사실 옆에 있는지 (D96·D97)
16. 구조 되풀이 경고: 문장 시작·섹션 첫 이음말·목록 길이·문단 길이·글 자체를 말하는 문장 (D97, 경고만)
17. 「**제목**：설명」 목록·읽점이 든 괄호 경고, 노트 사실에 나온 말은 전문어로 세지 않음 (D98)
10. 상자 형식, 「ヒカリちゃんの案内」 첫 줄, 짧은 인용 2개까지, 원문(일본어) 25자 이상 같은 부분이 인용 밖에 있는지
11. 용어: 사이트 용어집의 괄호 풀이가 첫 등장에 있는지, 피하는 말 (rules/glossary.md)
12. 문체 경고: 80자 넘는 문장, 「！」, 「〜ね/〜よ」 끝맺음, 표시 없는 사실 문장 후보
13. SOURCES가 본문에서 쓴 S번호와 같은지 (--write-sources 로 노트에서 채운다)

사용법:
  python3 -I check_draft.py drafts/<slug>.md [--root .] [--write-sources]
종료 코드 0 = 통과(경고만 있을 수 있음), 1 = 오류
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "blog-outline"))
from check_outline import front, sections, table, bullets, norm, width, has_kw  # noqa: E402

FRONT = ["slug", "brief", "outline", "research", "route", "kind", "type", "author", "trial", "length",
         "main_keyword", "sub_keywords", "event_keywords", "cta_main", "cta_sub", "rep_comment", "meta",
         "created_at"]
BOX_TYPES = {"box", "guide", "matome", "note", "rep", "cta", "trial"}   # trial = 사람 실습 자리 표시 (D79)
NO_ANSWER_H2 = ("3行まとめ", "FAQ", "よくある質問", "SOURCES")
FORBIDDEN = ["絶対", "100%安全", "100％安全", "最強", "神ツール", "革命的", "いかがでしたか", "大変なことに",
             "ずさん", "手遅れ", "今すぐ対策しないと", "なのだ"]
REPEAT_LIMIT = {"と言えるでしょう": 1, "することが重要です": 1, "さまざまな": 2}
EXP_PHRASES = ["私たちの経験", "使ってきた感覚", "試してみました", "試しました", "試したところ", "実際に使ってみると",
               "使ってみました", "使ってみた"]
REP_PHRASES = ["代表ヤン", "代表は", "ヤンは", "ヤンの"]
AVOID = {"ウェブサイト": "ホームページ / サイト", "Webサイト": "ホームページ / サイト", "セキュリティホール": "脆弱性",
         "ジェネレーティブAI": "生成AI", "ダッシュボード": "管理画面", "コンソール": "管理画面",
         "コンフィグ": "設定", "ハッキング": "不正アクセス", "PII": "個人情報"}
KW_ONLY = {"パッチ": "修正版", "アップデート": "更新"}
TAG_RE = re.compile(r"\[(S\d+|EXP|OP|\?)\]")
S_RE = re.compile(r"S\d+")
ZEN_DIGIT = re.compile(r"[０-９]")
# 글 뼈대·부품 분량 (rules/voice-hikari.md 2장, D47): 이름 → (속보 범위, 일반 범위). None = 그 경로엔 없음
PARTS = {"리드": ((100, 200), (100, 200)), "3行まとめ": ((100, 150), (100, 150)), "こんな方に": (None, (60, 100)),
         "この記事でわかること": ((50, 80), (60, 100)), "ヒカリちゃんの案内": ((50, 100), (100, 200)),
         "ヒカリちゃんのまとめ": ((20, 50), (30, 60)), "cta": ((40, 80), (40, 80)), "cta_sub": ((15, 60), (15, 60))}
DRAFT_RATIO = 0.9
# 전문어로 세지 않는 말: 심각도 이름(공식 표기 그대로 쓴다)·표기 규칙의 시간대 (D59)
NOT_JARGON = {"Critical", "High", "Medium", "Moderate", "Low", "UTC", "JST", "URL", "PDF", "IT", "AI"}
# D78: 나라·지역 이름은 전문어가 아니다
PLACE_KATA = {"アメリカ", "イギリス", "ドイツ", "フランス", "カナダ", "オーストラリア", "インド", "ロシア", "ヨーロッパ", "アジア",
              "シンガポール", "ブラジル", "イタリア", "スペイン", "オランダ", "スイス", "アフリカ"}
TERM_CAP = {"속보": 3, "일반": 6}
DEICTIC = re.compile(r"^(この|その|あの|上の|下の|次の表|これは|それは|これら|そこで|こちら)")
WARN_WORDS = re.compile(r"攻撃|悪用|漏えい|漏洩|被害|乗っ取|侵入|不正アクセス")
ACTION_WORDS = re.compile(r"確かめ|確認|更新|相談|設定|変更|対策|見直|聞い|聞き|チェック|バックアップ|切り替え|移行|止め")
COMMON_KATA = {"ホームページ", "サーバー", "レンタルサーバー", "メール", "パスワード", "セキュリティ", "サポート", "バージョン",
               "サイト", "メニュー", "ツール", "チェック", "プラン", "データ", "ファイル", "アカウント", "ログイン", "サービス",
               "システム", "ニュース", "リスト", "ページ", "スマホ", "パソコン", "インターネット", "アップデート", "アプリ",
               "ソフトウェア", "プログラム", "コード", "テスト", "メッセージ", "ブラウザー", "ブログ", "サイトヘルス", "タブ",
               "クリック", "ボタン", "スケジュール", "カレンダー", "トラブル", "ポイント", "ケース", "ステップ", "コスト",
               "ニーズ", "メーカー", "リスク", "イメージ", "ヒカリ", "ヒカリちゃん", "ホスティング", "ホスティングサービス", "チェックリスト", "マニュアル",
               # D97: 앱 설치 글에서 빼기 어려운 PC 일상어 (2026-11-28 Claude 아티팩트 글에서 상한 6을 혼자 넘음)
               "インストール", "アンインストール", "アイコン", "ウィンドウ", "オンライン", "サインイン", "ショートカット", "スタートメニュー", "タイトル"}


FIG_RULE_FROM = "2026-11-28"   # D96 설계안 「그림 자리」가 생긴 날 — 그 전 설계안은 그림 표시를 보지 않는다
# D97 ② 구조 되풀이 (경고만): 글 자체를 말하는 문장 시작 — 「について解説します」 등 리드 쪽은 check_polish(7-5)가 본다
TALK_ABOUT = re.compile(r"^(重要なのは|大切なのは|ポイントは|注目すべきは|ここでは|ここからは|本記事では|この記事では)")
LIST_SD_MIN = 3.0    # 4항목 이상 목록의 글자 수 표준편차가 이보다 작으면 경고
PARA_CV_MIN = 0.2    # 본문 문단 6개 이상의 길이 변동계수가 이보다 작으면 경고


def block_after(lines, i):
    """i행 표시 주석 바로 아래 블록 (빈 줄·다른 주석은 건너뛰고, 빈 줄 없는 연속 줄)"""
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("<!--")):
        j += 1
    blk = []
    while j < len(lines) and lines[j].strip() and not lines[j].startswith(("## ", "<!--")):
        blk.append(lines[j]); j += 1
    return blk


def strip_tags(s):
    return TAG_RE.sub("", s)


def plain(s):
    """Markdown 기호·링크 URL·주석·표시를 뺀 읽는 글자"""
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", s)
    s = strip_tags(s)
    s = re.sub(r"^\s*(#+|>|-|\d+\.(?!\d)|:::.*$)\s*", "", s)
    s = s.replace("**", "").replace("|", " ")
    s = re.sub(r"^[\s\-:]+$", "", s)
    return s.strip()


def split_draft(text):
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    m = re.search(r"^## SOURCES\s*$", body, re.M)
    n = re.search(r"^## 초안 메모.*$", body, re.M)
    main = body[:m.start()] if m else body
    src = body[m.end():n.start() if n else len(body)] if m else ""
    memo = body[n.end():] if n else ""
    return main, src, memo


def note_facts(note):
    sec = sections(note)
    facts = {}
    for r in table(sec.get("핵심 사실", [])):
        if r and S_RE.fullmatch(r[0]):
            facts[r[0]] = r
    exp = "\n".join(sec.get("직접 써 본 결과", [])).strip()
    has_exp = bool(exp) and not re.search(r"해당 없음|없음 \(trial", exp) and "◆" not in exp
    return facts, has_exp


SENT_RE = re.compile(r".+?[。？！](?:\s*\[(?:S\d+|EXP|OP|\?)\])*|.+$")


def sentences(line):
    """문장 끝 「。」 뒤에 붙은 표시까지 한 문장으로 자른다"""
    return [x for x in SENT_RE.findall(line) if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--root", default=".")
    ap.add_argument("--write-sources", action="store_true", help="본문에서 쓴 S번호로 SOURCES 절을 노트에서 채운다")
    a = ap.parse_args()
    root = Path(a.root)
    path = Path(a.file)
    text = path.read_text()
    errs, warns = [], []
    E, W = errs.append, warns.append

    f = front(text)
    for k in FRONT:
        if k not in f:
            E(f"머리에 `{k}:` 없음")
    if errs:
        return report(errs, warns)
    if f["author"] != "ヒカリちゃん":
        E("author는 ヒカリちゃん (D38, D46)")
    if path.stem != f["slug"]:
        E(f"파일 이름({path.stem})과 slug({f['slug']})가 다름")
    op = root / f["outline"]
    npth = root / f["research"]
    if not op.exists() or not npth.exists():
        E("설계안 또는 조사 노트 파일이 없음")
        return report(errs, warns)
    outline, note = op.read_text(), npth.read_text()
    of, osec = front(outline), sections(outline)
    facts, has_exp = note_facts(note)
    rep = f["rep_comment"] not in ("없음", "")
    # D79: 사람 실습 결과 전이면 「使ってみた」 섹션은 자리 표시(:::trial)로 두고 업로드까지 간다
    trial_pending = f["trial"].split("|")[0].strip() == "사람" and not has_exp
    for k in ("slug", "route", "type", "trial", "main_keyword", "sub_keywords", "event_keywords", "cta_main",
              "cta_sub", "rep_comment", "length"):
        if of.get(k, "").strip() != f[k].strip():
            E(f"머리 `{k}:`가 설계안과 다름 (설계안: {of.get(k)})")

    main_txt, src_txt, memo = split_draft(text)
    OFF = text[:text.find(main_txt)].count("\n") if main_txt in text else 0   # 메시지 줄 번호 = 파일 줄 번호 (D54)
    lines = main_txt.splitlines()

    # --- 제목·메타
    titles = [l[2:].strip() for l in lines if l.startswith("# ")]
    rec = next((r[1] for r in table(osec.get("제목", [])) if "추천" in r[0]), "")
    if len(titles) != 1:
        E(f"제목(# 줄)은 1개 — 지금 {len(titles)}개")
    elif rec and titles[0] != rec:
        E(f"제목이 설계안 추천 제목과 다름: 「{rec}」")
    ometa = " ".join(l.strip() for l in osec.get("메타 설명", []) if l.strip() and not l.strip().startswith("- "))
    if ometa and norm(f["meta"]) != norm(ometa):
        W("머리 `meta:`가 설계안 메타 설명과 다름 — 바꿨으면 이유를 초안 메모에")

    # --- 상자
    open_box, boxes, in_box = None, [], [False] * len(lines)
    for i, ln in enumerate(lines):
        if ln.startswith(":::"):
            t = ln[3:].strip()
            if open_box is None:
                typ = t.split()[0] if t else ""
                if typ not in BOX_TYPES:
                    E(f"{i+1+OFF}행 상자 종류 「{typ}」 — {sorted(BOX_TYPES)} 중 하나")
                open_box = {"type": typ, "label": t[len(typ):].strip(), "start": i, "lines": []}
            else:
                if t:
                    E(f"{i+1+OFF}행: 상자 「{open_box['label']}」가 닫히기 전에 새 상자 — 「:::」 한 줄로 닫는다")
                boxes.append(open_box)
                open_box = None
            in_box[i] = True
        elif open_box is not None:
            open_box["lines"].append(ln)
            in_box[i] = True
    if open_box is not None:
        E(f"상자 「{open_box['label']}」가 닫히지 않음")
    guide = [b for b in boxes if b["type"] == "guide"]
    if len(guide) != 1:
        E("「ヒカリちゃんの案内」 상자(:::guide)는 1개")
    else:
        first = next((l.strip() for l in guide[0]["lines"] if l.strip()), "")
        if first != "こんにちは、ヒカリです。":
            E("案内 상자 첫 줄은 「こんにちは、ヒカリです。」 (voice-hikari.md 2-1)")
    if [b for b in boxes if b["type"] == "rep"] and not rep:
        E("대표 한마디가 없는데 「代表ヤンのひとこと」 상자가 있음 (철칙 1)")
    if rep and not [b for b in boxes if b["type"] == "rep"]:
        E("대표 한마디가 있는데 :::rep 상자가 없음")
    trial_boxes = [b for b in boxes if b["type"] == "trial"]
    trial_lines = {i for b in trial_boxes for i in range(b["start"], b["start"] + len(b["lines"]) + 2)}
    if trial_boxes and not trial_pending:
        E("실습 자리 표시(:::trial)가 남아 있음 — 실습 결과가 노트에 있거나 trial이 사람이 아니면 섹션을 채우거나 뺀다 (D79)")
    if trial_pending and len(trial_boxes) != 1:
        E(f"trial: 사람이고 실습 결과 전 — 「使ってみた」 섹션에 :::trial 자리 표시 상자 1개 (지금 {len(trial_boxes)}개, D79)")

    # --- H2
    toc = [r for r in table(osec.get("목차", [])) if len(r) >= 8]
    want = [r[2] for r in toc]
    got = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    got_h = [h for _, h in got] + ["SOURCES"]
    if got_h != want:
        E("H2가 설계안 목차와 다름\n   설계안: " + " / ".join(want) + "\n   초안:   " + " / ".join(got_h))
    sec_ranges = []
    for k, (i, h) in enumerate(got):
        end = got[k + 1][0] if k + 1 < len(got) else len(lines)
        sec_ranges.append((h, i, end))
    pending_h2 = {r[2] for r in toc if "◆" in " ".join(r[3:6])} if trial_pending else set()
    for b in trial_boxes:
        sec = next((h for h, i, end in sec_ranges if i < b["start"] < end), None)
        if trial_pending and sec not in pending_h2:
            E(f"실습 자리 표시(:::trial)는 설계안 「◆ 실습 대기」 행의 H2 안에 — 지금 「{sec}」 (D79)")
    # 글 뼈대 순서 (voice-hikari.md 2장, D47): 리드 → 3行まとめ → (こんな方に) → わかること → 案内 → 첫 H2
    route = f["route"]
    _n0 = sum(len(re.sub(r"\s", "", plain(l))) for l in lines if not l.startswith("# ") and not l.startswith("<!--"))
    short = route == "속보" and _n0 <= 3000   # 짧은 속보(초안 분량 3,000자 이하)만 속보 부품·용어 기준 (D59, D69)
    ri = 0 if short else 1
    first_h2_i = got[0][0] if got else len(lines)
    lead_i = next((i for i, l in enumerate(lines[:first_h2_i]) if l.strip() and not in_box[i]
                   and not l.startswith(("#", "<!--", ">", "|"))), None)
    order = [("리드", lead_i)]
    for name in ("3行まとめ", "こんな方に", "この記事でわかること", "ヒカリちゃんの案内"):
        if PARTS[name][ri] is None:
            if any(b["label"].startswith(name) for b in boxes):
                W(f"속보에는 「{name}」 상자를 두지 않는다 (voice-hikari.md 2장)")
            continue
        bx = next((b for b in boxes if b["label"].startswith(name)), None)
        order.append((name, bx["start"] if bx else None))
    for name, pos in order:
        if pos is None:
            E(f"글 뼈대: 「{name}」가 없음 (voice-hikari.md 2장)")
        elif pos > first_h2_i:
            E(f"글 뼈대: 「{name}」는 첫 H2보다 앞에 (voice-hikari.md 2장)")
    seq = [p for _, p in order if p is not None]
    if seq != sorted(seq):
        E("글 뼈대 순서가 다름 — 리드 → 3行まとめ → (こんな方に) → この記事でわかること → ヒカリちゃんの案内 (voice-hikari.md 2장)")
    if any(h.startswith("3行まとめ") for h in got_h):
        E("「3行まとめ」는 H2가 아니라 :::box 상자 (D47)")
    # 부품 분량 (경고)
    def blen(ls):
        return sum(len(re.sub(r"\s", "", plain(x))) for x in ls)
    if lead_i is not None:
        rg = PARTS["리드"][ri]
        n_lead = len(re.sub(r"\s", "", plain(lines[lead_i])))
        if not rg[0] <= n_lead <= rg[1]:
            W(f"리드 {n_lead}자 (목표 {rg[0]}~{rg[1]})")
    for b in boxes:
        if b["type"] == "cta":
            key = "cta_sub" if norm(b["label"]) == norm(f["cta_sub"]) else "cta"
        else:
            key = next((k for k in PARTS if b["label"].startswith(k)), None)
        if not key or PARTS[key][ri] is None:
            continue
        rg = PARTS[key][ri]
        n_b = blen(b["lines"])
        if not rg[0] <= n_b <= rg[1]:
            W(f"「{b['label'] or key}」 {n_b}자 (목표 {rg[0]}~{rg[1]})")
    for h, i, end in sec_ranges:
        if h.startswith(NO_ANSWER_H2) or h in pending_h2:   # 실습 자리 표시 섹션은 직답 없음 (D79)
            continue
        nxt = next((l.strip() for l in lines[i + 1:end] if l.strip() and not l.strip().startswith("<!--")), "")
        if not nxt.startswith("**"):
            E(f"H2 「{h}」 바로 뒤 첫 문장이 굵은 직답(**…**)이 아님")
        else:
            ans = re.sub(r"\*\*", "", strip_tags(nxt)).strip()
            w = width(ans)
            if not 40 <= w <= 80:
                W(f"H2 「{h}」 직답 전각 {w:g}자 (40~80)")

    # --- 표시
    used = []
    for ln in lines:
        for t in TAG_RE.findall(ln):
            if t.startswith("S") and t not in used:
                used.append(t)
    for s in used:
        if s not in facts:
            E(f"[{s}]가 조사 노트 핵심 사실표에 없음")
    toc_facts = {r[2]: set(S_RE.findall(r[5])) for r in toc}
    faq_facts = set()
    for r in table(osec.get("FAQ", [])):
        if len(r) >= 4:
            faq_facts |= set(S_RE.findall(r[3]))
    allowed_all = set().union(*toc_facts.values()) | faq_facts if toc_facts else set()
    for h, i, end in sec_ranges:
        sec_s = set(S_RE.findall(" ".join(TAG_RE.findall("\n".join(lines[i:end])))))
        allow = toc_facts.get(h, set()) | (faq_facts if h.startswith("FAQ") else set())
        extra = sorted(sec_s - allow, key=lambda x: int(x[1:]))
        # D78: 설계안 「쓸 사실」 밖의 S번호 경고는 뺐다 — 모든 [S번호]는 사실 대조가 원문과 맞춰 본다
    lead_s = set()
    first_h2 = got[0][0] if got else len(lines)
    lead_s = set(S_RE.findall(" ".join(TAG_RE.findall("\n".join(lines[:first_h2])))))
    if lead_s - allowed_all:
        W(f"도입부의 S번호 {', '.join(sorted(lead_s - allowed_all))}가 설계안 어디에도 없음")
    if "[EXP]" in main_txt and not has_exp:
        E("[EXP] 표시가 있는데 노트에 실습 기록이 없음 (철칙 1)")
    if "[OP]" in main_txt and not rep:
        E("[OP] 표시가 있는데 대표 한마디가 없음 (철칙 1)")
    unknown = main_txt.count("[?]")
    if unknown:
        W(f"[?] {unknown}개 — blog-factcheck에서 반드시 처리. 초안 메모에 목록")

    body_lines = [(i, l) for i, l in enumerate(lines) if not l.startswith("<!--")]
    body_join = "\n".join(l for _, l in body_lines)
    # 실습 자리 표시 상자와 그 H2는 철칙 1 표현 검사에서 뺀다 (D79 — 상자 밖에 쓰면 지금처럼 오류)
    exp_join = "\n".join(l for i, l in body_lines if i not in trial_lines
                         and not (l.startswith("## ") and l[3:].strip() in pending_h2))

    # --- 철칙 1 · 금지 표현
    if not has_exp:
        for p in EXP_PHRASES:
            if p in exp_join:
                E(f"실습 기록이 없는데 「{p}」 (철칙 1)")
    if not rep:
        for p in REP_PHRASES:
            if p in body_join:
                E(f"대표 한마디가 없는데 「{p}」 (철칙 1)")
    for p in FORBIDDEN:
        if p in body_join:
            E(f"금지 표현 「{p}」 (common.md 4장)")
    for p, n in REPEAT_LIMIT.items():
        if body_join.count(p) > n:
            E(f"「{p}」 {body_join.count(p)}회 (AI 문투, {n}회까지)")

    # --- 표기
    for i, l in body_lines:
        t = re.sub(r"https?://\S+", "", l)
        if ZEN_DIGIT.search(t):
            E(f"{i+1+OFF}행 전각 숫자 — 반각으로")
        if re.search(r"(?<![\d.])\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?<![\d./])\d{1,2}/\d{1,2}(?![\d/])", t):
            E(f"{i+1+OFF}행 날짜 형식 — 「2026年11月19日」")
        if re.search(r"\d+(?:\.\d+)?系以前|系以前", t):
            W(f"{i+1+OFF}행 「系以前」 — 범위가 원문보다 넓어지지 않았는지 (D44 ⑨)")
    note_n = unicodedata.normalize("NFKC", note)
    for v in sorted(set(re.findall(r"(?<![\d.])\d+\.\d+(?:\.\d+)?(?![\d.])", strip_tags(body_join)))):
        if v not in note_n:
            E(f"판 번호·수치 「{v}」가 조사 노트에 없음")
    iso = set()
    for y, m, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", note_n):
        iso.add(f"{int(m)}月{int(d)}日")
    for y, m, d in re.findall(r"(\d{4})年(\d{1,2})月(\d{1,2})日", note_n):
        iso.add(f"{int(m)}月{int(d)}日")
    for md in sorted(set(re.findall(r"(?<!\d)(\d{1,2}月\d{1,2}日)", body_join))):
        if md not in iso and md not in note_n:
            W(f"날짜 「{md}」가 조사 노트에 없음 — 확인")

    # --- 첫 문단·키워드
    lead = ""
    for i, l in enumerate(lines[:first_h2]):
        if l.startswith(("#", ":::", "<!--", ">", "|")) or in_box[i] or not l.strip():
            continue
        lead = l
        break
    lead_p = plain(lead)
    if not lead_p:
        E("제목 바로 아래 리드 문단이 없음 (첫 문단 200자 이내에 메인 키워드 + 직답)")
    else:
        head = lead_p[:200]
        if not has_kw(head, f["main_keyword"]):
            E(f"첫 문단 200자 안에 메인 키워드 「{f['main_keyword']}」가 없음")
        for ek in [x.strip() for x in f["event_keywords"].split("/") if x.strip() and x.strip() != "-"]:
            if not has_kw(head, ek):
                E(f"첫 문단 200자 안에 사건 검색어 「{ek}」가 없음 (속보)")
    # --- 훅은 리드 첫 1~2문장에 (rules/blog-draft.md, D53)
    hook_txt = " ".join(osec.get("훅", []))
    hook_s = set(S_RE.findall(hook_txt))
    lead_sents = [x.strip() for x in re.findall(r"[^。]*。(?:\s*\[S\d+\])*", lead) if x.strip()]
    if hook_s and lead_p:
        first2 = set(S_RE.findall(" ".join(lead_sents[:2])))
        if not hook_s & first2:
            E(f"리드 첫 1~2문장에 설계안 「훅」이 없음 (훅 근거 {', '.join(sorted(hook_s))} 중 하나가 리드 앞 2문장에) — "
              "사실 나열이 아니라 독자가 멈춰 읽을 문장으로 시작 (D53)")

    # --- 서브 키워드 퍼뜨리기 (common.md 6장 키워드 배치, D53)
    main_toks = {norm(t) for t in f["main_keyword"].split()}
    def core(kw):   # 서브 키워드에서 메인 키워드 낱말을 뺀 핵심어. 「〜方法」「〜手順」은 앞말만 봐도 된다
        return [re.sub(r"(方法|手順|やり方)$", "", norm(t)) or norm(t) for t in kw.split() if norm(t) not in main_toks]
    subs = [x.strip() for x in f["sub_keywords"].split("/") if x.strip() and x.strip() != "-"]
    non_h2 = norm("\n".join(plain(l) for i, l in enumerate(lines) if not l.startswith("#") and not l.startswith("<!--")))
    meta_n = norm(f.get("meta", ""))
    any_lead = any_meta = False
    for k in subs:
        toks = core(k)
        miss = [t for t in toks if t not in non_h2]
        if toks and len(miss) == len(toks):
            E(f"서브 키워드 「{k}」의 핵심어({'·'.join(toks)})가 H2 밖 본문에 하나도 없음 — 독자가 검색하는 말을 본문에도 (D53)")
        elif miss:
            W(f"서브 키워드 「{k}」의 핵심어 {'·'.join(miss)}가 H2 밖 본문에 없음")
        any_lead |= any(t in norm(lead_p[:200]) for t in toks)
        any_meta |= any(t in meta_n for t in toks)
    # 검색어를 쉬운 말로 바꿔 쓰지 않았는지 (voice-hikari.md 7-2 예외, D54 — 규칙만으로는 새 초안에서도 「版の番号」가 나왔다)
    SUBST = {"バージョン": ["版の番号", "版番号"], "アップデート": ["更新"], "パッチ": ["修正版"], "確認": ["確かめ"]}
    kw_all = norm(f["main_keyword"] + " " + f["sub_keywords"])
    for term, alts in SUBST.items():
        if norm(term) in kw_all:
            n_t = non_h2.count(norm(term))
            n_a = sum(non_h2.count(norm(x)) for x in alts)
            if n_t < 2 and n_a > n_t:   # 검색어가 본문에 거의 없고 쉬운 말로 대신한 경우만 (確かめる 등은 부드러운 일본어로 써도 된다, D49)
                W(f"검색어 「{term}」 대신 「{'/'.join(alts)}」를 더 많이 씀 ({n_a} > {n_t}) — 독자가 검색하는 말을 쓴다 (D54)")
    if subs and lead_p and not any_lead:
        W("리드 200자 안에 서브 키워드 핵심어가 하나도 없음 (D53)")
    if subs and not any_meta:
        W("메타 설명에 서브 키워드 핵심어가 하나도 없음 (D53)")

    # --- 리드와 3行まとめ가 같은 말을 되풀이하지 않게 (D53)
    def bigr(x):
        x = re.sub(r"\[S\d+\]|\s|[、。・（）「」]", "", x)
        return {x[i:i + 2] for i in range(len(x) - 1)}
    for b_ in boxes:
        if b_["type"] == "box" and "3行まとめ" in b_["label"]:
            for it in b_["lines"]:
                ib = bigr(re.sub(r"^\s*\d+\.\s*", "", it))
                for ls in lead_sents:
                    lb = bigr(ls)
                    if ib and lb and len(ib & lb) / min(len(ib), len(lb)) > 0.6:
                        W(f"3行まとめ 「{it.strip()[:25]}…」가 리드 「{ls.strip()[:25]}…」와 거의 같은 말 — "
                          "3行まとめ는 리드에 없는 판단 기준·할 일로 (D53)")

    for k in [f["main_keyword"]] + [x.strip() for x in f["sub_keywords"].split("/")]:
        if "とは" in k:
            phrase = k.replace("とは", "").strip()
            # 「〜とは、」 앞부분에 키워드 낱말이 모두 있으면 정의 문장 (「Claude アーティファクトの「公開」とは、」도 됨)
            defs = [re.sub(r"[「」『』*]", "", d) for d in re.findall(r"([^。\n]*?)とは、", body_join)]
            if not any(has_kw(d, phrase) for d in defs):
                E(f"「{k}」: 「{phrase}とは、〜です。」 정의 문장이 없음 (AEO)")

    # --- CTA·내부 링크·FAQ
    cta_box = "\n".join("\n".join(b["lines"]) for b in boxes if b["type"] == "cta")
    for r in table(osec.get("CTA", [])):
        if len(r) >= 4:
            if r[2] not in cta_box:
                E(f"CTA 버튼 문구 「{r[2]}」가 :::cta 상자에 없음")
            if r[3] not in cta_box:
                E(f"CTA 링크 {r[3]}가 :::cta 상자에 없음")
    links = dict((u, t) for t, u in re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", main_txt))
    for r in table(osec.get("내부 링크", [])):
        if len(r) >= 3 and r[1].startswith("http"):
            if r[1] not in links:
                E(f"내부 링크 {r[1].rsplit('/', 1)[-1]}가 본문에 없음 (설계안 위치 {r[0]})")
            elif links[r[1]] != r[2]:
                W(f"내부 링크 {r[1].rsplit('/', 1)[-1]} 앵커가 설계안과 다름: 「{links[r[1]]}」 → 「{r[2]}」")
    if re.search(r"\[(こちら|ここ)\]\(", main_txt):
        E("앵커 텍스트 「こちら」 금지")
    h3 = [l[4:].strip() for l in lines if l.startswith("### ")]
    for r in table(osec.get("FAQ", [])):
        if r and r[0] and r[0] not in h3:
            E(f"FAQ 질문 「{r[0]}」가 H3(### )로 없음")

    # --- 분량
    lo, hi = [int(x) for x in re.findall(r"\d+", f["length"])[:2]]
    n = sum(len(re.sub(r"\s", "", plain(l))) for k, l in enumerate(lines)
            if not l.startswith("# ") and not l.startswith("<!--") and k not in trial_lines)   # 자리 표시는 분량에서 뺀다 (D79)
    cap = int(hi * DRAFT_RATIO)
    if n < lo:
        E(f"분량 {n}자 — 하한 {lo} 미만. 늘려 쓰지 말고 초안 메모 「조사 보충 필요」로 (D47)")
    elif n > cap:
        W(f"분량 {n}자 — 상한 {hi}의 90%({cap})를 넘음. 다듬기에서 늘 여유가 적다 (D47, D58: 오류는 상한 초과만)")

    # --- 인용·전재
    quotes = [l for l in lines if l.startswith(">")]
    if len(quotes) > 2:
        W(f"인용 줄 {len(quotes)}개 — 글당 2개까지 (common.md 5장)")
    for q in quotes:
        if not TAG_RE.search(q):
            E(f"인용에 출처 표시가 없음: {q[:30]}…")
    outside = re.sub(r"\s", "", strip_tags("\n".join(l for l in lines if not l.startswith(">"))))
    for sid, r in facts.items():
        org = re.sub(r"\s|…", "", r[2]) if len(r) > 2 else ""
        if not re.search(r"[ぁ-んァ-ヶ一-龠]", org):
            continue
        for k in range(0, max(0, len(org) - 24)):
            frag = org[k:k + 25]
            if frag in outside:
                E(f"{sid} 원문과 25자 이상 같음 — 새로 쓰거나 인용(>)으로: 「{frag}…」 (철칙 5)")
                break

    # --- 용어
    gp = HERE / "glossary_site.json"
    if gp.exists():
        g = json.loads(gp.read_text())
        # 제목(# 줄)은 괄호를 달 수 없으니 첫 등장에서 뺀다 (D98)
        txt = strip_tags("\n".join(l for l in body_join.splitlines() if not l.startswith("# ")))
        bases = [t["base"] for t in g["terms"] if len(t["base"]) >= 2]
        for t in g["terms"]:
            b, pl = t["base"], t["plain"]
            if not pl or len(b) < 2 or b not in txt:
                continue
            # 더 긴 용어집 말(「APIキー」)의 일부인 「API」는 그 자리에서 세지 않는다 (D98)
            longer = [lb for lb in bases if b in lb and lb != b]
            covered = {i for lb in longer for m_ in re.finditer(re.escape(lb), txt) for i in range(m_.start(), m_.end())}
            pos = next((m_.start() for m_ in re.finditer(re.escape(b), txt) if m_.start() not in covered), None)
            if pos is None:
                continue
            win = txt[max(0, pos - 30):pos + len(b) + len(pl) + 6]
            if pl not in win and pl[:6] not in win:
                W(f"용어 「{b}」 첫 등장에 용어집 괄호 풀이가 없음: （{pl}）")
    else:
        W("glossary_site.json 없음 — glossary_sync.py로 만든다")
    faq_kw = " ".join(r[1] for r in table(osec.get("FAQ", [])) if len(r) >= 2)
    title_kw = norm(f["main_keyword"] + f["sub_keywords"] + f["event_keywords"] + faq_kw)
    for w_, rep_ in AVOID.items():
        if w_ in body_join:
            W(f"「{w_}」 → 「{rep_}」 (rules/glossary.md 3장)")
    for w_, rep_ in KW_ONLY.items():
        if w_ in body_join and norm(w_) not in title_kw:
            W(f"「{w_}」는 검색 키워드일 때만 — 「{rep_}」 (rules/glossary.md 3장)")
    if "漏洩" in "\n".join(l for l in lines if not l.startswith("# ")):
        W("본문은 「漏えい」 (제목·키워드만 「漏洩」 허용, rules/glossary.md 3장)")

    # --- 문체 경고
    long_s, cand = [], []
    for i, l in body_lines:
        if l.startswith(("#", "|", ":::", "<!--")) or not l.strip():
            continue
        lp = re.sub(r"^\s*(#+|>|-|\d+\.(?!\d))\s*", "", l)
        for s in sentences(lp):
            p = plain(s) if not re.match(r"^\d+\.\d", s.strip()) else strip_tags(s).replace("**", "").strip()
            if len(p) > 80:
                long_s.append(f"{i+1+OFF}행 {len(p)}자 「{p[:20]}…」")
            if in_box[i] and any(b["type"] in ("guide", "cta") and b["start"] < i for b in boxes
                                 if b["start"] < i <= b["start"] + len(b["lines"])):
                continue
            if not TAG_RE.search(s) and re.search(r"\d|[A-Za-z]{3,}|「[^」]{4,}」", strip_tags(p)) \
                    and not l.lstrip().startswith(("**",)) and not re.search(r"\]\(https?://", s):
                cand.append(f"{i+1+OFF}행 「{p[:24]}…」")
    if long_s:
        W(f"80자 넘는 문장 {len(long_s)}개 — 나눈다: " + " / ".join(long_s[:5]))
    ex = body_join.count("！")
    if ex > 1:
        W(f"「！」 {ex}회 — 글당 0~1회 (voice-hikari.md 1)")
    friendly = len(re.findall(r"(ね|よ)。", body_join))
    if friendly:
        W(f"「〜ね。/〜よ。」 {friendly}회 — 쓰지 않는다, 질문·FAQ만 예외 (voice-hikari.md 7-6)")
    if cand:
        W(f"표시 없는 사실 문장 후보 {len(cand)}개 — 사실이면 [S번호]/[?]: " + " / ".join(cand[:8]))

    # --- 차별 포인트 필수 (D47)
    # 초안은 차별 포인트를 쓴 블록 바로 위에 <!-- 차별 N --> 표시를 둔다 (N = 설계안 「차별 포인트 배치」의 번호)
    # 그 블록(표시 다음의 빈 줄 없는 연속 줄)에 그 항목의 S번호가 있어야 하고, 판정표·표 항목이면 표가 있어야 한다
    no2h = {r[0]: r[2] for r in toc}
    marks = {}
    for i, l in enumerate(lines):
        m_ = re.match(r"^<!--\s*차별\s*(\d+)\s*-->\s*$", l.strip())
        if m_:
            sec_h = next((hh for hh, s0, e0 in sec_ranges if s0 <= i < e0), None)
            marks.setdefault(m_.group(1), []).append((i, sec_h, block_after(lines, i)))
    changed = "\n".join(memo.splitlines())
    placed, ok = 0, 0
    for r in table(osec.get("차별 포인트 배치", [])):
        if len(r) < 2 or "안 씀" in r[1]:
            continue
        mn = re.match(r"\s*(\d+)\.", r[0])
        sids = set(S_RE.findall(r[0]))
        m_no = re.search(r"\d{2}", r[1])
        h = no2h.get(m_no.group()) if m_no else None
        if not mn or not sids or not h:
            continue
        placed += 1
        n_ = mn.group(1)
        label = r[0][:45]
        need_table = any(k in (r[0] + " " + (r[2] if len(r) > 2 else "")) for k in ("판정표", "표", "체크리스트"))
        hits = [x for x in marks.get(n_, []) if x[1] == h]
        if not hits:
            if f"차별 {n_}" in changed:
                W(f"차별 {n_} 「{label}」를 섹션 「{h}」에 쓰지 않음 — 초안 메모의 이유 확인")
            else:
                E(f"차별 {n_} 「{label}」: 섹션 「{h}」에 <!-- 차별 {n_} --> 표시가 없음 (설계안 배치대로, 빼면 초안 메모에 이유, D47)")
            continue
        good = False
        for i_, _, blk in hits:
            bt = "\n".join(blk)
            has_s = any(f"[{x}]" in bt for x in sids)
            has_t = any(x.startswith("|") for x in blk)
            if has_s and (has_t or not need_table):
                good = True
            elif not has_s:
                E(f"{i_+1+OFF}행 차별 {n_}: 표시 아래 블록에 근거 S번호({', '.join(sorted(sids))})가 없음")
            else:
                E(f"{i_+1+OFF}행 차별 {n_}: 판정표·표 항목인데 표시 아래 블록이 표가 아님")
        ok += good
    for n_, lst in marks.items():
        for i_, sec_h, _ in lst:
            if not any(re.match(rf"\s*{n_}\.", r[0]) for r in table(osec.get("차별 포인트 배치", [])) if r):
                E(f"{i_+1+OFF}행 <!-- 차별 {n_} -->: 설계안에 그 번호가 없음")
    if not placed:
        E("설계안 「차별 포인트 배치」에 섹션을 정한 항목이 없음 — blog-outline으로 (D47)")
    elif not ok:
        E("차별 포인트가 본문에 하나도 없음 — 새 가치 없는 글은 내지 않는다 (D47, scaled content abuse)")

    # --- 그림 표시 (D97 ①, D96): 설계안 「## 그림 자리」 표의 N번째 행 → 그 섹션 안, 그림이 뒷받침하는 블록 바로 위에 <!-- 그림 N -->
    # blog-publish가 이 자리에 그림을 넣는다 (find_images.py --slot N). D96 이전 설계안이면 점검하지 않는다
    fig_rows = [r for r in table(osec.get("그림 자리", [])) if len(r) >= 4 and re.match(r"\d{2}", r[0])]
    fig_marks = {}
    for i, l in enumerate(lines):
        m_ = re.match(r"^<!--\s*그림\s*(\d+)\s*-->\s*$", l.strip())
        if m_:
            fig_marks.setdefault(int(m_.group(1)), []).append((i, next((hh for hh, s0, e0 in sec_ranges if s0 <= i < e0), None), block_after(lines, i)))
    if of.get("created_at", "")[:10] >= FIG_RULE_FROM:
        for k, r in enumerate(fig_rows, 1):
            h = no2h.get(r[0][:2])
            hits = [x for x in fig_marks.get(k, []) if x[1] == h]
            if not hits:
                where = [x[1] for x in fig_marks.get(k, [])]
                if re.search(rf"그림 {k}\s*[—-]", changed):   # 「그림 N — 이유」 형식만 (다른 메모 속 「그림 2의」는 아님)
                    W(f"그림 {k} ({r[0]} {r[1][:16]})을 두지 않음 — 초안 메모의 이유 확인")
                else:
                    E(f"그림 {k} ({r[0]} {r[1][:16]}): 섹션 「{h}」에 <!-- 그림 {k} --> 표시가 없음"
                      + (f" — 지금 「{where[0]}」에 있음" if where else "") + " (설계안 그림 자리대로, 빼면 초안 메모 「설계와 달라진 점」에 「그림 N — 이유」, D97)")
                continue
            if len(hits) > 1:
                E(f"<!-- 그림 {k} --> 표시가 {len(hits)}개 — 하나만")
            sids = set(S_RE.findall(r[3]))
            if r[1].startswith("편집부") and sids and not any(f"[{x}]" in "\n".join(hits[0][2]) for x in sids):
                E(f"{hits[0][0]+1+OFF}행 그림 {k}: 표시 아래 블록에 그 그림의 사실({', '.join(sorted(sids))})이 없음 — 그림이 뒷받침하는 사실 바로 위에 (D97)")
        for k, lst in fig_marks.items():
            if not 1 <= k <= len(fig_rows):
                E(f"{lst[0][0]+1+OFF}행 <!-- 그림 {k} -->: 설계안 「그림 자리」에 {k}번째 행이 없음")
    elif fig_marks:
        W("D96 이전 설계안인데 <!-- 그림 N --> 표시가 있음 — 설계안에 그림 자리가 없으면 표시를 뺀다")

    # --- 구조 되풀이 (D97 ②, 경고만): 말투를 고쳐도 남는 모양. 굵은 직답·상자·표·CTA·FAQ는 사이트 형식이라 뺀다
    faq_start = next((s0 for hh, s0, e0 in sec_ranges if "FAQ" in hh or "よくある質問" in hh), len(lines))
    paras, starts, lists, first_openers = [], [], [], []
    cur_list, sec_first = [], {}
    for i, l in enumerate(lines[:faq_start]):
        st = l.strip()
        in_sec = next((hh for hh, s0, e0 in sec_ranges if s0 < i < e0), None)
        is_item = bool(re.match(r"^(-|\d+\.(?!\d))\s", st))
        if cur_list and not is_item:
            lists.append(cur_list); cur_list = []
        if not in_sec or in_box[i] or not st or st.startswith(("#", "|", ">", "<!--", "**", ":::")):
            continue
        p_ = plain(l)
        if is_item:
            cur_list.append(len(re.sub(r"\s", "", p_)))
            continue
        paras.append(len(re.sub(r"\s", "", p_)))
        if in_sec not in sec_first:
            sec_first[in_sec] = p_
        for s in sentences(p_):
            m_ = re.match(r"^(.{1,6}?)(?:[、]|(?<=[^\s])[はがをにでも](?=.))", s.strip())
            starts.append(m_.group(1) if m_ else s.strip()[:4])
            if TALK_ABOUT.match(s.strip()):
                first_openers.append(f"{i+1+OFF}행 「{s.strip()[:14]}…」")
    if cur_list:
        lists.append(cur_list)
    if len(starts) >= 12:
        from collections import Counter
        top = Counter(starts).most_common(3)
        share = sum(c for _, c in top) / len(starts)
        if share > 0.25 and top[0][1] >= 3:
            W(f"문장 시작이 되풀이됨 — 많이 쓴 시작 3개가 {share:.0%} ({' · '.join(f'「{w}」{c}' for w, c in top)}). 주어·순서를 바꿔 본다 (D97)")
    joints = [h for h, p_ in sec_first.items() if re.match(r"^(まず|次に|また|さらに|そして)", p_)]
    if len(sec_first) >= 4 and len(joints) * 2 >= len(sec_first):
        W(f"섹션 첫 본문 문단 {len(joints)}/{len(sec_first)}개가 「まず・次に・また・さらに・そして」로 시작 — 내용으로 시작한다 (D97)")
    for ls_ in lists:
        if len(ls_) >= 4:
            mean = sum(ls_) / len(ls_)
            sd = (sum((x - mean) ** 2 for x in ls_) / len(ls_)) ** 0.5
            if sd < LIST_SD_MIN:
                W(f"목록 {len(ls_)}항목의 길이가 거의 같음 (평균 {mean:.0f}자, 표준편차 {sd:.1f}) — 항목마다 필요한 만큼 쓴다 (D97)")
    if len(paras) >= 6:
        mean = sum(paras) / len(paras)
        cv = ((sum((x - mean) ** 2 for x in paras) / len(paras)) ** 0.5) / mean if mean else 1
        if cv < PARA_CV_MIN:
            W(f"본문 문단 {len(paras)}개의 길이가 고름 (변동계수 {cv:.2f}) — 짧은 문단·긴 문단을 섞는다 (D97)")
    if first_openers:
        W(f"글 자체를 말하는 문장 {len(first_openers)}개 — 바로 내용을 쓴다 (D97): " + " / ".join(first_openers[:5]))
    # D98 (voice-hikari.md 7-5-2): 굵은 글씨 + 콜론 목록, 내용을 채운 괄호
    boldcolon = [f"{i+1+OFF}행" for i, l in enumerate(lines[:faq_start]) if re.match(r"^\s*(-|\d+\.)\s*\*\*[^*]+\*\*\s*[：:]", l)]
    if boldcolon:
        W(f"「**제목**：설명」 목록 {len(boldcolon)}개 — 굵게 하지 말고 문장으로 시작한다 (D98): " + " / ".join(boldcolon[:6]))
    gl_paren = {m for t_ in (g["terms"] if gp.exists() else []) for m in re.findall(r"[（(]([^）)]+)[）)]", t_["term"])}
    stuffed = []
    for i, l in enumerate(lines[:faq_start]):
        if in_box[i] or l.startswith(("#", ">", "|", "<!--")):
            continue
        for m_ in re.finditer(r"（([^（）]{2,})）", strip_tags(l)):
            if re.search(r"[、。]", m_.group(1)) and m_.group(1) not in gl_paren:
                stuffed.append(f"{i+1+OFF}행 「（{m_.group(1)[:14]}…）」")
    if stuffed:
        W(f"읽점·마침표가 든 괄호 {len(stuffed)}개 — 설명은 괄호 밖 문장으로 (D98): " + " / ".join(stuffed[:5]))

    # --- 문단 독립성·경고 문장 (voice-hikari.md 2-3, D47)
    deictic, alarm = [], []
    for i, l in body_lines:
        if not l.strip() or l.startswith(("#", "|", ":::", "<!--")):
            continue
        p_ = plain(l)
        if DEICTIC.match(p_) and not in_box[i]:
            deictic.append(f"{i+1+OFF}행 「{p_[:12]}…」")
        if WARN_WORDS.search(p_) and not ACTION_WORDS.search(p_) and not l.startswith(">"):
            alarm.append(f"{i+1+OFF}행 「{p_[:16]}…」")
    if deictic:
        W(f"앞 문단에 기대는 시작 {len(deictic)}개 — 주어를 다시 쓴다 (AI 인용): " + " / ".join(deictic[:5]))
    if alarm:
        W(f"대책 없는 경고 문단 {len(alarm)}개 — 같은 문단에 할 일을 붙인다: " + " / ".join(alarm[:5]))

    # --- 용어 수준 (glossary.md 2-1, D47)
    if gp.exists():
        known = set()
        for t in g["terms"]:
            known.add(t["base"]); known.add(t["term"])
        kwtxt = f["main_keyword"] + " " + f["sub_keywords"] + " " + f["event_keywords"] + " " + faq_kw
        srcnames = " ".join(r[3] for r in facts.values() if len(r) > 3)
        # D98: 노트 사실·원문 문장에 나온 말은 그 글의 정해진 이름 — 상한에 세지 않는다 (바꿔 말하지 않게)
        notewords = " ".join(" ".join(r[1:3]) for r in facts.values() if len(r) > 2)
        prose = "\n".join(l for i, l in body_lines if not l.startswith((":::", "#")) and
                          not any(b["type"] == "cta" and b["start"] < i <= b["start"] + len(b["lines"]) for b in boxes))
        txt2 = re.sub(r"\]\(https?://[^)]+\)", "]", strip_tags(prose))
        # D78: 세지 않는 것 — 코드 이름(`…`, _ . ( : 숫자에 붙은 말), 괄호 풀이가 붙은 말, 대문자로 시작하는 영문 이름, 나라 이름
        txt2 = re.sub(r"`[^`]*`", " ", txt2)
        txt2 = re.sub(r"[（(][^（）()]*[）)]", " ", re.sub(r"[A-Za-zァ-ヶー\-]+(?=[（(])", " ", txt2))
        txt2 = re.sub(r"[A-Za-z0-9_.:\-]*[_.:0-9][A-Za-z0-9_.:\-]*\(?\)?|[A-Za-z_]+\(\)", " ", txt2)
        cands = set(re.findall(r"(?<![A-Za-z])[a-z][A-Za-z\-]{2,}|(?<![A-Za-z])[A-Z]{2,}(?![a-z])", txt2)) | set(re.findall(r"[ァ-ヶー]{4,}", txt2))
        jargon = sorted(c for c in cands
                        if c not in COMMON_KATA and c not in NOT_JARGON and c not in PLACE_KATA
                        and not any(c in k or k in c for k in known if len(k) >= 3)
                        and norm(c) not in norm(kwtxt) and c not in srcnames and c not in notewords)
        cap_t = TERM_CAP["속보" if short else "일반"]
        if len(jargon) > cap_t:
            W(f"용어집에 없는 전문어 {len(jargon)}개 (상한 {cap_t}) — 빼기·행동으로 바꾸기·괄호 풀이, 남기면 초안 메모 「용어집 추가 후보」: {', '.join(jargon[:12])}")

    # --- SOURCES
    # 사실 대조(blog-factcheck) 뒤에는 URL별 번호 형식 「1. 제목 | … | S4, S6」 (D48) — 그 뒤로는 여기서 덮어쓰지 않는다
    grouped = [l.strip() for l in src_txt.splitlines() if re.match(r"^\d+\.\s", l.strip())]
    if a.write_sources and grouped:
        print("[SOURCES] 이미 사실 대조 형식(URL별 번호) — 덮어쓰지 않음. check_factcheck.py --write-sources 로")
        a.write_sources = False
    if a.write_sources:
        src_lines = []
        for s in used:
            r = facts.get(s)
            if r:
                src_lines.append(f"- {s} | {r[3]} | 発表日 {r[6]} | {r[4]} | 確認日 {r[7]}")
        new_src = "\n\n" + "\n".join(src_lines) + "\n\n"
        text2 = re.sub(r"(^## SOURCES\s*\n)(.*?)(?=^## 초안 메모|\Z)", lambda m: m.group(1) + new_src.lstrip("\n"),
                       text, count=1, flags=re.S | re.M)
        path.write_text(text2)
        print(f"[SOURCES] {len(src_lines)}개 채움")
        src_txt = new_src
    src_ids = []
    for l in src_txt.splitlines():
        m = re.match(r"^-\s*(S\d+)\b", l.strip())
        if m:
            src_ids.append(m.group(1))
    if grouped:
        g_ids = set(S_RE.findall(" ".join(l.rsplit("|", 1)[-1] for l in grouped)))
        if g_ids != set(used):
            E(f"SOURCES(URL별)의 S번호가 본문과 다름 — check_factcheck.py --write-sources\n   본문만: {', '.join(sorted(set(used) - g_ids))}\n   SOURCES만: {', '.join(sorted(g_ids - set(used)))}")
    elif "## SOURCES" not in text:
        E("「## SOURCES」 절이 없음")
    elif src_ids != used:
        E(f"SOURCES가 본문에서 쓴 S번호(처음 나온 순서)와 다름 — --write-sources 로 채운다\n   본문: {', '.join(used)}\n   SOURCES: {', '.join(src_ids)}")
    if "## 초안 메모" not in text:
        E("「## 초안 메모」 절이 없음 ([?] 목록·조사 보충 필요·용어집 추가 후보·설계와 달라진 점, 없으면 「-」)")

    print(f"분량 {n}자 (범위 {lo}~{hi}) / S번호 {len(used)}개 / [?] {unknown}개")
    return report(errs, warns)


def report(errs, warns):
    for e in errs:
        print("❌ " + e)
    for w in warns:
        print("⚠ " + w)
    print("통과" if not errs else f"오류 {len(errs)}건")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
