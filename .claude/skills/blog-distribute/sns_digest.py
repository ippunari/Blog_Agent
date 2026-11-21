#!/usr/bin/env python3
"""blog-distribute: 날짜별 모음 파일 sns/YYYY-MM-DD.md — 그날 발행한 글의 SNS 문안을 발행 순으로 모은 보기용 파일 (D66 보강)

원본은 글별 publish/done/YYYY-MM/<slug>/sns.md. 이 파일은 check_sns.py·sns_post.py가 돌 때마다 다시 만든다 (손으로 고치지 않는다)
사람은 이 파일(또는 같은 내용의 공유 드라이브 시트)을 보고 「올려」 하고, ✋ 표시(X·note)는 위에서부터 복사해 붙여 넣는다

사용법:
  python3 -I sns_digest.py [YYYY-MM-DD|오늘]     # 다시 만들기
  python3 -I sns_digest.py 2026-11-21 --slot 아침 --sheet <Drive 파일 ID>   # 올린 회차 시트 ID를 머리에 적기
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blog-publish"))
from sns_common import PLATFORMS, EXTRA, SLOTS, parse_sns, front, slot_of, hero_url  # noqa: E402

JST = timezone(timedelta(hours=9))
NAMES = {"x": "X", "threads": "Threads", "note": "note", "linkedin": "LinkedIn 회사 페이지", "facebook": "Facebook 페이지"}
ACCOUNTS = json.loads((HERE / "accounts.json").read_text())


def parse_date(s):
    if s in (None, "", "오늘", "today", "아침", "저녁"):
        return datetime.now(JST).strftime("%Y-%m-%d")
    datetime.strptime(s, "%Y-%m-%d")
    return s


def entries_for(root, date, slot=None):
    """그날(회차를 주면 그 회차) 발행한 글: (발행 시각, slug, 카드, sns.md) — 발행 순"""
    out = []
    for card in (root / "briefs" / "done").glob("*/*.md"):
        c = front(card.read_text())
        if not c.get("published_at", "").startswith(date):
            continue
        if slot and slot_of(c["published_at"]) != slot:
            continue
        sns = root / "publish" / "done" / card.parent.name / card.stem / "sns.md"
        out.append((c["published_at"][:16], card.stem, card, sns))
    return sorted(out)


def account(p):
    return {"test": "시험 계정", "company": "회사 계정"}.get(ACCOUNTS.get(p, {}).get("label"), "")


def status(p, done):
    """→ (기호, 설명)"""
    r = done.get(p)
    if r and not r.get("error"):
        return "✅", f"올림 {r.get('url') or r.get('id')}"
    if r:
        return "❌", f"실패 {r['error'][:80]} — 다시 「올려」"
    if p == "x":
        return "✋", "붙여 넣기 (Windsor 미지원)"
    if p == "note":
        return "✋", "붙여 넣기 (공식 API 없음)"
    return "⏳", f"「올려」 대기 · {account(p)}"


def render(date, items, sheets=None):
    sheets = sheets or {}
    lines = [f"# SNS 문안 {date}", ""] + [f"sheet-{k}: {v}" for k, v in sheets.items()] + ([""] if sheets else []) + [
             "> 보기용 모음 — 원본은 글별 sns.md (스크립트가 다시 만든다). ⏳은 「올려」로 에이전트가 올리고, ✋(X·note)는 손으로 붙여 넣는다", ""]
    if not items:
        lines.append("(이 날 발행한 글이 없음)")
    for when, slug, card, sns in items:
        c = front(card.read_text())
        if not sns.exists():
            lines += [f"## {when[11:16]} `{slug}`", "", "- 문안 없음 — `/blog-distribute " + slug + "`", ""]
            continue
        head, posts = parse_sns(sns.read_text())
        rec = sns.parent / "sns_posted.json"
        done = json.loads(rec.read_text()) if rec.exists() else {}
        title = next((ln[len("# SNS 문안: "):] for ln in sns.read_text().splitlines() if ln.startswith("# SNS 문안: ")), slug)
        lines += [f"## {slot_of(when)} {when[11:16]} {title}", "", f"- slug: `{slug}` · 글: {c.get('url') or head.get('url')}",
                  f"- 대표 이미지 (X·note 첨부): {hero_url(sns, head) or head.get('hero', '(없음)')}"]
        for p in PLATFORMS:
            lines.append(f"- {NAMES[p]}: " + " ".join(status(p, done)))
        lines.append("")
        for p in PLATFORMS:
            secs = posts.get(p, {})
            lines += [f"### {NAMES[p]}" + (f" · 切り口 {secs['切り口']}" if secs.get("切り口") else ""), ""]
            order = ["タイトル", "本文"] + ([EXTRA[p][0]] if p in EXTRA else [])
            for s in order:
                if s in secs:
                    lines += [f"**{s}**", "", "```text", secs[s], "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def build(root, date, items=None, out=None):
    root = Path(root)
    items = entries_for(root, date) if items is None else items
    out = out or root / "sns" / f"{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(date, items, sheets_of(out)))   # 회차 시트 ID는 다시 만들어도 남긴다
    return out


def sheets_of(out):
    """모음 머리의 회차별 시트 ID {아침: ID, 저녁: ID}"""
    t = Path(out).read_text() if Path(out).exists() else ""
    return {k: v for k, v in re.findall(r"^sheet-(아침|저녁): (\S+)", t, re.M)}


def set_sheet(root, date, slot, sid):
    out = Path(root) / "sns" / f"{date}.md"
    if not out.exists():
        build(root, date)
    sh = sheets_of(out)
    sh[slot] = sid
    out.write_text(render(date, entries_for(Path(root), date), dict(sorted(sh.items(), key=lambda x: SLOTS.index(x[0])))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?")
    ap.add_argument("--root", default=".")
    ap.add_argument("--slot", choices=SLOTS, help="회차 (--sheet와 함께)")
    ap.add_argument("--sheet", help="공유 드라이브에 올린 회차 시트 ID를 머리에 적는다 (sheet-아침: ID)")
    a = ap.parse_args()
    d = parse_date(a.date)
    if a.sheet:
        if not a.slot:
            sys.exit("❌ --sheet에는 --slot 아침|저녁")
        print(set_sheet(Path(a.root), d, a.slot, a.sheet))
    else:
        print(build(Path(a.root), d))


if __name__ == "__main__":
    main()
