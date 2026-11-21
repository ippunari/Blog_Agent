#!/usr/bin/env python3
"""blog-distribute: sns.md 점검 (rules/blog-distribute.md). 오류 0이어야 sns_post.py --plan이 게시 요청을 낸다

사용법:
  python3 -I check_sns.py <slug>                       # 발행 완료 카드 기준 (publish/done/YYYY-MM/<slug>/sns.md) → 통과하면 sns/YYYY-MM-DD.md 다시 만들기
  python3 -I check_sns.py <slug> --sns F --draft F --card F --url U --offline   # 시험 모드 (발행 전 글)

보는 것:
  길이 (X는 X 방식 가중치: 한글·가나·한자 2, 영숫자 1 → 280 = 전각 140) / 링크 자리·UTM / 해시태그 수 /
  note 「全文はブログで」 / 복사 금지 (플랫폼끼리·본문과 30자 이상 같은 구간, 「」 인용 제외) /
  숫자가 최종 본문에 있는지 (철칙 4) / 금지 표현·「〜ね/〜ですよ」·AI 문투 / 대표 한마디 없이 ヤン /
  개인 계정 ID(@) / 공개 URL 200 (--offline이면 건너뜀)
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blog-polish"))
sys.path.insert(0, str(HERE.parent / "blog-draft"))
from sns_common import PLATFORMS, EXTRA, URL_RE, utm, parse_sns, paths, front, to_slug  # noqa: E402
from check_polish import FRIENDLY_END, AI_PHRASES, INVISIBLE  # noqa: E402
from check_draft import split_draft, plain  # noqa: E402

# 플랫폼 → (최소, 최대) 글자 수 (본문). X는 가중치로 따로
LENGTH = {"threads": (0, 500), "note": (1000, 2000), "linkedin": (300, 600), "facebook": (200, 400)}
HASHTAGS = {"x": (1, 2), "note": (3, 5), "threads": (0, 1), "linkedin": (2, 3), "facebook": (0, 2)}
EMOJI_MAX = {"x": 1, "threads": 2, "facebook": 1, "linkedin": 0, "note": 0}
# 切り口: 플랫폼마다 앞에 세울 것 (rules/blog-distribute.md 「플랫폼별 스타일」, D75)
KIRIKUCHI = {"x": {"数字", "意外な事実", "質問"}, "threads": {"試した", "気づき"}, "facebook": {"場面"},
             "linkedin": {"判断"}, "note": {"編集部メモ", "裏側", "視点"}}
NOTE_KIRI = {"속보": {"編集部メモ"}, "깊이": {"裏側", "視点"}}   # note는 블로그 요약이 아니라 다른 각도 (D76)
# 목소리 표지: 이 말이 나오면 안 되는 플랫폼
VOICE_NG = {"ヒカリです": {"x", "facebook", "linkedin"}, "弊社": {"x", "threads", "facebook"}}
CLICKBAIT = ["衝撃", "必見", "知らないと損", "ヤバい", "やばい", "驚愕", "してないの？", "な人は今すぐ"]
BAIT = ["いいねして", "いいねお願い", "RTして", "リポストして", "シェアして", "フォローして", "保存して", "コメントして", "拡散"]
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u203C\u2049\u3030\u303D]")
GREETING = re.compile(r"^(ヒカリです|こんにちは)")
EN_TERM = re.compile(r"(?<![A-Za-z0-9./_-])([A-Za-z][A-Za-z0-9._-]{2,})(?![A-Za-z0-9])")
KNOWN_NAMES = {"PHP", "AI", "WordPress", "ChatGPT", "Gemini", "Claude", "Copilot", "Google", "Microsoft", "Windows",
               "Excel", "Word", "LINE", "Apple", "iPhone", "Android", "Mac", "Zoom", "Slack", "Teams", "OpenAI", "Gmail"}
# 본문에 링크가 있어야 하는 곳 / 있으면 안 되는 곳
LINK_IN_BODY = {"x": False, "threads": True, "note": True, "linkedin": False, "facebook": False}
BANNED = ["絶対", "100%安全", "100％安全", "最強", "神ツール", "革命的", "今すぐ対策しないと", "大変なことに", "ずさん"]
COPY_N = 30
HASHTAG_RE = re.compile(r"(?<![\w&/])#[^\s#、。]+")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*(?:件|年|月|日|時|系|%|％|分|つ|週|回|人|社|円|万|億|か月|カ月|版)?")
QUOTE = re.compile(r"「[^「」]*」|『[^『』]*』")


def x_weight(s):
    """X 글자 수 (twitter-text v3): 이 범위는 1, 나머지(한글·가나·한자·이모지)는 2. 280까지"""
    w = 0
    for ch in s:
        c = ord(ch)
        w += 1 if (c <= 4351 or 8192 <= c <= 8205 or 8208 <= c <= 8223 or 8242 <= c <= 8247) else 2
    return w


def norm(s):
    return re.sub(r"\s+", "", QUOTE.sub("", URL_RE.sub("", HASHTAG_RE.sub("", s))))


def shared_span(a, b, n=COPY_N):
    """a와 b에 똑같이 있는 n자 이상 구간 하나 (없으면 None)"""
    if len(a) < n or len(b) < n:
        return None
    grams = {b[i:i + n] for i in range(len(b) - n + 1)}
    for i in range(len(a) - n + 1):
        if a[i:i + n] in grams:
            return a[i:i + n]
    return None


def first_line(b):
    """인사 줄(「ヒカリです。」「こんにちは…」)을 뺀 첫 줄"""
    for ln in b.strip().splitlines():
        ln = ln.strip()
        if ln and not GREETING.match(ln):
            return ln
    return ""


def style(p, secs, b, E, W, title_words):
    """플랫폼별 스타일 점검 (rules/blog-distribute.md 「플랫폼별 스타일」, D75)"""
    k = secs.get("切り口", "").strip()
    if k not in KIRIKUCHI[p]:
        E.append(f"{p}: 「### 切り口」이 {sorted(KIRIKUCHI[p])} 중 하나여야 함 (지금 {k or '없음'})")
    for w_, ng in VOICE_NG.items():
        if p in ng and w_ in b:
            E.append(f"{p}: 「{w_}」를 쓰지 않는다 (목소리: 플랫폼별 스타일)")
    for w_ in CLICKBAIT:
        if w_ in b:
            E.append(f"{p}: 낚시 표현 「{w_}」")
    for w_ in BAIT:
        if w_ in b:
            E.append(f"{p}: 반응 구걸 「{w_}」 (노출이 줄어든다)")
    n = len(EMOJI_RE.findall(b))
    if n > EMOJI_MAX[p]:
        E.append(f"{p}: 이모지 {n}개 — {EMOJI_MAX[p]}개까지")
    lines = [ln.strip() for ln in b.strip().splitlines() if ln.strip()]
    text_lines = [ln for ln in lines if not URL_RE.fullmatch(ln) and not re.fullmatch(r"(#\S+\s*)+", ln)]
    first = first_line(b)
    if p != "note" and re.search(r"(公開|発表|リリース|発売|開始)(されました|しました)", first):
        W.append(f"{p}: 첫 줄이 「〜が公開されました」 소식형 — 切り口({k or '?'})을 첫 줄에")
    if p == "threads":
        if text_lines and not re.search(r"[？?]$", text_lines[-1]):
            W.append("threads: 마지막 문장을 질문으로 끝내 답글을 부른다")
        if any(re.match(r"^(\d+[.．)](?!\d)|・|■|-\s)", ln) for ln in lines):
            W.append("threads: 번호·기호 목록을 쓰지 않는다 (이야기하듯)")
    if p == "facebook":
        if not re.search(r"「|たら|と言われ|から.*(届|来|聞)", first):
            W.append("facebook: 첫 줄에 장면이 없음 — 「○○から『△△』と言われたら」처럼 사장님이 겪을 장면으로")
        if len(first) > 60:
            W.append(f"facebook: 첫 줄 {len(first)}자 — 60자 이내 (접기 전에 보이게)")
        for t in EN_TERM.findall(URL_RE.sub("", b)):
            if t not in KNOWN_NAMES and t not in title_words and not re.search(re.escape(t) + r"[（(]", b):
                W.append(f"facebook: 영문 기술 용어 「{t}」 — 쓰지 않거나 괄호로 풀이")
    if p == "linkedin":
        if not re.search(r"\d", "".join(text_lines[:2])):
            W.append("linkedin: 첫 두 줄에 근거 수치가 없음 (「もっと見る」 전에 판단 + 수치)")
        if "弊社" not in b:
            W.append("linkedin: 「弊社編集部では」로 판단 주체를 밝힌다")
    if p in ("x", "threads", "facebook", "linkedin") and GREETING.match(first) is None and re.match(r"^\d{4}年\d+月\d+日", first):
        W.append(f"{p}: 첫 줄이 날짜로 시작 — 切り口을 앞에")


def kwn(s):
    """검색어 비교용: 공백·전각 공백 빼고 소문자"""
    return re.sub(r"[\s\u3000]", "", s or "").lower()


def seo(p, secs, b, E, W, kw_main, kw_all, route, blog_titles):
    """검색: note는 블로그와 다른 검색어를 맡는다 / 다른 SNS는 첫 두 줄에 블로그 키워드 (D76)"""
    lines = [ln.strip() for ln in b.strip().splitlines() if ln.strip() and not GREETING.match(ln.strip())]
    head2 = kwn("".join(lines[:2]))
    if p == "note":
        k = secs.get("切り口", "").strip()
        if k and k not in NOTE_KIRI[route]:
            E.append(f"note: {route} 글의 切り口은 {sorted(NOTE_KIRI[route])} (블로그 요약이 아니라 다른 각도)")
        title = secs.get("タイトル", "")
        if not title:
            E.append("note: 「### タイトル」 없음")
        if kw_main and (kw_main in kwn(title) or kw_main in head2):
            E.append(f"note: 제목·첫 문단에 블로그 메인 키워드 「{kw_main}」 — note가 블로그와 같은 검색어로 겨룬다 (다른 말로)")
        for t in blog_titles:
            if t and t != "-" and kwn(title)[:15] == kwn(t)[:15]:
                E.append(f"note: 제목 첫 15자가 블로그 제목과 같음 — 「{t[:20]}」")
                break
    elif p in ("x", "threads", "linkedin") and kw_all and not any(k in head2 for k in kw_all):
        W.append(f"{p}: 첫 두 줄에 블로그 키워드(메인·서브)가 없음 — SNS 안 검색용으로 자연스럽게 1번 ({kw_all[0]} 등)")


def http_status(url):
    p = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-L", "--max-time", "30", "-w", "%{http_code}", "--", url],
                       capture_output=True, text=True)
    return p.stdout.strip()


def check(sns_path, draft_path, card_path, url=None, offline=False):
    E, W = [], []
    text = sns_path.read_text()
    head, posts = parse_sns(text)
    card = front(card_path.read_text())
    slug = head.get("slug") or card.get("slug")
    url = url or card.get("url") or head.get("url")
    if not url:
        E.append("머리: url 없음 (카드 url: 또는 --url)")
        return E, W, posts
    if head.get("url") and head["url"] != url:
        E.append(f"머리 url이 카드와 다름: {head['url']} ≠ {url}")
    if INVISIBLE.search(text):
        E.append("보이지 않는 문자가 섞여 있음")

    main, _, _ = split_draft(draft_path.read_text())
    body_plain = "\n".join(plain(ln) for ln in main.splitlines())
    body_norm = norm(body_plain)
    body_compact = re.sub(r"\s+", "", re.sub(r"\[S\d+\]", "", main))
    h1 = next((ln[2:] for ln in main.splitlines() if ln.startswith("# ")), "")
    dfm = front(draft_path.read_text())
    title_words = set(EN_TERM.findall(dfm.get("og_title", "") + " " + h1))   # 글 제목의 이름은 Facebook에서도 된다
    kw_main = kwn(dfm.get("main_keyword", ""))
    kw_all = [k for k in [kw_main] + [kwn(x) for f in ("sub_keywords", "event_keywords")
                                      for x in re.split(r"\s*/\s*", dfm.get(f, ""))] if k and k != "-"]
    route = "속보" if "속보" in dfm.get("route", "") else "깊이"
    rep = card.get("rep_comment", "없음").strip()
    has_rep = rep not in ("", "없음", "-", "none")

    for p in PLATFORMS:
        if p not in posts or "本文" not in posts[p]:
            E.append(f"{p}: 「## {p}」 아래 「### 本文」 블록이 없음")
    norms = {}
    for p, secs in posts.items():
        if p not in PLATFORMS:
            E.append(f"모르는 플랫폼 이름: {p} (x / threads / note / linkedin / facebook)")
            continue
        b = secs.get("本文", "")
        if not b:
            continue
        want = utm(url, p, slug)
        # 길이
        if p == "x":
            w = x_weight(b)
            if w > 280:
                E.append(f"x: 길이 {w}/280 (전각 {w / 2:.0f}자) — 전각 140자 이내")
        else:
            lo, hi = LENGTH[p]
            n = len(b)
            if not lo <= n <= hi:
                E.append(f"{p}: 길이 {n}자 — {lo}~{hi}자")
        # 링크 자리·UTM
        links = URL_RE.findall(b)
        if LINK_IN_BODY[p]:
            if links != [want]:
                E.append(f"{p}: 본문 링크는 이 UTM 링크 1개만: {want} (지금 {links or '없음'})")
        elif links:
            E.append(f"{p}: 본문에 링크를 넣지 않는다 ({EXTRA[p][1]} 칸으로) — {links}")
        if p in EXTRA:
            name, what = EXTRA[p]
            ex = secs.get(name, "")
            exl = URL_RE.findall(ex)
            if exl != [want]:
                E.append(f"{p}: 「### {name}」({what})에 이 UTM 링크 1개만: {want} (지금 {exl or '없음'})")
            if p in ("facebook", "linkedin") and ex.strip() != want:
                E.append(f"{p}: 「### リンク」에는 URL만 쓴다")
        # 해시태그
        tags = HASHTAG_RE.findall(b)
        lo, hi = HASHTAGS[p]
        if not lo <= len(tags) <= hi:
            E.append(f"{p}: 해시태그 {len(tags)}개 — {lo}~{hi}개 {tags}")
        # 스타일 (D75)
        style(p, secs, b, E, W, title_words)
        seo(p, secs, b, E, W, kw_main, kw_all, route, [h1, dfm.get("og_title", ""), dfm.get("seo_title", "")])
        # note 꼬리
        if p == "note" and "全文はブログで" not in b:
            E.append("note: 「全文はブログで」와 링크가 없음 (전문 전재 금지)")
        # X 첫 문장 — 수치나 질문
        if p == "x":
            first = re.split(r"[。！？?\n]", b.strip(), maxsplit=1)[0]
            if not (re.search(r"\d", first) or re.search(r"[？?]", b.strip()[:len(first) + 1])):
                W.append("x: 첫 문장이 수치나 질문으로 시작하지 않음")
        # 숫자 → 최종 본문에 있어야 (철칙 4). URL·해시태그는 뺀다
        whole = b + "\n" + "\n".join(v for k, v in secs.items() if k != "本文")
        # 숫자는 단위까지 붙여 본문에 같은 꼴이 있는지 본다 (「7件」→「9件」을 잡는다). 줄 머리 「1.」 목록 번호는 뺀다
        for num in NUM_RE.findall(re.sub(r"(?m)^\d+\.\s", "", HASHTAG_RE.sub("", URL_RE.sub("", whole)))):
            if num not in body_compact:
                E.append(f"{p}: 숫자 「{num}」이 최종 본문에 없음 — 본문에 있는 사실만 쓴다")
        # 표현
        for w_ in BANNED:
            if w_ in b:
                E.append(f"{p}: 금지 표현 「{w_}」 (common.md 4장)")
        for w_ in AI_PHRASES:
            if w_ in b:
                E.append(f"{p}: AI 문투 「{w_}」")
        for ln in re.split(r"(?<=。)|\n", b):
            ln = ln.strip()
            if ln and not re.search(r"[？?]", ln) and FRIENDLY_END.search(QUOTE.sub("", ln)):
                E.append(f"{p}: 「〜ね/〜よ」 끝맺음 — {ln[-25:]}")
        if "ヤン" in b and not has_rep:
            E.append(f"{p}: 대표 한마디가 없는데 「ヤン」이 나옴 (철칙 1)")
        if p != "linkedin" and "ヤン" in b:
            W.append(f"{p}: 대표 한마디는 LinkedIn 첫머리에만 (blog-distribute.md)")
        if re.search(r"(?<![\w.])@[A-Za-z0-9_]{2,}", whole):
            E.append(f"{p}: 계정 ID(@…)를 쓰지 않는다 (파일에 개인 계정 ID 금지)")
        norms[p] = norm(b)
        # 본문 복사
        span = shared_span(norms[p], body_norm)
        if span:
            E.append(f"{p}: 블로그 본문과 {COPY_N}자 이상 같음 — 「{span}」 (새로 쓴다, 전재 금지)")
    firsts = {p: first_line(posts[p]["本文"]) for p in norms}
    fp = list(firsts)
    for i, a in enumerate(fp):
        for b_ in fp[i + 1:]:
            if firsts[a][:20] and re.sub(r"\s", "", firsts[a])[:20] == re.sub(r"\s", "", firsts[b_])[:20]:
                E.append(f"{a}·{b_}: 첫 문장 첫 20자가 같음 — 「{firsts[a][:20]}」 (切り口을 다르게)")
    ps = list(norms)
    for i, a in enumerate(ps):
        for b_ in ps[i + 1:]:
            span = shared_span(norms[a], norms[b_])
            if span:
                E.append(f"{a}·{b_}: {COPY_N}자 이상 같음 — 「{span}」 (플랫폼마다 새로 쓴다)")
    if not offline:
        code = http_status(url)
        if code != "200":
            E.append(f"공개 URL 응답 {code}: {url}")
    hero = head.get("hero")
    if not hero or not Path(hero).exists():
        W.append(f"머리 hero(대표 이미지) 파일 없음: {hero} — X 첨부 없이 올라간다")
    return E, W, posts


def report(E, W):
    for w in W:
        print("⚠ " + w)
    for e in E:
        print("❌ " + e)
    print(f"\n{'통과' if not E else '고칠 것 ' + str(len(E)) + '건'} (경고 {len(W)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--root", default=".")
    ap.add_argument("--sns"); ap.add_argument("--draft"); ap.add_argument("--card"); ap.add_argument("--url")
    ap.add_argument("--offline", action="store_true", help="공개 URL 확인을 건너뜀 (발행 전 시험)")
    a = ap.parse_args()
    root = Path(a.root)
    if a.sns and a.draft and a.card:
        sns, draft, card = Path(a.sns), Path(a.draft), Path(a.card)
    else:
        P = paths(root, to_slug(a.slug))
        sns, draft, card = P["sns"], P["draft"], P["card"]
    for f in (sns, draft, card):
        if not f.exists():
            sys.exit(f"❌ {f} 없음")
    E, W, _ = check(sns, draft, card, a.url, a.offline)
    report(E, W)
    date = front(card.read_text()).get("published_at", "")[:10]
    if not E and date and not a.sns:
        import sns_digest
        print(f"날짜별 모음: {sns_digest.build(root, date)}")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
