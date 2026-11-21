#!/usr/bin/env python3
"""blog-publish: 다듬은 초안(drafts/<slug>.md)을 Ghost에 붙여 넣을 파일로 만든다 (임시 방식, D23·D50).

만드는 것 (publish/<slug>/):
  card1-style.html  Ghost HTML 카드 1 — 사이트 HowtoAI 템플릿 CSS + 보충분 (template/)
  card2-body.html   Ghost HTML 카드 2 — 본문 (초안 표시 변환: [S] 삭제(SOURCES에 쓰였는지만 확인, D51), 주석·[EXP]·[OP] 삭제, ::: → 템플릿 상자,
                    FAQ → faq-i + FAQPage JSON-LD, SOURCES → cs-src, 글 끝 CTA → cs-cta). 초안 메모·다듬기 메모는 넣지 않는다
  preview.html      로컬 미리보기 (두 카드 + 머리. 실제 확인은 Ghost 미리보기 ◆)
  (카드 머리에 publish: 줄을 더한다)
  ghost.md          Ghost 입력값(제목·slug·excerpt·메타·SNS·태그·대표 이미지·이메일 끄기·발행 시각)과 미리보기 체크리스트 — 한국어
점검 (오류가 있으면 파일을 쓰지 않는다):
  카드 상태·대조 통과·재대조, 속보 마감(D34), 하루 발행 상한, 남은 초안 표시, 각주 ↔ SOURCES, CTA 문구·링크(cta.json),
  내부 링크가 기존 글 목록에 있는지, HTML 태그 짝, 대표 이미지(있으면) 규격
  --check-links: 본문·SOURCES·CTA 링크를 실제로 열어 본다 (네트워크)

사용법:
  python3 -I build_publish.py drafts/<slug>.md [--root .] [--check-links] [--now 2026-11-20T21:00+09:00]
"""
import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

JST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent
SITE = "https://atatakaidigital.com"
IMG = "https://cms.ondi.jp/content/images/2026/10/"
HIKARI = {"guide": IMG + "hikari_welcome.png", "say": IMG + "hikari_avatar.png", "cta": IMG + "hikari_next-step.png"}
YANG_FACE = IMG + "face-base.jpg"
# 일본 공휴일 (内閣府 「国民の祝日」, 2026~2027). 해가 바뀌기 전에 다음 해를 더한다 — 목록에 없는 해면 경고
JP_HOLIDAYS = {
    "2026-01-01", "2026-01-12", "2026-02-11", "2026-02-23", "2026-03-20", "2026-04-29", "2026-05-03", "2026-05-04",
    "2026-05-05", "2026-05-06", "2026-07-20", "2026-08-11", "2026-09-21", "2026-09-22", "2026-09-23", "2026-10-12",
    "2026-11-03", "2026-11-23",
    "2027-01-01", "2027-01-11", "2027-02-11", "2027-02-23", "2027-03-21", "2027-03-22", "2027-04-29", "2027-05-03",
    "2027-05-04", "2027-05-05", "2027-07-19", "2027-08-11", "2027-09-20", "2027-09-23", "2027-10-11", "2027-11-03",
    "2027-11-23",
}
DAILY_CAP = 6          # 평일 하루 6편 (D31). 넘으면 멈추고 사람에게 (common.md 7장 B)
TAGS = json.loads((HERE / "tags.json").read_text())   # 실제 Ghost 태그 slug (D62에서 확인)


def tag_slugs(axis, route, typ):
    """기본 = 언어 + 주제 축, 보조 = 글 종류 (common.md 6장 12) → 사이트 실제 태그"""
    out = TAGS["lang"] + TAGS["axis"].get(axis, [])
    if axis == "보안":
        cat = TAGS["security_cat"]
        hit = cat["속보"] if route == "속보" else next((v for k, v in cat.items() if not k.startswith("_") and k != "속보" and re.search(k, typ)), "")
        out += [hit] if hit else []
    return out
BTN_LINE = re.compile(r"^\[[^\]]+\]\([^)\s]+\)$")
UA = "Mozilla/5.0 (compatible; BlogAgentPublish/1.0)"

errs, warns = [], []
E, W = errs.append, warns.append


def front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            k, sep, v = ln.partition(":")
            if sep and re.match(r"^[a-z_]+$", k.strip()):
                out[k.strip()] = v.strip()
    return out, (text[m.end():] if m else text)


def parse_dt(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?::\d{2})?([+-]\d{2}:\d{2})", s or "")
    return datetime.fromisoformat(m.group(1) + m.group(2)) if m else None


def jdate(d):
    y, mo, da = d.split("-")
    return f"{int(y)}年{int(mo)}月{int(da)}日"


def zen_len(s):
    return sum(0.5 if ord(c) < 0x2000 else 1 for c in s)


# ---------- SOURCES ----------
def parse_sources(lines):
    srcs, s2n = [], {}
    for ln in lines:
        m = re.match(r"^(\d+)\.\s+(.*)$", ln.strip())
        if not m:
            continue
        parts = [p.strip() for p in m.group(2).split(" | ")]
        if len(parts) != 6:
            E(f"SOURCES {m.group(1)}번 칸 수 {len(parts)} (제목 | 발행처 | 発表日 | URL | 確認日 | S번호 6칸)")
            continue
        title, pub, pdate, url, cdate, ss = parts
        n = int(m.group(1))
        if n != len(srcs) + 1:
            E(f"SOURCES 번호가 순서대로가 아님: {n}")
        for s in re.findall(r"S\d+", ss):
            s2n[s] = n
        srcs.append({"n": n, "title": title, "pub": pub, "pdate": pdate.replace("発表日", "").strip(),
                     "url": url, "cdate": cdate.replace("確認日", "").strip(), "used": False})
    return srcs, s2n


