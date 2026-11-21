"""blog-distribute 공통: sns.md 읽기·경로 찾기·UTM (check_sns.py, sns_post.py가 같이 쓴다)

sns.md 형식 (rules/blog-distribute.md 「sns.md」):
  ---
  slug: <slug>
  url: https://atatakaidigital.com/ja/blog/<slug>
  created_at: 2026-11-21T15:00+09:00
  hero: <대표 이미지 경로>
  ---
  # SNS 문안: <글 제목>
  ## x            ← 플랫폼 이름 (x / threads / note / linkedin / facebook)
  ### 本文
  ```text
  ...
  ```
  ### 返信        ← X: 링크 답글 / LinkedIn: ### 最初のコメント / Facebook: ### リンク
  ```text
  ...
  ```
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "blog-publish"))
from after_publish import front, set_front  # noqa: E402,F401

PLATFORMS = ["x", "threads", "note", "linkedin", "facebook"]
# 본문 말고 따로 두는 칸: 플랫폼 → (칸 이름, 들어갈 것)
EXTRA = {"x": ("返信", "링크 답글"), "linkedin": ("最初のコメント", "링크 첫 댓글"), "facebook": ("リンク", "링크 미리보기 URL")}
URL_RE = re.compile(r"https?://[^\s「」（）()<>]+")


def utm(url, platform, slug):
    return f"{url}?utm_source={platform}&utm_medium=social&utm_campaign={slug}"


def parse_sns(text):
    """→ (머리 dict, {플랫폼: {칸 이름: 글}})"""
    head = front(text)
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    out = {}
    plat = None
    sec = None
    for m in re.finditer(r"^## (\S+)\s*$|^### (\S+)\s*$|^```text\n(.*?)\n```\s*$", body, re.M | re.S):
        if m.group(1):
            plat, sec = m.group(1).strip().lower(), None
            out.setdefault(plat, {})
        elif m.group(2):
            sec = m.group(2).strip()
        elif plat and sec:
            out[plat][sec] = m.group(3).strip()
    return head, out


def month_dir(root, folder, slug, suffix):
    """done/YYYY-MM/ 안에서 slug 파일(또는 폴더)을 찾는다. 가장 최근 달"""
    hits = sorted((root / folder / "done").glob(f"*/{slug}{suffix}"))
    return hits[-1] if hits else None


def paths(root, slug):
    """발행 완료 카드 기준의 입력·출력 경로 (BlogAgent.md 「주제 카드의 상태와 정리」)"""
    card = month_dir(root, "briefs", slug, ".md")
    if not card:
        sys.exit(f"❌ briefs/done/*/{slug}.md 없음 — 발행 완료 카드만 배포한다 (먼저 blog-publish 「발행했어」)")
    month = card.parent.name
    return {"card": card, "draft": root / "drafts" / "done" / month / f"{slug}.md",
            "outline": root / "outlines" / "done" / month / f"{slug}.md",
            "dir": root / "publish" / "done" / month / slug,
            "sns": root / "publish" / "done" / month / slug / "sns.md"}


DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|오늘|today)$")


def is_date(arg):
    return bool(DATE_RE.match(arg or ""))


def to_slug(arg):
    """slug·파일 이름·경로·글 주소 어느 것이든 slug로: briefs/x.md → x, publish/done/…/x/sns.md → x, https://…/blog/x?utm… → x"""
    s = (arg or "").strip()
    if s.startswith("http"):
        s = s.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    p = Path(s)
    if p.name in ("sns.md", "sns_posted.json"):
        return p.parent.name
    return p.name[:-3] if p.name.endswith(".md") else p.name
