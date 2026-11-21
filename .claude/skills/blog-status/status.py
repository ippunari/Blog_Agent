#!/usr/bin/env python3
"""blog-status: 주제 카드 진행 현황을 표 하나로 보여 준다 (읽기 전용 — 파일을 바꾸지 않는다).

briefs/*.md(진행 중) 카드 머리를 읽어 slug / 경로 / 상태 / 마감 / 노트·설계·초안·대조 보고서 유무를 표로 낸다.
done/·dropped/는 건수만 센다 (--all 이면 목록도).

사용법:
  python3 -I .claude/skills/blog-status/status.py [--root .] [--all]
"""
import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ORDER = ["조사 대기", "기존 글 업데이트", "설계 대기", "초안 대기", "대조 대기", "다듬기 대기", "실습 대기", "발행 준비", "발행 완료", "중단"]   # 실습 대기 = Ghost 초안([실습 필요]) 업로드 뒤 (D79)


def front(path):
    m = re.match(r"---\n(.*?)\n---", path.read_text(), re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            k, sep, v = ln.partition(":")
            if sep and re.match(r"^[a-z_]+$", k.strip()):
                out[k.strip()] = v.strip()
    return out


def parse_deadline(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}))?", s or "")
    if not m:
        return None, False
    d = datetime.fromisoformat(m.group(1) + "T" + (m.group(2) or "23:59")).replace(tzinfo=JST)
    return d, bool(m.group(2))


def status_name(s):
    s = (s or "").split("(")[0].strip()
    for o in ORDER:
        if s.startswith(o):
            return o
    return s or "?"


def mark(root, folder, slug):
    return "✓" if (root / folder / f"{slug}.md").exists() else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    now = datetime.now(JST)

    rows = []
    for p in sorted((root / "briefs").glob("*.md")):
        f = front(p)
        slug = f.get("slug") or p.stem
        dl, has_time = parse_deadline(f.get("deadline"))
        route = f.get("route", "?")
        kind = f.get("kind", "").split("|")[0].strip() or ("개편" if "업데이트" in f.get("status", "") else "")
        if dl:
            left = dl - now
            hours = left.total_seconds() / 3600
            dl_txt = dl.strftime("%m/%d %H:%M" if has_time else "%m/%d")
            if hours < 0:
                dl_txt += " ⚠지남"
            elif hours < 12:
                dl_txt += f" ⚠{hours:.0f}시간 남음"
            elif not has_time:
                dl_txt += " (시각 미확인)"
        else:
            dl_txt = "-"
        rows.append({
            "slug": slug, "route": route, "kind": kind, "type": f.get("type", "?"),
            "status": status_name(f.get("status")), "dl": dl, "dl_txt": dl_txt,
            "origin": f.get("origin", "시트"), "trial": f.get("trial", "-").split("|")[0].strip() or "-",
            "sel": f.get("selected_at", ""), "trial_doc": f.get("trial_doc", ""), "trial_due": f.get("trial_due", ""),
            "ghost_draft": f.get("ghost_draft", ""),
            "r": mark(root, "research", slug), "o": mark(root, "outlines", slug), "d": mark(root, "drafts", slug), "c": mark(root, "factcheck", slug),
        })

    far = datetime.max.replace(tzinfo=JST)
    rows.sort(key=lambda r: (r["route"] != "속보", r["dl"] or far, r["sel"]))

    print(f"# 진행 현황 ({now.strftime('%Y-%m-%d %H:%M')} JST) — 진행 중 {len(rows)}건")
    print()
    print("| slug | 경로 | 글 종류 | 상태 | 마감 | 노트 | 설계 | 초안 | 대조 | 실습 | 출처 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        route = r["route"] + (f"·{r['kind']}" if r["kind"] and r["kind"] != r["route"] else "")
        print(f"| {r['slug']} | {route} | {r['type']} | {r['status']} | {r['dl_txt']} | {r['r']} | {r['o']} | {r['d']} | {r['c']} | {r['trial']} | {r['origin']} |")

    print()
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("상태별: " + " / ".join(f"{s} {counts[s]}" for s in ORDER + sorted(set(counts) - set(ORDER)) if s in counts))

    todo = [r for r in rows if r["status"] == "실습 대기"]
    if todo:
        print()
        print("사람이 할 일 (실습 대기 — Ghost에 「[실습 필요]」 초안으로 올라가 있음, D79):")
        for r in todo:
            due, _ = parse_deadline(r["trial_due"])
            if due:
                h = (due - now).total_seconds() / 3600
                due_txt = due.strftime("%m/%d %H:%M") + (" ⚠지남 → 연장 / 실습 섹션 빼고 발행 / 중단 중에서 정한다" if h < 0 else " ⚠1일 안" if h < 24 else "")
            else:
                due_txt = "(기한 없음)"
            print(f"- {r['slug']}: 기한 {due_txt} / 실습 문서 {r['trial_doc'] or '(링크 없음 — blog-research에서 올리지 못함)'}"
                  f" / Ghost 초안 {r['ghost_draft'] or '(아직 안 올림)'} → 끝나면 「실습 끝났어 {r['slug']}」")

    done = sorted((root / "briefs" / "done").glob("*/*.md"))
    dropped = sorted((root / "briefs" / "dropped").glob("*.md"))
    print(f"발행 완료 {len(done)}건 (briefs/done/) / 중단 {len(dropped)}건 (briefs/dropped/)")
    if a.all:
        for p in done:
            f = front(p)
            print(f"- 발행 {p.parent.name} {p.stem} {f.get('published_at', '')} {f.get('url', '')}")
        for p in dropped:
            f = front(p)
            print(f"- 중단 {p.stem} {f.get('status', '')}")

    # 노트만 남은 것 (카드가 없는 research 파일) — 정리 누락 점검
    cards = {r["slug"] for r in rows}
    for folder, name in [("research", "조사 노트"), ("outlines", "설계안")]:
        orphans = [p.stem for p in (root / folder).glob("*.md") if p.stem not in cards]
        if orphans:
            print(f"⚠ 카드 없이 남은 {name} (done/·dropped/로 옮겨야 할 수 있음): " + ", ".join(orphans))
    return 0


if __name__ == "__main__":
    sys.exit(main())