def clean_title(t):
    t = re.split(r" ／ | · ", t)[0]
    t = re.sub(r"（\d+ページ目 / 全\d+ページ）.*$", "", t)
    return t.strip()


def source_li(s):
    dates = []
    if s["pdate"] not in ("", "-"):
        dates.append("・".join(jdate(d.strip()) for d in s["pdate"].split(",")) + "発表")
    if re.match(r"\d{4}-\d{2}-\d{2}", s["cdate"]):
        dates.append(jdate(s["cdate"][:10]) + "確認")
    dom = urlparse(s["url"]).netloc.removeprefix("www.")
    pub = re.sub(r"\s*[（(][^）)]*[）)]$", "", s["pub"])   # 「The PHP Group (php.net News Archive)」 → 「The PHP Group」
    return (f'<li><span>{html.escape(pub)}「{html.escape(clean_title(s["title"]))}」'
            f'（{"、".join(dates)}） <a href="{html.escape(s["url"])}">{html.escape(dom)}</a></span></li>')


# ---------- 인라인 ----------
def make_inline(s2n, srcs):
    def inline(t):
        if "[?]" in t:
            E(f"[?] 표시가 남음 (blog-factcheck에서 처리해야 함): {t[:40]}")
        t = t.replace("[EXP]", "").replace("[OP]", "")
        t = html.escape(t, quote=False)

        def fn(m):
            nums = []
            for s in re.findall(r"S\d+", m.group(0)):
                if s not in s2n:
                    E(f"[{s}]가 SOURCES에 없음")
                    continue
                n = s2n[s]
                srcs[n - 1]["used"] = True
                if n not in nums:
                    nums.append(n)
            return ""   # 본문에는 각주 번호를 내지 않는다 — 출처는 문장 속 출처명 + 글 끝 SOURCES (D51)
        t = re.sub(r"\s*(?:\[S\d+\])+", fn, t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

        def link(m):
            url = m.group(2)
            if url.startswith(SITE):
                url = url[len(SITE):] or "/"
            return f'<a href="{html.escape(url)}">{m.group(1)}</a>'
        t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
        return t
    return inline


def plain(h):
    h = re.sub(r'<sup class="fn">.*?</sup>', "", h)
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


# ---------- 블록 ----------
def blocks(lines):
    """Markdown 줄 → 블록 목록 [(종류, 데이터)]"""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith(":::"):
            m = re.match(r":::(\w+)\s*(.*)$", ln)
            j = i + 1
            while j < len(lines) and lines[j].strip() != ":::":
                j += 1
            out.append(("box", (m.group(1), m.group(2).strip(), blocks(lines[i + 1:j]))))
            i = j + 1
            continue
        if ln.startswith("<!--"):
            m = re.match(r"<!--\s*(\d{2})\s+(.+?)\s*-->$", ln)
            if m:
                out.append(("label", (m.group(1), m.group(2))))
            elif not re.match(r"<!--\s*차별 \d+\s*-->$", ln):
                W(f"모르는 주석 — 지움: {ln[:40]}")
            i += 1
            continue
        m = re.match(r"(#{2,3}) (.+)$", ln)
        if m:
            out.append(("h" + str(len(m.group(1))), m.group(2).strip()))
            i += 1
            continue
        for kind, pat in (("table", r"\|"), ("ol", r"\d+\. "), ("ul", r"- "), ("quote", r"> ?")):
            if re.match(pat, ln):
                j = i
                while j < len(lines) and re.match(pat, lines[j]):
                    j += 1
                out.append((kind, [l.rstrip() for l in lines[i:j]]))
                i = j
                break
        else:
            if BTN_LINE.match(ln.strip()):     # 줄 전체가 링크 = CTA 버튼 줄 → 따로
                out.append(("p", ln.strip()))
                i += 1
                continue
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r"(:::|<!--|#|\||\d+\. |- |>)", lines[j]) \
                    and not BTN_LINE.match(lines[j].strip()):
                j += 1
            out.append(("p", " ".join(l.strip() for l in lines[i:j])))
            i = j
    return out


def render(bl, inline, ol_class="cs-chk"):
    h = []
    for kind, d in bl:
        if kind == "p":
            h.append(f"<p>{inline(d)}</p>")
        elif kind == "h3":
            h.append(f"<h3>{inline(d)}</h3>")
        elif kind == "ol":
            items = [re.sub(r"^\d+\.\s*", "", l) for l in d]
            if ol_class == "cs-chk":
                h.append('<ol class="cs-chk">' + "".join(f"<li><span>{inline(x)}</span></li>" for x in items) + "</ol>")
            else:
                h.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
        elif kind == "ul":
            h.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in d) + "</ul>")
        elif kind == "quote":
            h.append(f'<blockquote class="cs-q">{inline(" ".join(re.sub(r"^> ?", "", l) for l in d))}</blockquote>')
        elif kind == "table":
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in d]
            if len(rows) < 2 or not re.match(r"^:?-+:?$", rows[1][0]):
                E(f"표 머리 구분줄이 없음: {d[0][:40]}")
                continue
            th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[2:])
            wide = max(len(plain(inline(r[0]))) for r in rows[2:]) > 8 if rows[2:] else False  # 첫 칸이 길면 줄바꿈 허용 (사이트 .check)
            h.append(f'<div class="hta-table{" check" if wide else ""}"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')
        elif kind == "box":
            h.append(render_box(d, inline))
        elif kind == "label":
            E(f"섹션 라벨 위치가 이상함 (H2 바로 위가 아님): {d}")
        else:
            E(f"이 자리에 올 수 없는 블록: {kind} {str(d)[:30]}")
    return "\n".join(h)


