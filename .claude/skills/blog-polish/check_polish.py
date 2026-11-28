#!/usr/bin/env python3
"""blog-polish: 다듬기 점검 (기본은 읽기 전용).

drafts/<slug>.md 를 rules/voice-hikari.md 7장(D49)·rules/common.md 4·6장·rules/blog-polish.md로 본다.
 1. textlint (preset-japanese·히라가나·한자 연속·중복 표현·prh 사전) — 본문만 떼어 낸 사본으로. 원문 인용(>)과 「」『』 안은 제외
    preset-ai-writing(AI 문투: 목록 꾸밈·과장·강조·콜론·간결성)은 경고만, 「する必要があります」 제안은 넘김 (D99)
    yomiyasu lint(vendor/, 판 고정 — 직역어·비유 동사·決まり文句 등)도 경고만, 참고(info)는 개수만 (D101)
    같은 말 몰림(確かめ 등)·「版」·한 문단에 같은 긴 이름 3번 (D100)
    (문장 길이는 「」 안까지 세야 하므로 textlint가 아니라 이 스크립트가 본다: 80자 초과 오류, 71~80자 경고, D78)
 2. 보이지 않는 특수 문자 (파일 전체)
 3. 「〜ね。」「〜よ。」 끝맺음 (질문 「？」 문장은 제외), 같은 어미 3연속, 「〜てください」 문단당 2회, 「ぜひ」 글당 1회
 4. 일본어 AI 문투, 관청 말투·판단이 필요한 말 (경고)
 5. 리듬: 71~80자 문장(경고), 긴 문장만 이어지는 문단(D78), 体言止め 후보, 「の」 3연속 후보
 6. 한자 비율 25~35% (40% 넘으면 오류)
 7. 메타: 검색용 제목·메타 설명·SNS 제목·설명·excerpt·slug — 길이·키워드·대조된 문장인지
 8. 초안 점검(blog-draft/check_draft.py)을 같이 돌린다

사용법:
  python3 -I check_polish.py drafts/<slug>.md                 점검
  python3 -I check_polish.py drafts/<slug>.md --strip-invisible  보이지 않는 특수 문자를 지운다 (파일을 고침)
  python3 -I check_polish.py drafts/<slug>.md --write-memo       「## 다듬기 메모」의 자동 칸(지표·SEO 체크리스트)을 채운다
  python3 -I check_polish.py drafts/<slug>.md --snapshot         다듬기 시작 때 사본 (drafts/.before-polish/, 로컬만)
  python3 -I check_polish.py drafts/<slug>.md --meaning-diff     사본과 비교 — 뜻이 바뀔 위험 문장 (재대조 대상에 더함)
종료 코드 0 = 통과(경고만 있을 수 있음), 1 = 오류
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "blog-draft"))
sys.path.insert(0, str(HERE.parent / "blog-outline"))
from check_outline import front, sections, width, has_kw  # noqa: E402
from check_draft import split_draft, sentences, strip_tags, plain, TAG_RE  # noqa: E402

JST = timezone(timedelta(hours=9))
INVISIBLE = re.compile("[ ­᠎​-‏  ‪-‮⁠-⁤﻿︀-️"
                       "\U000e0000-\U000e007f]")
FRIENDLY_END = re.compile(r"(ね|よ|よね|ですよ|わ)。$")
AI_PHRASES = ["と言っても過言ではありません", "と言っても過言では", "が不可欠です", "が求められます", "多岐にわたる", "徹底解説",
              "いかがでしたか", "について解説します", "をご紹介します", "をご紹介していきます", "見ていきましょう"]
AI_PATTERNS = [(re.compile(r"まず(は)?.{0,25}から始め(て(み)?)?ましょう"), "「まず〜から始めましょう」 상투 결말 (7-5)"),
               # 번역투 (voice-hikari.md 7-2-2, D56) — 말한 쪽을 숨기는 보고 동사 수동, require 직역
               (re.compile(r"(説明|指摘|予告|発表|報告|言及|推奨)され(て(い)?)?(ました|ます|た|る|ている|ていました)"),
                "번역투 — 「〜と説明されました」처럼 누가 말했는지 숨긴 수동. 「〇〇は〜と説明していました」 (7-2-2)"),
               (re.compile(r"が条件(だ|です|と|に|で)"), "번역투 — 「〜が条件だ」(require 직역). 「〜のときだけ影響します」 (7-2-2)"),
               (re.compile(r"一般的でない構成|一般的ではない構成"), "번역투 — 「一般的でない構成」(uncommon setups). 「あまり使われない構成」 (7-2-2)"),
               (re.compile(r"には[^。]{0,25}(条件|もの)が必要(です|とされ)"), "번역투 — 「〜には条件が必要です」(require 직역). 「〜できるのは〜がそろった場合です」 (7-2-2, D57)"),
               (re.compile(r"最初から(使う|使われ|無効|有効|入って)"), "default 직역 「最初から〜」 → 「初期設定で〜」 (7-2-3, D57)"),
               # 해야 할 일을 흐리는 말 (voice-hikari.md 7-4-2, D52)
               (re.compile(r"(の|こと)が基本(です|になります|となります)|(対応|対策|対処)の基本は"),
                "해야 할 일을 「基本」으로 흐림 → 「〜する必要があります」 (출처가 하라고 한 대책일 때, 7-4-2)")]
JUDGE = [(re.compile(r"を行(う|い|っ|わ|え)"), "「〜を行う」 → 「〜する」로 쓸 수 있는지"),
         (re.compile(r"(?<!す)ることが(可能|でき)"), "「〜ることが可能です / できます」 → 「〜られます / できます」"),
         (re.compile(r"において"), "「〜において」 → 「〜で」"),
         (re.compile(r"(?<!によると)とされています|とされていました"), "「〜とされています」 — 누가? 출처를 주어로 (「〇〇によると」)"),
         (re.compile(r"実施|把握|留意"), "관청 말투 (実施→行う / 把握→確かめる / 留意→気をつける)"),
         (re.compile(r"ないわけでは(ない|ありません)"), "이중 부정"),
         (re.compile(r"(推奨|要求|期待)されます"), "수동태 — 능동으로 (「〜しましょう」)"),
         (re.compile(r"させていただ"), "경어 과잉 「させていただく」"),
         (re.compile(r"[一-龯ァ-ヶー」）A-Za-z0-9]は[、「（A-Za-z0-9一-龯ぁ-んァ-ヶ][^。]*?[一-龯ァ-ヶー」）A-Za-z0-9]は[、\s]"), "「〜は、〜は、」 は가 두 번 — 하나를 「〜が」「〜について」로 바꾸거나 두 문장으로 (7-2-3)"),
         (re.compile(r"(?<!と)としています|としていました"), "문서 말투 「〜としています」 — 「〜と書かれています」「〜と説明しています」 (7-2-2, D57)"),
         (re.compile(r"(?<!その)ときだけ|のときに限り"), "조건은 「〜場合」가 자연스럽다 (「〜場合に限られます」「〜場合だけです」) (7-2-3)"),
         (re.compile(r"とよいでしょう|が望ましい(です)?|(?<!が)基本です"), "해야 할 일이면 「〜する必要があります」, 선택이면 「〜がおすすめです」 (7-4-2)")]
OK_END = set("すんうたるだかぬねよ")  # です·ます·ません·でしょう·ました·ある… 로 끝나면 体言止め 아님
# 「い」로 끝나는 말: 형용사·ない·たい·ください는 괜찮고, 「違い」「扱い」 같은 명사는 体言止め
I_OK = re.compile(r"(な|た|し|さ|く|す|か|ご|る|ら|き|よ|い|ぽ|ど|高|多|早|速|安|低|遅|広|狭|近|遠|強|弱|古|深|浅|重|軽|長|短|若|痛|辛|甘|細|太|丸|黒|白|赤|青|良|悪|怖|鋭|厚|薄|固|硬|暗|明|温|寒|暑|熱|冷|緩|淡|濃|醜|美|偉|幼|賢|鈍)い$")
QUOTE = re.compile(r"「[^「」]*」|『[^『』]*』")
# D78: 흐린 말 — 글 전체에서 2회 넘으면 경고 (「」 안 인용 제외)
VAGUE_WORDS = ("多くの", "幅広い", "欠かせません", "必要不可欠", "と考えられます")
VAGUE_MAX = 2
CONCLUSION_RE = re.compile(r"結論から(言うと|言えば|いうと|いえば)")
# D78: 한자 6자 연속 금지의 예외 — 기관·법률·직함 이름 (줄이면 사실이 흐려진다: 最高研究責任者 → 研究部門の責任者)
NAME_SUFFIX = re.compile(r"(委員会|機構|協会|研究所|大学|省|庁|局|法|条例|責任者|担当者|部長|課長|社長|会長|理事長|長官|大臣|本部|機関|裁判所|銀行)$")
KANJI_RANGE = {"default": (25, 35), "보안 사고 해설": (25, 38), "보안 대책 가이드": (25, 38)}
# D100: 같은 말이 한 글에 몰리면 단조롭다 — 글당 이 횟수를 넘으면 경고 (「」 안 인용 제외)
REPEAT_MAX = {"確かめ": (4, "見る・調べる・聞く・チェックする 등으로 나누거나 문장을 합친다"),
              "確認し": (4, "見る・調べる・聞く 등으로"),
              "する必要があります": (3, "섹션당 1번. 나머지는 「〜してください」나 출처를 주어로 「〇〇は〜よう求めています」 (강도는 그대로, 7-4-2)"),
              "おすすめします": (2, "「〜がおすすめです」「〜と安心です」로 섞는다"),
              "しましょう": (4, "「〜してください」「〜と安心です」로 섞는다")}
# D100: 「アプリの版」 — 일본 독자는 「バージョン」 (일상 가타카나를 한자 한 글자로 바꾸지 않는다, 7-1)
VERSION_KANJI = re.compile(r"(アプリ|ソフト(ウェア)?|ブラウザー?|OS|[A-Za-z][A-Za-z0-9 ・]*)の版|版の番号|版を(確か|調べ|見)")
# D101: yomiyasu (vendor/yomiyasu, MIT, 판 고정) — 경고로만. 우리 글 틀·다른 점검과 겹치거나 부딪치는 규칙은 뺀다
YOMI = HERE / "vendor" / "yomiyasu"
YOMI_SKIP = {"excess_list",        # 글 뼈대(わかること·3行まとめ·순서 목록)가 목록이다 (D47)
             "bold_label_list",    # check_draft(D98)·preset-ai-writing(D99)가 잡는다
             "excess_bold",        # H2마다 굵은 직답 1문장이 규칙이다 (voice-hikari.md 2장)
             "sentence_length"}    # 문장 길이는 이 스크립트가 (80자)
YOMI_INFO_KEEP = {"calque", "translated_term", "metaphor_label", "ai_phrase", "thin_evaluation", "slop_vocabulary"}


def unquote(s):
    """「」『』 안(원문 인용·메뉴 이름·공식 표기)은 고치지 않으므로 검사에서 뺀다"""
    return QUOTE.sub("「」", s)


def is_taigen(s):
    core = re.sub(r"[）」』\)\]]+$", "", s.rstrip("。"))
    if not s.endswith("。") or not core:
        return False
    if core in ("はい", "いいえ"):  # FAQ 답 (D78)
        return False
    if core[-1] == "い":
        return not I_OK.search(core)
    return core[-1] not in OK_END
NO_CHAIN = re.compile(r"(?<![こそあどもい])の[^、。「」\s]{1,10}(?<![こそあどもい])の[^、。「」\s]{1,10}(?<![こそあどもい])の")
KANJI = re.compile(r"[一-鿿々〆]")
KANA = re.compile(r"[ぁ-ゖァ-ヺー]")
MEMO_START, MEMO_END = "<!-- auto:start -->", "<!-- auto:end -->"


_GLOSS = None


def glossary_words(root):
    """사이트 용어집 말 (한자 연속 예외용, D78)"""
    global _GLOSS
    if _GLOSS is None:
        gp = Path(root) / ".claude/skills/blog-draft/glossary_site.json"
        try:
            g = json.loads(gp.read_text())
            _GLOSS = {w for t in g["terms"] for w in (t.get("term", ""), t.get("base", "")) if w}
        except (OSError, ValueError, KeyError):
            _GLOSS = set()
    return _GLOSS


def jlen(s):
    return len(re.sub(r"\s", "", s))


def body_lines(text):
    """(줄 번호, 줄, 상자 종류) — 머리·SOURCES 뒤 제외"""
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    start = m.group(0).count("\n") if m else 0
    lines = text.splitlines()
    box, out, trial_open = None, [], False
    for i in range(start, len(lines)):
        st = lines[i].strip()
        if re.match(r"^## SOURCES\s*$", st):
            break
        if st.startswith(":::"):
            opening = box is None
            box = st[3:].strip() or None if box is None else None
            if not (opening and box and box.startswith("trial")) and not (not opening and trial_open):
                out.append((i, lines[i], "marker"))
            trial_open = bool(opening and box and box.startswith("trial"))
            continue
        if box and box.startswith("trial"):
            continue   # 사람 실습 자리 표시는 다듬기 대상이 아니다 (D79)
        out.append((i, lines[i], box))
    return out


def prose_paragraphs(bl):
    """본문 문단 [(시작 줄 번호, [문장…], is_list)] — 표·제목·인용·주석·CTA 상자 제외"""
    paras, cur, cur_list, cur_start = [], [], False, None
    def flush():
        nonlocal cur, cur_start
        if cur:
            paras.append((cur_start, cur, cur_list))
        cur, cur_start = [], None
    for i, l, box in bl:
        st = l.strip()
        if (not st or box == "marker" or st.startswith(("#", "|", ">", "<!--")) or
                (box and box.startswith("cta"))):
            flush()
            continue
        is_list = bool(re.match(r"^(-|\d+\.(?!\d))\s", st))
        if is_list:
            flush()
        cur_list = is_list
        if cur_start is None:
            cur_start = i
        body = re.sub(r"^(-|\d+\.(?!\d))\s*", "", st).replace("**", "")
        for s in sentences(body):
            p = plain(s)
            if p:
                cur.append((i, p))
        if is_list:
            flush()
    flush()
    return paras


def lint_copy(text, bl):
    """textlint용 사본: 줄 번호를 그대로 두고, 본문 밖·상자 표시·주석·인용·[S번호]는 빈 줄/삭제"""
    lines = [""] * len(text.splitlines())
    for i, l, box in bl:
        st = l.strip()
        if box == "marker" or st.startswith(("<!--", ">")) or (box and box.startswith("cta")):
            continue
        s = TAG_RE.sub("", l)
        s = re.sub(r"<!--.*?-->", "", s)
        lines[i] = unquote(s)
    return "\n".join(lines) + "\n"


def run_textlint(root, copy_text):
    tl = root / "node_modules" / ".bin" / "textlint"
    if not tl.exists():
        return None, "textlint가 설치되지 않음 — 프로젝트 폴더에서 `npm ci --ignore-scripts`"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "body.md"
        p.write_text(copy_text)
        r = subprocess.run([str(tl), "--config", str(HERE / "textlintrc.json"), "--format", "json", str(p)],
                           capture_output=True, text=True, cwd=root)
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return None, "textlint 실행 실패: " + (r.stderr or r.stdout)[:300]
    msgs = [m for f in data for m in f.get("messages", [])]
    return msgs, None


def run_yomiyasu(root, copy_text):
    """yomiyasu_lint를 본문 사본(표준 입력)에 돌린다. 용어집 말은 allow.txt로 뺀다 (D101)"""
    lint = YOMI / "yomiyasu_lint.py"
    if not lint.exists():
        return None, "vendor/yomiyasu 없음"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "allow.txt").write_text("\n".join(sorted(w for w in glossary_words(root) if len(w) >= 2)) + "\n")
        r = subprocess.run([sys.executable, "-I", str(lint), "--json", "--doc-type", "article", "--reader", "general",
                            "--words", td, "-"], input=copy_text, capture_output=True, text=True, cwd=root)
    try:
        return json.loads(r.stdout).get("findings", []), None
    except json.JSONDecodeError:
        return None, "yomiyasu 실행 실패: " + (r.stderr or r.stdout)[:300]


def meaning_diff(root, before, after):
    """다듬기 전 사본과 지금 초안을 yomiyasu_diff로 비교 — 숫자·부정·조사 바뀜 등 「뜻이 바뀔 위험」만 (D101)"""
    # 사본은 점으로 시작하는 폴더라 yomiyasu가 파일로는 읽지 않는다 → 표준 입력으로
    r = subprocess.run([sys.executable, "-I", str(YOMI / "yomiyasu_diff.py"), "--no-words", "--json",
                        "-", str(Path(after).resolve().relative_to(root))],
                       input=Path(before).read_text(), capture_output=True, text=True, cwd=root)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, "yomiyasu_diff 실행 실패: " + (r.stderr or r.stdout)[:300]
    # 같은 문장이 여러 종류(숫자·부정·의무…)로 나오면 한 줄로 묶는다
    grouped = {}
    for m in d.get("meaning_risks", []):
        key = re.sub(r"\*\*", "", m.get("new", ""))
        g = grouped.setdefault(key, [m.get("new_line") or m.get("old_line"), [], m.get("old", ""), m.get("new", "")])
        if m.get("kind") and m["kind"] not in g[1]:
            g[1].append(m["kind"])
    return [(ln, "·".join(k), old, new) for ln, k, old, new in grouped.values()], None


def snapshot_path(dp):
    return dp.parent / ".before-polish" / dp.name


def metrics(text, bl):
    chars = "".join(plain(TAG_RE.sub("", l)) for i, l, box in bl
                    if box != "marker" and not l.strip().startswith((">", "<!--")) and not (box and box.startswith("cta")))
    chars = re.sub(r"https?://\S+", "", chars)
    k, kana = len(KANJI.findall(chars)), len(KANA.findall(chars))
    return k, kana, (k / (k + kana) * 100 if k + kana else 0)


def end_key(p):
    """같은 어미 판정: 「です」는 2글자, ます·ました·ません 꼴은 3글자 (あります/しています/できます는 다른 어미)"""
    s = re.sub(r"[）」』\)\]]+$", "", p.rstrip("。"))
    if re.search(r"(ます|ました|ません)$", s):
        return s[-4:] if s.endswith("ました") else s[-3:]
    return s[-2:]


def check_meta(f, text, E, W):
    main, _, _ = split_draft(text)
    h1 = next((l[2:].strip() for l in main.splitlines() if l.startswith("# ")), "")
    kw = f.get("main_keyword", "")
    checked = re.sub(r"\s", "", strip_tags(main + f.get("meta", "")))
    title = f.get("seo_title", "-")
    title = h1 if title in ("", "-") else title
    w = width(title)
    if not 28 <= w <= 35:
        E(f"검색용 제목 전각 {w:g}자 (28~35): 「{title}」")
    if kw and not has_kw(title[:max(12, len(kw) + 4)], kw):
        E(f"검색용 제목 앞쪽에 메인 키워드 「{kw}」가 없음")
    if title.count("【") > 1:
        E("검색용 제목의 【】는 1개까지")
    meta = f.get("meta", "")
    w = width(meta)
    if not 80 <= w <= 120:
        E(f"메타 설명 전각 {w:g}자 (80~120)")
    if kw and not has_kw(meta, kw):
        E(f"메타 설명에 메인 키워드 「{kw}」가 없음")
    elif kw and not has_kw(meta[:50], kw):
        W("메타 설명 앞 50자에 메인 키워드가 없음 — 핵심은 앞 50자")
    for k, lo, hi in (("og_title", 15, 40), ("og_description", 40, 100), ("excerpt", 60, 150)):
        v = f.get(k, "")
        if not v or v == "-":
            E(f"머리 `{k}:` 없음 — SNS 공유용 제목·설명·목록용 요약 (rules/blog-polish.md 메타 정보)")
            continue
        vw = width(v)
        if not lo <= vw <= hi:
            W(f"`{k}` 전각 {vw:g}자 (권장 {lo}~{hi})")
        for s in sentences(v) if k != "og_title" else [v]:
            ss = re.sub(r"\s", "", s).rstrip("。")
            if ss in checked:
                continue
            frags = [x for x in re.split(r"[、，,｜|？?！!。：:]", ss) if x]
            if frags and all(x in checked or x in re.sub(r"\s", "", h1) for x in frags):
                continue   # 제목·메타·본문 조각을 이어 붙인 것 (D54)
            if re.search(r"\d|[A-Za-z]{2,}", ss):
                E(f"`{k}`의 「{s[:30]}」 — 숫자·고유명사가 든 새 문장. 제목·메타·본문에서 대조된 문장을 쓰거나 "
                  "blog-factcheck 재대조 기록에 더한다 (철칙 4)")
            else:
                W(f"`{k}`의 「{s[:30]}」 — 본문·메타에 없는 문장. 사실이 들었으면 재대조 기록에 더한다")
    for k in ("seo_title", "og_title", "og_description", "excerpt", "meta"):
        v = f.get(k, "")
        if v and FRIENDLY_END.search(v):
            E(f"`{k}` 「〜ね/〜よ」 끝맺음")
        for rx, why in AI_PATTERNS[1:]:   # 번역투·「基本」 (D52, D56) — 메타·excerpt에도
            if v and rx.search(v):
                E(f"`{k}` {why}")
    slug = f.get("slug", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,4}", slug):
        E(f"slug 「{slug}」 — 영어 소문자·하이픈 3~5단어")
    if re.search(r"\d{4}|\b(the|a|an|of|and|to|for)\b", slug.replace("-", " ")):
        W(f"slug 「{slug}」에 날짜·불용어")
    return title


AI_PRESET = "@textlint-ja/ai-writing/"  # preset-ai-writing의 ruleId 앞부분


def check(a, root):
    errs, warns = [], []
    E, W = errs.append, warns.append
    dp = Path(a.file)
    text = dp.read_text()
    f = front(text)
    for n, l in enumerate(text.splitlines(), 1):
        if INVISIBLE.search(l):
            E(f"{n}행 보이지 않는 특수 문자 {[hex(ord(c)) for c in INVISIBLE.findall(l)]} — --strip-invisible")
    bl = body_lines(text)

    # 0. excerpt는 사이트 글 머리(제목 아래)에 보인다 → 본문 리드와 같은 문장이면 연달아 두 번 읽힌다 (D52)
    body_md = re.split(r"(?m)^## SOURCES", text.split("\n---\n", 1)[-1])[0]
    # 글 머리 = 첫 H2 앞 전부 (리드 + 3行まとめ·こんな方に·わかること·案内 상자) — 페이지에서 excerpt 바로 아래에 보인다 (D54)
    lead_md = re.split(r"(?m)^(<!--|## )", re.sub(r"(?m)^(# .*|:::.*|\d+\.\s*|-\s*)", "", body_md), maxsplit=1)[0]
    norm = lambda x: re.sub(r"\[(S\d+|EXP|OP|\?)\]|\s", "", x).rstrip("。")
    lead_s = {norm(x) for x in re.split(r"(?<=。)", lead_md) if norm(x)}
    for x in re.split(r"(?<=。)", f.get("excerpt", "")):
        if norm(x) and norm(x) in lead_s:
            E(f"`excerpt`의 「{x.strip()[:30]}…」가 글 머리(리드·3行まとめ 등 상자)와 같은 문장 — 사이트는 제목 아래에 excerpt를 보여 줘서 "
              "바로 아래에서 두 번 읽힌다. 메타 설명 문장이나 글 소개 문장(「〜をまとめました」)으로 (rules/blog-polish.md 메타 정보)")

    # 1. textlint
    msgs, err = run_textlint(root, lint_copy(text, bl))
    if err:
        E(err)
    else:
        src_lines = text.splitlines()
        for m in msgs:
            # 「方 => ほう」: 형태소 분석이 사람을 뜻하는 「方(かた)」(持っている方・知りたい方は)까지 「ほう」로 읽는다.
            # 「ほう」 쓰임은 거의 「〜ほうが」이므로, 「方」 다음이 「が」가 아니면 かた로 보고 넘긴다 (D60)
            if m.get("ruleId") == "ja-hiragana-keishikimeishi" and "方 => ほう" in m["message"]:
                ln = src_lines[m["line"] - 1] if 0 < m["line"] <= len(src_lines) else ""
                col = m.get("column", 1) - 1
                k = ln.find("方", max(col - 2, 0))
                if k >= 0 and ln[k + 1:k + 2] != "が":
                    continue
            # 한자 연속: 기관·법률·직함 이름이나 사이트 용어집 말이면 넘긴다 (D78)
            if m.get("ruleId") == "max-kanji-continuous-len":
                run = m["message"].rsplit(":", 1)[-1].strip()
                if NAME_SUFFIX.search(run) or run in glossary_words(root):
                    continue
            rid = m.get("ruleId", "")
            # preset-ai-writing(D99): AI 문투 후보 — 사실·인용 문장도 걸리므로 경고만 (판단해서 고친다)
            if rid.startswith(AI_PRESET):
                # 「する必要があります」를 「してください」로 바꾸라는 제안은 7-4-2(D52)와 부딪친다 — 넘긴다
                if "義務表現" in m["message"]:
                    continue
                W(f"{m['line']}행 textlint [{rid[len(AI_PRESET):]}] {m['message'].splitlines()[0]}")
                continue
            E(f"{m['line']}행 textlint [{rid}] {m['message'].splitlines()[0]}")

    # 1-2. yomiyasu (D101) — 경고만. 「주제 뒤 읽점」(pause_comma)·「AではなくB」 같은 참고(info)는 개수만
    copy = lint_copy(text, bl)
    yf, yerr = run_yomiyasu(root, copy)
    yinfo = 0
    if yerr:
        W(yerr)
    else:
        for m in yf:
            rule = m.get("rule", "")
            if rule in YOMI_SKIP or (rule == "calque" and "言い方: 版）" in m.get("message", "")):
                continue   # 「版」은 아래 우리 점검(D100)이 잡는다
            if m.get("severity") == "info" and rule not in YOMI_INFO_KEEP:
                yinfo += 1
                continue
            msg = m.get("message", "").split("。")[0]
            W(f"{m.get('line')}행 yomiyasu [{rule}] {msg}: 「{m.get('snippet', '')[:30]}…」")
        if yinfo:
            W(f"yomiyasu 참고 {yinfo}건(주제 뒤 읽점·「AではなくB」 등) — 자연스러우면 그대로. 보려면 "
              f"`python3 -I {YOMI.relative_to(root) if YOMI.is_relative_to(root) else YOMI}/yomiyasu_lint.py --doc-type article <초안>`")

    # 3·4·5. 문장·문단
    paras = prose_paragraphs(bl)
    all_s = [(i, s) for _, ss, _ in paras for i, s in ss]
    joined = "".join(s for _, s in all_s)
    for i, s in all_s:
        if FRIENDLY_END.search(s):
            E(f"{i+1}행 「〜ね/〜よ」 끝맺음 — 쓰지 않는다 (voice-hikari.md 7-6): 「{s[-20:]}」")
        uq = unquote(s)
        for ph in AI_PHRASES:
            if ph in uq:
                E(f"{i+1}행 AI 문투 「{ph}」 (voice-hikari.md 7-5)")
        for rx, why in AI_PATTERNS:
            if rx.search(uq):
                E(f"{i+1}행 {why}")
        for rx, why in JUDGE:
            if rx.search(uq):
                W(f"{i+1}행 {why}: 「{s[:30]}…」")
        if NO_CHAIN.search(uq):
            W(f"{i+1}행 「の」 3연속 후보 — 나누거나 바꾼다: 「{NO_CHAIN.search(uq).group(0)}」")
        n = jlen(s)
        if n > 80:
            E(f"{i+1}행 {n}자 — 80자 넘는 문장은 나눈다: 「{s[:20]}…」")
        elif 70 < n <= 80:
            W(f"{i+1}행 {n}자 — 60자 안팎이 기준. 나눌 수 있으면 나눈다: 「{s[:20]}…」 (D78: 71자부터 경고)")
    joined_uq = unquote(joined)
    for w in VAGUE_WORDS:
        c = joined_uq.count(w)
        if c > VAGUE_MAX:
            W(f"흐린 말 「{w}」 {c}회 — 글당 {VAGUE_MAX}회까지. 숫자·대상·이유를 구체적으로 쓴다 (7-5, D78)")
    if len(CONCLUSION_RE.findall(joined_uq)) > 1:
        E(f"「結論から言うと」 {len(CONCLUSION_RE.findall(joined_uq))}회 — 되풀이하지 않는다. 결론은 그냥 먼저 쓴다 (7-5, D78)")
    for w, (mx, how) in REPEAT_MAX.items():
        c = joined_uq.count(w)
        if c > mx:
            W(f"「{w}」 {c}회 — 같은 말이 몰림(글당 {mx}회까지 권장). {how} (7-2, D100)")
    for i, s in all_s:
        if VERSION_KANJI.search(unquote(s)):
            W(f"{i+1}행 「版」 — 앱·소프트웨어의 판이면 「バージョン」 (일상 가타카나를 한자로 바꾸지 않는다, 7-1, D100): 「{s[:30]}…」")
    zehi = joined.count("ぜひ")
    if zehi > 1:
        E(f"「ぜひ」 {zehi}회 — 글당 1회까지 (7-5)")
    for start, ss, is_list in paras:
        txt = "".join(s for _, s in ss)
        kd = txt.count("てください") + txt.count("でください")
        if kd > 2:
            E(f"{start+1}행 문단 「〜てください」 {kd}회 — 문단당 2회까지 (7-4)")
        # D100: 한 문단에 같은 긴 이름(가타카나·영문 6자 이상)이 3번 — 두 번째부터는 줄여 부른다 (문단 첫 문장만 이름 그대로)
        for nm in set(re.findall(r"[A-Za-z][A-Za-z0-9 .・]{5,}[A-Za-z0-9]|[ァ-ヶー・]{6,}", unquote(txt))):
            if unquote(txt).count(nm) >= 3:
                W(f"{start+1}행 문단에 「{nm.strip()}」 {unquote(txt).count(nm)}회 — 두 번째부터는 「アプリ」「この機能」처럼 줄여 부른다 (7-5-2, D100)")
        if txt.count("することで") > 1:
            W(f"{start+1}행 문단 「〜することで」 {txt.count('することで')}회 — 문단당 1회까지 (7-5)")
        if is_list:
            continue
        ends = [end_key(s) for _, s in ss if s.endswith("。")]
        for j in range(len(ends) - 2):
            if ends[j] == ends[j + 1] == ends[j + 2]:
                E(f"{ss[j][0]+1}행부터 같은 어미 「〜{ends[j]}。」 3연속 (rules/blog-polish.md)")
                break
        # D78: 짧은 문장을 일부러 만들지 않는다 — 긴 문장(40자 넘음)만 이어질 때만 경고
        if len(ss) >= 3 and not any(jlen(s) <= 40 for _, s in ss):
            W(f"{start+1}행 문단의 문장이 모두 40자를 넘음 — 하나를 나눈다 (채우기 문장을 더하지 않는다, 7-3)")
        for i, s in ss:
            if is_taigen(s):
                W(f"{i+1}행 体言止め 후보 「…{s[-12:]}」 (7-3)")
    lead = next((ss for _, ss, lst in paras if not lst), [])
    if lead and re.search(r"(について|を)(解説|ご紹介)", lead[0][1]):
        E("리드를 「〜について解説します / をご紹介します」로 시작하지 않는다 (7-5)")
    if lead and re.search(r"(こんな|このような|そんな)(お)?悩み", lead[0][1]):
        E("리드를 「こんなお悩みはありませんか？」류로 시작하지 않는다 — 실제 장면·사실로 시작 (7-5, D78)")

    # 6. 한자 비율
    k, kana, ratio = metrics(text, bl)
    lo, hi = KANJI_RANGE.get(f.get("type", ""), KANJI_RANGE["default"])
    if ratio > 40:
        E(f"한자 비율 {ratio:.1f}% — 40% 넘음. ひらく·쉬운 말로 (7-1)")
    elif not lo <= ratio <= hi:
        W(f"한자 비율 {ratio:.1f}% (목표 {lo}~{hi}%, 글 종류 {f.get('type', '-')})")

    # 7. 메타
    check_meta(f, text, E, W)
    if "PHPフリー" in text and "PHP Free" in text:
        E("「PHP Free」와 「PHPフリー」가 섞여 있음 — 이름은 일관되게 (common.md 6장 AIO)")

    # 8. 초안 점검
    r = subprocess.run([sys.executable, "-I", str(HERE.parent / "blog-draft" / "check_draft.py"), str(dp),
                        "--root", str(root)], capture_output=True, text=True)
    draft_ok = r.returncode == 0
    if not draft_ok:
        E("초안 점검(check_draft.py) 불통과 — 다듬다가 깨진 것:\n" + "\n".join(
            "    " + l for l in r.stdout.splitlines() if l.startswith("❌")))
    return errs, warns, {"kanji": ratio, "sentences": len(all_s),
                         "long": sum(1 for _, s in all_s if jlen(s) > 60),
                         "textlint": 0 if msgs is None else sum(not m.get("ruleId", "").startswith(AI_PRESET) for m in msgs), "draft_ok": draft_ok}


def checklist(text, f, root):
    """common.md 6장 SEO 12항목·AEO·AIO — 기계로 볼 수 있는 것은 판정, 나머지는 단계를 적는다"""
    main, _, _ = split_draft(text)
    lines = main.splitlines()
    h2 = [l[3:].strip() for l in lines if l.startswith("## ")]
    is_faq = lambda h: h.strip().upper() == "FAQ" or "よくある質問" in h or "（FAQ）" in h   # D54
    h2q = [h for h in h2 if not is_faq(h)]
    h3_before = any(l.startswith("### ") for l in lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), 0)])
    kw = f.get("main_keyword", "")
    subs = [s.strip() for s in f.get("sub_keywords", "").split("/") if s.strip()]
    lead = next((l for l in lines if l.strip() and not l.startswith(("#", "---", ":::", "<!--"))), "")
    lead200 = plain(lead)[:200]
    links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", main)
    inner = [(t, u) for t, u in links if "atatakaidigital.com/ja/blog/" in u]
    outer = [(t, u) for t, u in links if "atatakaidigital.com" not in u]
    answers = []
    for i, l in enumerate(lines):
        if l.startswith("## ") and not is_faq(l[3:]):
            nxt = next((x for x in lines[i + 1:] if x.strip() and not x.startswith("<!--")), "")
            if nxt.startswith("**"):
                answers.append(width(plain(nxt)))
    title = f.get("seo_title", "-")
    title = next((l[2:] for l in lines if l.startswith("# ")), "") if title in ("", "-") else title
    meta = f.get("meta", "")
    existing = root / "topics" / "existing_posts.json"
    same_title = False
    if existing.exists():
        try:
            posts = json.loads(existing.read_text())
            posts = posts.get("posts", posts) if isinstance(posts, dict) else posts
            same_title = any(p.get("title") == title for p in posts if isinstance(p, dict))
        except (json.JSONDecodeError, AttributeError):
            pass
    outline = root / f.get("outline", "-")
    osec = sections(outline.read_text()) if outline.exists() else {}
    ok = lambda c: "통과" if c else "미통과"  # noqa: E731
    rows = [
        ("SEO 1 쓰기 전", ok("검색 의도" in osec and "겹침 구분" in osec), "설계안 「검색 의도」「겹침 구분」"),
        ("SEO 2 제목", ok(28 <= width(title) <= 35 and has_kw(title[:12], kw) and title.count("【") <= 1 and not same_title),
         f"전각 {width(title):g}자, 키워드 앞쪽, 기존 글과 {'같음' if same_title else '다름'}"),
        ("SEO 3 메타 설명", ok(80 <= width(meta) <= 120 and has_kw(meta[:50], kw)), f"전각 {width(meta):g}자, 앞 50자에 키워드"),
        ("SEO 4 slug", ok(bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){2,4}", f.get("slug", "")))), f.get("slug", "")),
        ("SEO 5 소제목", ok(4 <= len(h2q) <= 8 and all(h.endswith("？") or "？" in h for h in h2q) and not h3_before),
         f"H2 {len(h2q)}개 (FAQ 제외), 모두 질문형"),
        ("SEO 6 본문", ok(has_kw(lead200, kw) and all(any(has_kw(h, s) for h in h2) for s in subs)),
         "첫 200자에 메인 키워드, 질문형 서브 키워드가 H2에 / 분량·차별 포인트는 초안 점검"),
        ("SEO 7 내부 링크", ok(2 <= len(inner) and not any(t.strip() in ("こちら", "ここ") for t, _ in inner)),
         f"본문 {len(inner)}개, 「こちら」 앵커 없음 / 기존 글에서 새 글로 역링크는 blog-publish 뒤"),
        ("SEO 8 외부 링크", "통과" if not outer else "사람 확인", f"본문 외부 링크 {len(outer)}개 / 출처는 SOURCES(사실 대조 통과)"),
        ("SEO 9 이미지", "blog-publish", "대표 이미지 1200×630·WebP·alt"),
        ("SEO 10 구조화 데이터", "blog-publish", "BlogPosting·저자·BreadcrumbList" + (" / FAQPage (FAQ 있음)" if any(is_faq(h) for h in h2) else "")),
        ("SEO 11 날짜·갱신", "blog-publish", "발행일·최종 업데이트일"),
        ("SEO 12 태그", ok("태그" in osec), "설계안 「태그」"),
        ("AEO 직답", ok(answers and all(40 <= w <= 80 for w in answers)), "H2 직답 전각 " + ", ".join(f"{w:g}" for w in answers)),
        ("AEO 목록·표", ok(any(re.match(r"^\d+\.\s", l) for l in lines) or any(l.startswith("|") for l in lines)), "순서는 번호 목록, 비교는 표"),
        ("AEO FAQ", ok(any(is_faq(h) for h in h2) and any(l.startswith("### ") for l in lines)), "FAQ H3 = 실제 검색 질문 (설계안)"),
        ("AIO 문단 독립", "초안 점검", "check_draft.py 문단 독립성"),
        ("AIO 수치 출처", "사실 대조", "factcheck 보고서·SOURCES 확인일"),
        ("AIO 1차 정보", "초안 점검", "차별 포인트 표시 (D47)"),
        ("AIO 필자 프로필", "사이트 설정", "ヒカリちゃん = 편집부 (BlogAgent.md 남은 일)"),
        ("AIO 이름 일관", ok(not ("PHPフリー" in text and "PHP Free" in text)), "서비스·회사 이름 표기"),
    ]
    return rows


def write_memo(a, root, stats):
    dp = Path(a.file)
    text = dp.read_text()
    f = front(text)
    rows = checklist(text, f, root)
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    auto = [MEMO_START, f"- 점검 시각: {now}",
            f"- 한자 비율 {stats['kanji']:.1f}% / 문장 {stats['sentences']}개 중 60자 넘는 문장 {stats['long']}개 / "
            f"textlint 지적 {stats['textlint']}건 / 초안 점검 {'통과' if stats['draft_ok'] else '불통과'}",
            "", "| 항목 | 판정 | 근거 |", "|---|---|---|"]
    auto += [f"| {a_} | {b} | {c} |" for a_, b, c in rows]
    auto.append(MEMO_END)
    block = "\n".join(auto)
    if "## 다듬기 메모" not in text:
        text = text.rstrip("\n") + "\n\n## 다듬기 메모\n- 바꾼 것: \n- 재대조: \n- 남은 경고: \n\n" + block + "\n"
    elif MEMO_START in text:
        text = re.sub(re.escape(MEMO_START) + r".*?" + re.escape(MEMO_END), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    dp.write_text(text)
    print(f"다듬기 메모 자동 칸을 채움: {dp}")


def report(errs, warns):
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
    ap.add_argument("--strip-invisible", action="store_true")
    ap.add_argument("--write-memo", action="store_true")
    ap.add_argument("--snapshot", action="store_true", help="다듬기 시작 때 초안 사본을 drafts/.before-polish/에 둔다 (D101)")
    ap.add_argument("--meaning-diff", action="store_true", help="사본과 지금 초안을 비교해 뜻이 바뀔 위험 문장을 보인다 (D101)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if a.strip_invisible:
        p = Path(a.file)
        t = p.read_text()
        n = len(INVISIBLE.findall(t))
        p.write_text(INVISIBLE.sub(lambda m: " " if m.group(0) == " " else "", t))
        print(f"보이지 않는 특수 문자 {n}개를 지움 (NBSP는 공백으로)")
        return 0
    dp = Path(a.file)
    if a.snapshot:
        sp = snapshot_path(dp)
        sp.parent.mkdir(exist_ok=True)
        sp.write_text(dp.read_text())
        print(f"다듬기 전 사본: {sp}")
        return 0
    if a.meaning_diff:
        sp = snapshot_path(dp)
        if not sp.exists():
            print(f"사본 없음 — 다듬기 시작 때 --snapshot ({sp})")
            return 1
        risks, err = meaning_diff(root, sp, dp)
        if err:
            print("❌ " + err)
            return 1
        for ln, kind, old, new in risks:
            print(f"⚠ {ln or '-'}행 뜻이 바뀔 위험 [{kind}]\n    전: {old[:90]}\n    후: {new[:90]}")
        print(f"뜻이 바뀔 위험 {len(risks)}건 — 이 문장들을 재대조 대상에 더한다 (SKILL 4장)" if risks else "뜻이 바뀔 위험 없음")
        return 0
    errs, warns, stats = check(a, root)
    if a.write_memo:
        write_memo(a, root, stats)
    return report(errs, warns)


if __name__ == "__main__":
    sys.exit(main())
