#!/usr/bin/env python3
"""blog-distribute: 날짜별 모음 파일 sns/YYYY-MM-DD.md — 그날 발행한 글의 SNS 문안을 발행 순으로 모은 보기용 파일 (D66 보강)

원본은 글별 publish/done/YYYY-MM/<slug>/sns.md. 이 파일은 check_sns.py·sns_post.py가 돌 때마다 다시 만든다 (손으로 고치지 않는다)
사람은 이 파일 하나를 열고 ✋ 표시가 붙은 것(note, 키가 없는 플랫폼, Facebook 개인 계정 공유)을 위에서부터 복사한다

사용법:
  python3 -I sns_digest.py [YYYY-MM-DD|오늘]     # 다시 만들기
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blog-publish"))
from sns_common import PLATFORMS, EXTRA, parse_sns, front  # noqa: E402
from ghost_upload import load_env  # noqa: E402

JST = timezone(timedelta(hours=9))
NAMES = {"x": "X", "threads": "Threads", "note": "note", "linkedin": "LinkedIn", "facebook": "Facebook 페이지"}
KEYS = {"x": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"], "threads": ["THREADS_USER_ID", "THREADS_TOKEN"],
        "linkedin": ["LINKEDIN_TOKEN", "LINKEDIN_AUTHOR_URN"], "facebook": ["FB_PAGE_ID", "FB_PAGE_TOKEN"]}


def parse_date(s):
    if s in (None, "", "오늘", "today"):
        return datetime.now(JST).strftime("%Y-%m-%d")
    datetime.strptime(s, "%Y-%m-%d")
    return s


def entries_for(root, date):
    """그날 발행한 글: (발행 시각, slug, 카드, sns.md) — 발행 순"""
    out = []
    for card in (root / "briefs" / "done").glob("*/*.md"):
        c = front(card.read_text())
        if not c.get("published_at", "").startswith(date):
            continue
        sns = root / "publish" / "done" / card.parent.name / card.stem / "sns.md"
        out.append((c["published_at"][:16], card.stem, card, sns))
    return sorted(out)


def status(p, done, env):
    if p in done:
        r = done[p]
        warn = "".join(f" ⚠ {k}" for k in r if k.endswith("_error"))
        return f"✅ 올림 {r.get('url') or r.get('id')}{warn}"
    if p == "note":
        return "✋ 붙여 넣기 (공식 API 없음)"
    if any(not env.get(k) for k in KEYS[p]):
        return "✋ 붙여 넣기 (키 없음)"
    return "⏳ 「올려」 대기"


def render(date, items, env):
    lines = [f"# SNS 문안 {date}", "",
             "> 보기용 모음 — 원본은 글별 sns.md (스크립트가 다시 만든다). ✋ 표시만 손으로 올린다. Facebook 개인 계정 공유도 사람", ""]
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
        lines += [f"## {when[11:16]} {title}", "", f"- slug: `{slug}` · 글: {c.get('url') or head.get('url')}"]
        if (env.get("SNS_ACCOUNT_LABEL") or "") == "test":
            lines.append("- ⚠ 시험 계정")
        for p in PLATFORMS:
            lines.append(f"- {NAMES[p]}: {status(p, done, env)}")
        lines.append("")
        for p in PLATFORMS:
            secs = posts.get(p, {})
            lines += [f"### {NAMES[p]}", ""]
            order = ["タイトル", "本文"] + ([EXTRA[p][0]] if p in EXTRA else [])
            for s in order:
                if s in secs:
                    lines += [f"**{s}**", "", "```text", secs[s], "```", ""]
            if p in ("x", "note"):
                lines += [f"첨부: 대표 이미지 `{head.get('hero', '')}`", ""]
    return "\n".join(lines).rstrip() + "\n"


def build(root, date, items=None, out=None):
    root = Path(root)
    items = entries_for(root, date) if items is None else items
    out = out or root / "sns" / f"{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(date, items, load_env(root)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    d = parse_date(a.date)
    print(build(Path(a.root), d))


if __name__ == "__main__":
    main()