TRIAL = {"pending": False}
TRIAL_MARK = "◆ 실습 필요"          # 본문 자리 표시 상자 (D79) — after_publish.py가 공개 글에서 찾는다
TRIAL_TITLE = "[실습 필요] "        # Ghost 제목(title)에만 붙인다. meta_title·og_title·slug에는 붙이지 않는다


def box_text(inner, inline):
    return "".join(f"<p>{inline(d)}</p>" if k == "p" else render([(k, d)], inline, "plain") for k, d in inner)


def render_box(d, inline):
    typ, label, inner = d
    if typ == "matome":
        txt = " ".join(inline(x) for k, x in inner if k == "p")
        return (f'<div class="hta-say"><img alt="" src="{HIKARI["say"]}"><p class="hta-say-b">'
                f'<b>{html.escape(label)}</b>{txt}</p></div>')
    if typ == "rep":
        txt = " ".join(inline(x) for k, x in inner if k == "p")
        return (f'<div class="hta-say"><img alt="" src="{YANG_FACE}"><p class="hta-say-b">'
                f'<b>{html.escape(label)}</b>{txt}</p></div>')
    if typ == "note":
        return f'<div class="cs-lim"><strong>{html.escape(label)}：</strong>{box_text(inner, inline)}</div>'
    if typ == "cta":
        return ("CTA", label, inner)  # 호출한 쪽에서 처리
    if typ == "trial":   # 사람 실습 자리 표시 (D79) — 미리보기에서 눈에 띄게, 발행 전에 반드시 채운다
        TRIAL["pending"] = True
        return ('<div class="cs-trial-pending" style="border:3px dashed #d33;background:#fff4f2;padding:16px;'
                'margin:16px 0;border-radius:8px"><p style="margin:0 0 8px;font-weight:700;color:#c00">'
                f'{TRIAL_MARK} — 이 섹션은 팀원 실습 뒤 에이전트가 채운다. 이 상자가 있는 동안 발행하지 않는다</p>'
                f'{box_text(inner, inline)}</div>')
    E(f"본문 안에 올 수 없는 상자: :::{typ} {label}")
    return ""


def cta_parts(label, inner, inline, cta_map):
    c = cta_map.get(label)
    if not c:
        E(f"CTA 종류 「{label}」가 cta.json에 없음")
        return None
    if c["link"] is None:
        E(f"CTA 「{label}」의 링크가 사이트에 없음 (cta.json link null) — 사람에게 묻는다")
        return None
    texts, btn = [], None
    for k, x in inner:
        if k != "p":
            continue
        m = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", x.strip())
        if m:
            url = m.group(2).removeprefix(SITE)
            if m.group(1) != c["button"] or url != c["link"]:
                E(f"CTA 「{label}」 버튼 「{m.group(1)}」({url}) ≠ cta.json 「{c['button']}」({c['link']})")
            btn = (m.group(1), url)
        else:
            texts.append(inline(x))
    if not btn:
        E(f"CTA 「{label}」에 버튼 링크 줄이 없음")
        return None
    return {"kicker": c["kicker"], "texts": texts, "btn": btn}


IMG_OK = re.compile(r"^(CC0|Public domain|PD\b|CC BY(-SA)? \d(\.\d)?|編集部作成)", re.I)


def figure(it, out_dir, n):
    """images.json 한 항목 → <figure> (D55). 출처·라이선스는 figcaption에"""
    cap = html.escape(it["caption"])
    if it["kind"] == "diagram":
        svg = (out_dir / it["src"]).read_text()
        svg = re.sub(r"<\?xml[^>]*>\s*", "", svg)
        svg = re.sub(r'id="([^"]+)"', lambda m: f'id="fig{n}-{m.group(1)}"', svg)
        svg = re.sub(r'aria-labelledby="([^"]+)"', lambda m: f'aria-labelledby="fig{n}-{m.group(1)}"', svg)
        return f'<figure class="cs-fig">{svg.strip()}<figcaption>{cap}</figcaption></figure>'
    where = "Wikimedia Commons" if it["kind"] == "commons" else "米国政府の著作物"
    credit = (f'写真：<a href="{html.escape(it["page"])}">{html.escape(it["credit"])}</a> / '
              f'<a href="{html.escape(it.get("license_url", ""))}">{html.escape(it["license"])}</a>（{where}）')
    return (f'<figure class="cs-fig"><img alt="{html.escape(it["alt"])}" src="{html.escape(it["src"])}" loading="lazy">'
            f'<figcaption>{cap} {credit}</figcaption></figure>')


def track(slug, pos):
    return f'data-track="cta_click" data-track-label="{slug}" data-track-location="blog_post" data-track-position="{pos}"'


# ---------- HTML 짝 점검 ----------
class Balance(HTMLParser):
    VOID = {"img", "br", "hr", "meta", "link", "input"}

    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            E(f"HTML 태그 짝이 맞지 않음: </{tag}> (열린 것 {self.stack[-3:]})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def http_status(url):
    p = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-L", "--max-time", "20", "-A", UA,
                        "-w", "%{http_code}", "--", url], capture_output=True, text=True)
    return p.stdout.strip() or "ERR"


def next_weekday_8(now):
    d = now.astimezone(JST)
    cand = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if cand <= d:
        cand += timedelta(days=1)
    while cand.weekday() >= 5 or cand.strftime("%Y-%m-%d") in JP_HOLIDAYS:
        cand += timedelta(days=1)
    return cand


def published_today(root, now):
    n = 0
    for p in (root / "briefs" / "done").glob("*/*.md"):
        f, _ = front(p.read_text())
        dt = parse_dt(f.get("published_at", ""))
        if dt and dt.astimezone(JST).date() == now.astimezone(JST).date():
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--now")
    a = ap.parse_args()
    root = Path(a.root)
    dpath = root / a.draft if not Path(a.draft).is_absolute() else Path(a.draft)
    now = parse_dt(a.now) if a.now else datetime.now(JST)
    text = dpath.read_text()
    fm, body = front(text)
    slug = fm.get("slug") or dpath.stem
    cta_map = {k: v for k, v in json.loads((HERE / "cta.json").read_text()).items() if not k.startswith("_")}

    # --- 카드·대조 상태 ---
    card_p = root / "briefs" / f"{slug}.md"
    card, _ = front(card_p.read_text()) if card_p.exists() else ({}, "")
    if not card:
        E(f"주제 카드 없음: {card_p}")
    elif card.get("status") != "발행 준비":
        E(f"카드 상태가 「발행 준비」가 아님: {card.get('status')}")
    fc_p = root / "factcheck" / f"{slug}.md"
    fc, _ = front(fc_p.read_text()) if fc_p.exists() else ({}, "")
    if fc.get("result") != "통과":
        E(f"대조 보고서 result가 통과가 아님: {fc.get('result')}")
    if card.get("polish") and not fc.get("rechecked_at"):
        E("다듬기 뒤 재대조(rechecked_at)가 없음 — blog-factcheck --recheck")
    route = card.get("route", fm.get("route", ""))
    deadline = parse_dt(card.get("deadline", ""))
    if route == "속보":
        if not deadline:
            E("속보인데 카드에 deadline이 없음")
        elif now > deadline:
            E(f"속보 마감 {deadline:%m/%d %H:%M}이 지남 — 속보로 발행하지 않는다. 깊이 있는 글로 돌린다 (D34, 사람에게 알림)")
        elif deadline - now < timedelta(hours=6):
            W(f"속보 마감까지 {(deadline - now).seconds // 3600}시간 — 미리보기 확인을 서둘러야 함")
    today = published_today(root, now)
    if today >= DAILY_CAP:
        E(f"오늘 이미 {today}편 발행 — 하루 상한 {DAILY_CAP}편 (common.md 7장 B). 사람에게 묻는다")

    # --- 본문 나누기 ---
    lines = body.splitlines()
    try:
        i_src = next(i for i, l in enumerate(lines) if l.strip() == "## SOURCES")
    except StopIteration:
        E("## SOURCES 없음")
        return report(slug, None)
    i_end = next((i for i in range(i_src + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    srcs, s2n = parse_sources(lines[i_src + 1:i_end])
    main_lines = lines[:i_src]
    title = next((l[2:].strip() for l in main_lines if l.startswith("# ")), "")
    if not title:
        E("# 제목 없음")
    main_lines = [l for l in main_lines if not l.startswith("# ")]
    inline = make_inline(s2n, srcs)
    bl = blocks(main_lines)

    # --- 앞부분 (첫 라벨/H2 전) ---
    k = next((i for i, b in enumerate(bl) if b[0] in ("label", "h2")), len(bl))
    pre, rest = bl[:k], bl[k:]
    lead, key, readers, guide = [], "", [], ""
    for kind, d in pre:
        if kind == "p":
            lead.append(f"<p>{inline(d)}</p>")
        elif kind == "box" and d[0] == "box" and d[1] == "3行まとめ":
            items = [re.sub(r"^\d+\.\s*", "", l) for kk, dd in d[2] if kk == "ol" for l in dd]
            if len(items) != 3:
                E(f"3行まとめ가 {len(items)}줄 (3줄)")
            key = ('<div class="cs-key"><b>3行まとめ</b><ol>' +
                   "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol></div>")
        elif kind == "box" and d[0] == "box":
            items = [l[2:] for kk, dd in d[2] if kk == "ul" for l in dd]
            cls, icon = ("cs-rc out", "!") if "わかる" in d[1] else ("cs-rc", "?")
            rt = "この記事はこんな方に" if cls == "cs-rc" else d[1]
            readers.append(f'<section class="{cls}"><p class="rc-title"><i aria-hidden="true">{icon}</i>{html.escape(rt)}</p>'
                           "<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul></section>")
        elif kind == "box" and d[0] == "guide":
            ps = [inline(x) for kk, x in d[2] if kk == "p"]
            if ps and ps[0].startswith("こんにちは、ヒカリです。") and len(ps[0]) > len("こんにちは、ヒカリです。"):
                ps = ["こんにちは、ヒカリです。", ps[0][len("こんにちは、ヒカリです。"):].strip()] + ps[1:]
            first, more = (ps[0], ps[1:]) if ps else ("", [])
            guide = (f'<div class="hta-hikari"><div class="hta-hikari-fig"><img alt="手を広げて案内するヒカリちゃん" '
                     f'src="{HIKARI["guide"]}"></div><div class="hta-hikari-copy"><span class="kicker">{html.escape(d[1])}</span>'
                     f'<p class="hi">{first}</p>' + "".join(f"<p>{x}</p>" for x in more) + "</div></div>")
        else:
            E(f"글 머리에 올 수 없는 블록: {kind} {str(d)[:30]}")
    if not lead:
        E("리드 문단이 없음")
    if not key:
        E("3行まとめ 상자가 없음 (D47)")

    # --- 섹션 ---
    sections, toc, faq_items, faq_title = [], [], [], ""
    end_ctas, label, cur = [], None, None
    for idx, (kind, d) in enumerate(rest):
        if kind == "label":
            label = d
            continue
        if kind == "h2":
            if d.strip().upper() == "FAQ" or "よくある質問" in d:   # D54
                cur = {"faq": True}
                faq_title = "よくある質問"
            else:
                cur = {"faq": False, "h2": d, "label": label, "blocks": []}
                sections.append(cur)
                if not label:
                    W(f"H2 「{d}」 위에 라벨 주석(<!-- NN Label -->)이 없음 — 번호 없이 낸다")
            label = None
            continue
        if kind == "box" and d[0] == "cta":
            tail = rest[idx + 1:]
            if all(k2 == "box" and d2[0] == "cta" for k2, d2 in tail):
                end_ctas.append(d)
                continue
        if cur is None:
            E(f"H2 앞에 블록: {kind}")
            continue
        if cur["faq"]:
            if kind == "h3":
                faq_items.append({"q": d, "a": []})
            elif kind == "p" and faq_items:
                faq_items[-1]["a"].append(d)
            else:
                E(f"FAQ 안에 올 수 없는 블록: {kind}")
            continue
        cur["blocks"].append((kind, d))

    out_dir = root / "publish" / slug
    imgs = json.loads((out_dir / "images.json").read_text()) if (out_dir / "images.json").exists() else []
    imgs_keep = [it for it in imgs if it.get("keep", True)]
    for it in imgs_keep:
        if not 1 <= it.get("section", 0) <= len(sections):
            E(f"이미지 {it.get('n')}: section {it.get('section')}이 본문 H2 범위(1~{len(sections)}) 밖")
        if len(it.get("alt", "")) < 10 or not it.get("caption"):
            E(f"이미지 {it.get('n')}: alt(10자 이상)·caption이 필요")
        if not IMG_OK.search(it.get("license", "")) or re.search(r"\b(NC|ND)\b", it.get("license", "")):
            E(f"이미지 {it.get('n')}: 쓸 수 없는 라이선스 「{it.get('license')}」 (rules/blog-publish.md 본문 이미지)")
        if it["kind"] != "diagram" and not it.get("page"):
            E(f"이미지 {it.get('n')}: 출처 페이지(page)가 없음")
    cap_n = 2 if route == "속보" else 4
    if len(imgs_keep) > cap_n:
        W(f"본문 이미지 {len(imgs_keep)}장 — {route or '일반'} 글은 {cap_n}장까지")
    img_table = "| 번호 | 종류 | 넣은 곳 | 출처 · 라이선스 | 설명 | 판단 |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {it['n']} | {it['kind']} | 섹션 {it['section']} | {it.get('page', '편집부 작성')} · {it['license']} | {it['caption']} | "
        f"{'남김(기본)' if it.get('keep', True) else '뺌'} |" for it in imgs) if imgs else "- 없음"

    sec_html = []
    for n, s in enumerate(sections, 1):
        parts = []
        figs = [figure(it, out_dir, it["n"]) for it in imgs_keep if it.get("section") == n]
        for kind, d in s["blocks"]:
            if kind == "box" and d[0] == "cta":
                c = cta_parts(d[1], d[2], inline, cta_map)
                if c:
                    parts.append(f'<div class="cs-midcta"><span class="kicker">{html.escape(c["kicker"])}</span>' +
                                 "".join(f"<p>{t}</p>" for t in c["texts"]) +
                                 f'<a class="btn" {track(slug, "mid")} href="{c["btn"][1]}">{html.escape(c["btn"][0])}</a></div>')
            else:
                parts.append(render([(kind, d)], inline))
            if figs and len(parts) == 1:   # 직답(섹션 첫 블록) 바로 아래에
                parts.extend(figs)
                figs = []
        parts.extend(figs)
        num = (f'<span class="cs-num"><b>{n:02d}</b>{html.escape(s["label"][1])}</span>\n' if s["label"] else "")
        sec_html.append(f'<section class="cs-sec" id="s{n}">\n{num}<h2>{inline(s["h2"])}</h2>\n' + "\n".join(parts) + "\n</section>")
        toc.append(f'<li><a href="#s{n}">{html.escape(plain(inline(s["h2"])))}</a></li>')

    faq_html, faq_ld = "", None
    if faq_items:
        faq_html = (f'<section class="cs-faq">\n<span class="kicker">FAQ</span>\n<h2>{faq_title}</h2>\n' +
                    "\n".join(f'<div class="faq-i">\n<h3>{inline(f["q"])}</h3>\n' +
                              "".join(f"<p>{inline(x)}</p>" for x in f["a"]) + "\n</div>" for f in faq_items) + "\n</section>")
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": "ja",
                  "mainEntity": [{"@type": "Question", "name": plain(inline(f["q"])),
                                  "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"(?<=[。！？])\s+", "", " ".join(plain(inline(x)) for x in f["a"]))}}
                                 for f in faq_items]}

    for s in srcs:
        if not s["used"]:
            E(f"SOURCES {s['n']}번이 본문에서 쓰이지 않음")
    src_html = '<section class="cs-src">\n<h2>SOURCES</h2>\n<ol>\n' + "\n".join(source_li(s) for s in srcs) + "\n</ol>\n</section>"

    # --- 글 끝 CTA ---
    cta_html, side = "", ""
    mains = [cta_parts(d[1], d[2], inline, cta_map) for d in end_ctas]
    if not end_ctas:
        E("글 끝 CTA(:::cta)가 없음")
    elif all(mains):
        m0 = mains[0]
        lead_t = m0["texts"][0] if m0["texts"] else ""
        sub = ""
        for c in mains[1:]:
            pre_t = (c["texts"][0] + " ") if c["texts"] else ""
            sub += f'<p class="cta-sub">{pre_t}<a {track(slug, "end_sub")} href="{c["btn"][1]}">{html.escape(c["btn"][0])}</a></p>'
        cta_html = (f'<div class="cs-cta has-hikari">\n<div class="cs-cta-copy">\n<span class="kicker">{html.escape(m0["kicker"])}</span>\n'
                    + (f"<h2>{lead_t}</h2>\n" if lead_t else "") + "".join(f"<p>{t}</p>" for t in m0["texts"][1:]) +
                    f'<a class="btn" {track(slug, "end")} href="{m0["btn"][1]}">{html.escape(m0["btn"][0])}</a>\n{sub}\n</div>\n'
                    f'<div class="cs-cta-hikari"><img alt="" src="{HIKARI["cta"]}"></div>\n</div>')
        side = (f'<div class="cs-sidecta">\n<b>{html.escape(m0["kicker"])}</b>\n'
                f'<a class="btn" {track(slug, "side")} href="{m0["btn"][1]}">{html.escape(m0["btn"][0])}</a>\n</div>')

    # --- 글 머리 보드 (D65): 사이트는 본문 카드 맨 앞 hta-top에서 분류 줄·태그 알약·번호를 읽어
    #     글 머리(전체 폭 대표 이미지 + 흰 보드)를 만든다. 기존 글 130편이 모두 이 블록을 가진다 ---
    bp = root / "publish" / slug / "board.json"
    board = json.loads(bp.read_text()) if bp.exists() else {}
    # site_axis: 사이트 분류(태그·글 머리)만 다른 축으로 둘 때 — 사람이 정한 카드만 (D68)
    series = TAGS.get("board", {}).get(card.get("site_axis") or card.get("axis", ""), {})
    top_html = ""
    if not series:
        E(f"주제 축 「{card.get('site_axis') or card.get('axis', '')}」의 글 머리 분류(tags.json board)가 없음 — 사람에게 묻는다")
    elif not board:
        E(f"publish/{slug}/board.json 없음 — 글 머리 보드 값(kind·cat·no)을 SKILL 3장대로 쓴다 (D65)")
    else:
        cat_parts = [x.strip() for x in str(board.get("cat", "")).split("·") if x.strip()]
        if not board.get("kind") or not 2 <= len(cat_parts) <= 4 or not board.get("no"):
            E("board.json: kind(굵은 글씨 1개)·cat(「·」로 2~4개)·no(번호 표시)가 모두 있어야 함")
        if series.get("topic") and not board.get("topic"):
            E(f"board.json topic이 없음 — 「{series['crumb']} · <topic> · <kind>」 (예: {series['topic']})")
        if board.get("no") and not str(board["no"]).startswith(series["no"]):
            E(f"board.json no는 「{series['no']}」로 시작 (기존 글과 같은 줄)")
        mins = max(1, round(len(plain(re.sub(r"<script.*?</script>", "", "".join(sec_html), flags=re.S))) / 600))
        info = [f"{series['time']} 約{mins}分", f"更新日 {now:%Y.%m.%d}"]
        top_html = ('<div class="hta-top">\n<div class="hta-w">\n'
                    f'<p class="cs-crumb">{html.escape(" · ".join(x for x in (series["crumb"], board.get("topic", "")) if x))} · <b>{html.escape(board.get("kind", ""))}</b></p>\n'
                    f'<div class="cs-tags">\n<span class="cs-cat"><i></i>{html.escape(" · ".join(cat_parts))}</span>\n'
                    f'<span class="cs-no">{html.escape(str(board.get("no", "")))}</span>\n</div>\n'
                    '<div class="cs-info">\n' + "\n".join(f"<span>{x}</span>" for x in info) + "\n</div>\n</div>\n</div>")

    readers_html = (f'<div class="cs-readers{"" if len(readers) > 1 else " single"}">\n' + "\n".join(readers) + "\n</div>") if readers else ""
    body_html = "\n".join(x for x in [
        "<!--kg-card-begin: html-->", '<div class="ondi-article">', '<div class="hta">', top_html, '<div class="hta-w">',
        '<div class="cs-lead">' + "".join(lead) + "</div>", key, readers_html, guide,
        '<div class="cs-wrap">', '<aside class="cs-side">',
        '<nav aria-label="目次" class="cs-toc">\n<p class="toc-title">CONTENTS</p>\n<ol>\n' + "\n".join(toc) + "\n</ol>\n</nav>",
        side, "</aside>", '<article class="cs-body">', *sec_html, faq_html, src_html, cta_html, "</article>",
        "</div>", "</div>", "</div>", "</div>",
        (f'<script type="application/ld+json">{json.dumps(faq_ld, ensure_ascii=False, separators=(",", ":"))}</script>' if faq_ld else ""),
        "<!--kg-card-end: html-->"] if x)
    css = (HERE / "template" / "hikari-base.css").read_text() + (HERE / "template" / "extra.css").read_text()
    style_html = f"<!--kg-card-begin: html-->\n<style>\n{css}\n</style>\n<!--kg-card-end: html-->"

    # --- 남은 표시·짝 점검 ---
    vis = re.sub(r"<!--kg-card-(begin|end): html-->", "", body_html)
    vis = re.sub(r'<script type="application/ld\+json">.*?</script>', "", vis, flags=re.S)
    for pat, what in ((r"\[S\d+\]", "[S번호]"), (r"\[(EXP|OP|\?)\]", "[EXP]/[OP]/[?]"), (r"<!--", "주석"),
                      (r"^:::|\n:::", ":::"), (r"\*\*", "**"), (r"\]\(", "링크 표기 ]("), (r"초안 메모|다듬기 메모", "메모 절")):
        if re.search(pat, vis):
            E(f"변환 뒤에도 {what}가 남음")
    Balance().feed(body_html)
    for u in re.findall(r'href="(/ja/blog/[^"#]+)"', body_html):
        ex = root / "topics" / "existing_posts.json"
        if ex.exists() and (SITE + u) not in ex.read_text():
            W(f"내부 링크 {u}가 topics/existing_posts.json에 없음 — 글이 있는지 확인")
    if a.check_links:
        urls = sorted(set([SITE + u if u.startswith("/") else u for u in re.findall(r'href="([^"#]+)', body_html)] +
                          [s["url"] for s in srcs]))
        for u in urls:
            st = http_status(u)
            if st != "200":
                (E if "atatakaidigital.com" in u else W)(f"링크 {st}: {u}")

    # --- 메타·대표 이미지 ---
    meta = {k: fm.get(k, "") for k in ("seo_title", "meta", "og_title", "og_description", "excerpt")}
    for k, v in meta.items():
        if not v:
            E(f"초안 머리 {k}가 비어 있음 (blog-polish 5장)")
    out = root / "publish" / slug
    hero = out / f"{slug}_hero.webp"
    hero_info = "아직 없음 — make_hero.py로 만든다"
    if hero.exists():
        try:
            from PIL import Image
            im = Image.open(hero)
            kb = hero.stat().st_size / 1024
            hero_info = f"{hero.name} {im.size[0]}×{im.size[1]} {im.format} {kb:.0f}KB"
            if im.size[0] < 1200 or abs(im.size[0] / im.size[1] - 1800 / 945) > 0.01 or im.format != "WEBP" or kb > 200:
                E(f"대표 이미지 규격 아님: {hero_info} (1.905:1, 폭 1200~1800, WebP 200KB 이하 — make_hero.py)")
        except ImportError:
            W("Pillow 없음 — 대표 이미지 규격을 확인하지 못함")
    alt_p = out / "hero_alt.txt"
    hero_alt = alt_p.read_text().strip() if alt_p.exists() else ""

    if errs:
        return report(slug, None)

    out.mkdir(parents=True, exist_ok=True)
    (out / "card1-style.html").write_text(style_html + "\n")
    (out / "card2-body.html").write_text(body_html + "\n")
    hero_tag = f'<img src="{hero.name}" alt="{html.escape(hero_alt)}" style="width:100%;max-width:1200px;display:block;margin:0 auto 24px">' if hero.exists() else '<p style="text-align:center;color:#c00">[대표 이미지 아직 없음]</p>'
    (out / "preview.html").write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>body{{margin:0;background:#f7f5ef;font-family:'Hiragino Sans','Noto Sans JP',sans-serif}}"
        ".pv-head{max-width:59rem;margin:0 auto;padding:32px 24px 8px;color:#18394b}.pv-head h1{font-size:28px;line-height:1.4;margin:8px 0}"
        ".pv-note{background:#fff3cd;padding:8px 16px;font-size:12px}</style></head><body>"
        '<div class="pv-note">로컬 미리보기 (blog-publish). 사이트 머리·글꼴은 실제와 다르다 — ◆ 최종 확인은 Ghost 미리보기에서</div>'
        f'<header class="pv-head">{hero_tag}<h1>{html.escape(title)}</h1><p>{html.escape(meta["excerpt"])}</p></header>'
        f'<div class="ondi-prose">\n{style_html}\n{body_html}\n</div></body></html>\n')
    if str(now.year) not in {d[:4] for d in JP_HOLIDAYS}:
        W(f"{now.year}년 일본 공휴일이 JP_HOLIDAYS에 없음 — 예약 시각이 공휴일일 수 있다")
    when = "확인 즉시 (속보)" if route == "속보" else f"{next_weekday_8(now):%Y-%m-%d %H:%M} JST 예약 (평일 오전 8시)"
    seo_title = title if meta["seo_title"] in ("", "-") else meta["seo_title"]
    # D79: 실습 자리 표시가 있으면 Ghost 제목에만 표시 — 사람이 Ghost 목록에서 알아보게
    ghost_title = TRIAL_TITLE + title if TRIAL["pending"] else title
    trial_note = (f"\n> ⚠ **{TRIAL_TITLE.strip()} — 발행 금지.** 「使ってみた」 섹션이 자리 표시(◆ 실습 필요)다. "
                  f"팀원이 실습 문서에 결과를 적고 「실습 끝났어 {slug}」 → 에이전트가 채워 같은 초안을 갱신하고 제목 표시를 뗀다 (D79)\n"
                  if TRIAL["pending"] else "")
    axis = card.get("site_axis") or card.get("axis", "")   # D68
    tags = tag_slugs(axis, route, card.get("type", fm.get("type", "")))
    if not TAGS["axis"].get(axis):
        W(f"주제 축 「{axis}」의 사이트 태그가 tags.json에 없음 — 사람에게 묻는다 (지금은 ja만)")
    (out / "ghost.md").write_text(f"""---
slug: {slug}
built_at: {now:%Y-%m-%dT%H:%M%z}
draft: {a.draft}
---

# Ghost 입력값: {ghost_title}

> blog-publish 임시 방식 (D23·D50). Ghost 관리 화면에서 **초안(Draft)** 으로 만들고, ◆ 미리보기 확인 뒤 사람이 발행·예약한다 (철칙 2)
{trial_note}
## 1. 본문 (HTML 카드 2개, 순서대로)
1. 새 글 → 본문에서 `/html` → HTML 카드에 `card1-style.html` 전체를 붙여 넣는다
2. 그 아래 HTML 카드 하나 더 → `card2-body.html` 전체를 붙여 넣는다
- 다른 카드·글은 넣지 않는다 (기존 글과 같은 구성: 스타일 카드 + 본문 카드)

## 2. 글 설정 (오른쪽 ⚙)
| 칸 | 넣을 값 |
|---|---|
| Post title | {ghost_title} |
| Post URL (slug) | {slug} — 발행 뒤 바꾸지 않는다 |
| Excerpt | {meta["excerpt"]} |
| Tags | {" → ".join(f"`{t}`" for t in tags)} (이 순서, 기존 태그만 — tags.json) |
| Authors | `ひかり` (Ghost 스태프 slug `hikari`, D38) — ghost_upload.py가 자동으로 넣는다 |
| Feature image | `{hero.name}` / alt: {hero_alt or "(hero_alt.txt 없음)"} |
| Visibility | Public (전체 공개) |
| Code injection | 비워 둔다 (FAQ 구조화 데이터는 카드 2 끝에 들어 있음) |

## 3. Meta data · X card · Facebook card
| 칸 | 넣을 값 | 전각 |
|---|---|---|
| Meta title | {seo_title} | {zen_len(seo_title):g} |
| Meta description | {meta["meta"]} | {zen_len(meta["meta"]):g} |
| X·Facebook title | {meta["og_title"]} | {zen_len(meta["og_title"]):g} |
| X·Facebook description | {meta["og_description"]} | {zen_len(meta["og_description"]):g} |
| X·Facebook image | 대표 이미지와 같음 (따로 넣지 않는다) | |

## 4. 발행
- 시각: **{when}**
- ⚠ Publish 화면에서 **「Publish only」(이메일 보내지 않음)** 를 고른다 — 뉴스레터는 주 1회 따로 (D21)
- 대표 이미지: {hero_info} (만드는 법: `hero_prompt.md` → make_hero.py)

## 4-2. 본문 이미지 (◆ 남길지 뺄지 사람이 정한다, D55)
{img_table}
- 빼려면 에이전트에게 「이미지 N 빼」 → find_images.py drop → 파일을 다시 만든다
- 사진은 원본 사이트(Wikimedia 등)의 주소를 그대로 쓴다. Ghost API 연동 뒤에는 Ghost에 올려서 바꾼다

## 5. ◆ 미리보기 확인 (사람)
- [ ] 제목에 「{TRIAL_TITLE.strip()}」, 본문에 「{TRIAL_MARK}」 상자가 **없다** (있으면 발행하지 않는다, D79)
- [ ] 제목·첫 문단(리드)·3行まとめ가 맞다
- [ ] CTA 버튼이 열린다 — 글 끝·옆 칸
- [ ] 대표 이미지가 보이고 잘리지 않는다
- [ ] 휴대폰 화면 (Ghost 미리보기의 Mobile)에서 표·상자가 넘치지 않는다
- [ ] 본문 이미지: 글과 맞는지, 출처 표기가 보이는지 — 이미지마다 남김/뺌 (4-2 표)
- [ ] 글 끝 SOURCES 링크가 열린다
- [ ] 이메일 발송이 꺼져 있다 (Publish only)
- 확인 뒤 발행·예약하고 에이전트에게: 「발행했어 {slug} <글 URL>」 (예약이면 「예약했어 {slug} <URL> <YYYY-MM-DD HH:MM>」)
""")
    # ghost_upload.py가 읽는 값 (D62) — ghost.md와 같은 값
    (out / "ghost.json").write_text(json.dumps({
        "slug": slug, "built_at": f"{now:%Y-%m-%dT%H:%M%z}", "title": ghost_title, "custom_excerpt": meta["excerpt"],
        "trial_pending": TRIAL["pending"],
        "meta_title": seo_title, "meta_description": meta["meta"],
        "og_title": meta["og_title"], "og_description": meta["og_description"],
        "twitter_title": meta["og_title"], "twitter_description": meta["og_description"],
        "tag_slugs": tags,
        "feature_image_file": hero.name if hero.exists() else "", "feature_image_alt": hero_alt,
    }, ensure_ascii=False, indent=1) + "\n")
    ct = card_p.read_text()
    line = f"publish: publish/{slug}/ ({now:%Y-%m-%d})"
    ct = re.sub(r"(?m)^publish: .*$", line, ct, count=1) if re.search(r"(?m)^publish: ", ct) else \
        re.sub(r"\n---\n", "\n" + line + "\n---\n", ct, count=1)
    card_p.write_text(ct)
    report(slug, out)


def report(slug, out):
    for w in warns:
        print("⚠", w)
    for e in errs:
        print("❌", e)
    if errs:
        print(f"불통과 — 오류 {len(errs)}개 (파일을 쓰지 않음)")
        sys.exit(1)
    print(f"통과 — publish/{slug}/ (card1-style.html · card2-body.html · preview.html · ghost.md · ghost.json)")
    if TRIAL["pending"]:
        print(f"◆ 실습 자리 표시 있음 — Ghost 제목 「{TRIAL_TITLE.strip()} …」, 업로드 뒤 카드 「실습 대기」 (D79)")


if __name__ == "__main__":
    main()
