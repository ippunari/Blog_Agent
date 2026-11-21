#!/usr/bin/env python3
"""blog-distribute: 「올려」 준비와 기록 (D74). 이 스크립트는 SNS에 아무것도 보내지 않는다

보내는 것은 에이전트가 Windsor.ai MCP `execute_action`으로 한다 — 사람이 「올려」 한 뒤에만 (철칙 2)
  1) sns_post.py <대상>            → 안전 점검 뒤 보낼 요청 목록 (사람이 읽는 꼴). 「올려 오늘」 목록 보여 주기에도 쓴다
  2) sns_post.py <대상> --plan     → 같은 내용을 JSON으로 (에이전트가 그대로 execute_action에 넣는다)
  3) execute_action (에이전트)      → 플랫폼마다 한 번
  4) sns_post.py <slug> --record <플랫폼> --id <결과 id> [--url <게시 주소>] [--error <실패 이유>]

보내는 곳 (sns_common.WINDSOR, 이 밖의 action은 없다):
  threads  → threads / create_text_post   {text}                 본문 끝에 UTM 링크
  facebook → facebook_organic / create_post {message, link}       예약(scheduled_publish_time) 칸은 넣지 않는다
  linkedin → linkedin_organic / create_image_post {commentary(본문 + 끝 링크), image_url(대표 이미지 JPEG)}
             JPEG 주소가 없으면 create_post {commentary, link, link_title, link_description} 링크 카드 (D76)
  x·note  → 사람이 붙여 넣는다 (X는 Windsor 미지원, note는 공식 API 없음)

막는 것: 프로젝트 루트 SNS_STOP 파일(긴급 정지) / 같은 slug·플랫폼 두 번 (--force 플랫폼) / 플랫폼당 하루 DAILY_CAP건 /
  check_sns.py 오류
계정: accounts.json에 플랫폼별 test|company만 적는다 (계정 ID·이름은 적지 않는다 — 실행 때 get_connectors로 받는다)

사용법:
  python3 -I sns_post.py <slug|파일|글 주소>
  python3 -I sns_post.py <slug> --plan [--only threads,facebook]
  python3 -I sns_post.py 오늘 | 2026-11-21 [--plan]            # 그날 발행한 글 중 아직 안 올린 것
  python3 -I sns_post.py 아침 | 저녁 [--plan]                  # 오늘 그 회차 (발행 12시 전/후). 다른 날: 2026-11-21 --slot 아침
  python3 -I sns_post.py - --record-many $SP/posted.json       # 「다 올렸어」: 시트 「게시 주소」 칸 → 기록
  python3 -I sns_post.py <slug> --record threads --id 123 --post-url https://www.threads.com/...
  python3 -I sns_post.py <slug> --record x --post-url https://x.com/...     # 사람이 붙여 넣고 알려 준 것
  python3 -I sns_post.py <slug> --sns F --draft F --card F --url U --offline [--plan | --record …]   # 시험 (카드는 고치지 않는다)
기록: sns.md 옆 sns_posted.json, 발행 완료 카드의 sns_posted_at·sns_platforms, 날짜별 모음·시트용 xlsx
"""
import argparse
import contextlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sns_common import (parse_sns, paths, set_front, front, is_date, to_slug, WINDSOR, AUTO, PLATFORMS,  # noqa: E402
                        ALLOWED_ACTIONS, SLOTS, hero_url)
import sns_digest  # noqa: E402
from check_sns import check, report  # noqa: E402

JST = timezone(timedelta(hours=9))
DAILY_CAP = 10                       # common.md 7장 B 하루 게시 상한
ACCOUNTS = json.loads((HERE / "accounts.json").read_text())


def label(p):
    return ACCOUNTS.get(p, {}).get("label", "?")


def now():
    return datetime.now(JST).strftime("%Y-%m-%dT%H:%M%z")


def load_done(sns):
    rec = sns.parent / "sns_posted.json"
    return json.loads(rec.read_text()) if rec.exists() else {}


def posted_today(root, platform):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    n = 0
    for f in (root / "publish").glob("**/sns_posted.json"):
        try:
            rec = json.loads(f.read_text()).get(platform) or {}
        except json.JSONDecodeError:
            continue
        if str(rec.get("posted_at", "")).startswith(today) and not rec.get("error"):
            n += 1
    return n


def pending(sns):
    done = load_done(sns)
    return [p for p in AUTO if p not in done or done[p].get("error")]


def draft_meta(draft):
    fm = front(draft.read_text())
    title = next((ln[2:].strip() for ln in draft.read_text().splitlines() if ln.startswith("# ")), "")
    return (fm.get("og_title") or title).strip(), (fm.get("excerpt") or fm.get("og_description") or "").strip()


def params_for(p, posts, draft, img):
    """→ (action, params). LinkedIn은 대표 이미지 JPEG가 있으면 이미지 글 + 본문 끝 링크, 없으면 링크 카드 (D76)"""
    s = posts[p]
    connector, action = WINDSOR[p]
    if p == "threads":
        return action, {"text": s["本文"]}
    if p == "facebook":
        return action, {"message": s["本文"], "link": s["リンク"].strip()}
    if p == "linkedin":
        link = s["リンク"].strip()
        if img:
            return "create_image_post", {"commentary": s["本文"].rstrip() + "\n\n" + link, "image_url": img}
        t, d = draft_meta(draft)
        return "create_post", {"commentary": s["本文"], "link": link, "link_title": t, "link_description": d}
    raise ValueError(p)


def plan_one(root, a, slug, sns, draft, card):
    """→ (보낼 요청 목록, 사람에게 보일 줄)"""
    out, lines = [], []
    E, W, _ = check(sns, draft, card, a.url, a.offline)
    if E:
        with contextlib.redirect_stdout(sys.stderr):   # --plan의 JSON에 섞이지 않게
            report(E, W)
        lines.append(f"❌ {slug}: check_sns.py 오류 {len(E)}건 — 이 글은 보내지 않는다")
        return out, lines
    head, posts = parse_sns(sns.read_text())
    img = hero_url(sns, head)
    done = load_done(sns)
    only = [p for p in a.only.split(",") if p] or AUTO
    force = {p for p in a.force.split(",") if p}
    for p in only:
        if p not in WINDSOR:
            lines.append(f"- {p}: ✋ 사람이 붙여 넣기 (자동 게시 없음)")
            continue
        if p in done and not done[p].get("error") and p not in force:
            lines.append(f"- {p}: 이미 올림 {done[p].get('url') or done[p].get('id')} — 다시 올리려면 사람이 --force {p}")
            continue
        if posted_today(root, p) >= DAILY_CAP:
            lines.append(f"- {p}: 오늘 {DAILY_CAP}건 상한 → 건너뜀")
            continue
        connector = WINDSOR[p][0]
        action, prm = params_for(p, posts, draft, img)
        assert (connector, action) in ALLOWED_ACTIONS
        out.append({"slug": slug, "platform": p, "connector": connector, "action": action,
                    "account_label": label(p), "params": prm, "sns": str(sns)})
        warn = " ⚠ 회사 계정 (실제 공개)" if label(p) == "company" else " (시험 계정)"
        lines.append(f"- {p} → {connector}/{action}{warn}\n    " + json.dumps(prm, ensure_ascii=False)[:500])
    return out, lines


def record(root, a, slug, sns, card, test_paths):
    p = a.record
    if p not in PLATFORMS:
        sys.exit(f"❌ --record는 {', '.join(PLATFORMS)} 중 하나")
    manual = p not in WINDSOR             # X·note·개인 계정: 사람이 올리고 알려 준 것
    done = load_done(sns)
    if p in done and not done[p].get("error") and p not in {x for x in a.force.split(",") if x}:
        sys.exit(f"❌ {p}는 이미 기록됨 {done[p].get('url') or done[p].get('id')} (덮어쓰려면 --force {p})")
    rec = {"id": a.id or "", "url": a.post_url or "", "posted_at": now(),
           "account": "사람" if manual else label(p), "via": "사람" if manual else "windsor"}
    if a.error:
        rec["error"] = a.error
    elif not (a.id or (manual and a.post_url)):
        sys.exit("❌ 성공 기록에는 --id(execute_action 결과) 또는 사람이 올린 글의 --post-url이 필요")
    done[p] = rec
    (sns.parent / "sns_posted.json").write_text(json.dumps(done, ensure_ascii=False, indent=1))
    ok = sorted(k for k, v in done.items() if not v.get("error"))
    print(f"{'❌ 실패 기록' if a.error else '✅ 기록'} {slug} {p}: {a.error or a.post_url or a.id}")
    if ok and not test_paths:
        set_front(card, {"sns_posted_at": now(), "sns_platforms": ",".join(f"{k}({done[k]['account']})" for k in ok)})
        print(f"카드에 기록: {card}")


NAME2ID = {"x": "x", "threads": "threads", "note": "note", "linkedin": "linkedin", "facebook": "facebook"}


def record_many(root, a):
    """시트 「게시 주소」 칸을 옮긴 JSON [{slug, platform, url}] → 아직 기록이 없는 것만 기록 (「다 올렸어 아침」)"""
    from sns_digest import NAMES
    names = {v: k for k, v in NAMES.items()} | NAME2ID
    rows = json.loads(Path(a.record_many).read_text())
    n = 0
    for r in rows:
        url, slug = (r.get("url") or "").strip(), to_slug(r.get("slug", ""))
        p = names.get((r.get("platform") or "").strip())
        if not url.startswith("http") or not slug or not p:
            continue
        P = paths(root, slug)
        cur = load_done(P["sns"]).get(p)
        if cur and not cur.get("error"):
            continue
        a.record, a.id, a.post_url, a.error = p, "", url, None
        record(root, a, slug, P["sns"], P["card"], False)
        n += 1
    print(f"새로 기록 {n}건")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="slug·파일 이름·글 주소, 또는 날짜(YYYY-MM-DD·오늘)")
    ap.add_argument("--plan", action="store_true", help="보낼 요청을 JSON으로 (「올려」 뒤 에이전트가 쓴다)")
    ap.add_argument("--only", default="", help="threads,facebook,linkedin 중 일부")
    ap.add_argument("--force", default="", help="이미 올린 플랫폼을 다시 (사람이 지시했을 때만)")
    ap.add_argument("--record", help="게시 결과 기록: 플랫폼 이름")
    ap.add_argument("--id"); ap.add_argument("--post-url", dest="post_url"); ap.add_argument("--error")
    ap.add_argument("--record-many", help="시트에서 읽은 게시 주소 JSON [{slug, platform, url}] (「다 올렸어」)")
    ap.add_argument("--slot", choices=SLOTS, help="날짜 대상의 회차")
    ap.add_argument("--root", default=".")
    ap.add_argument("--sns"); ap.add_argument("--draft"); ap.add_argument("--card"); ap.add_argument("--url")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    test_paths = bool(a.sns and a.draft and a.card)
    if a.record_many:
        return record_many(root, a)
    if (root / "SNS_STOP").exists() and not a.record:
        sys.exit("⛔ SNS_STOP 파일이 있어 아무것도 보내지 않는다 (긴급 정지 — 지우면 다시 보낸다)")

    if test_paths:
        targets = [(to_slug(a.target), Path(a.sns), Path(a.draft), Path(a.card), None)]
    elif is_date(a.target):
        if a.record:
            sys.exit("❌ --record는 글 하나(slug)에만")
        date = sns_digest.parse_date(a.target)
        slot = a.target if a.target in SLOTS else a.slot
        targets = []
        for w, s, c, f in sns_digest.entries_for(root, date, slot):
            if not f.exists():
                print(f"- {s}: 문안 없음 — /blog-distribute {s}")
            elif pending(f):
                targets.append((s, f, root / "drafts" / "done" / c.parent.name / f"{s}.md", c, date))
    else:
        slug = to_slug(a.target)
        P = paths(root, slug)
        date = front(P["card"].read_text()).get("published_at", "")[:10] or None
        targets = [(slug, P["sns"], P["draft"], P["card"], date)]

    if a.record:
        slug, sns, draft, card, date = targets[0]
        record(root, a, slug, sns, card, test_paths)
    else:
        plans, lines = [], []
        for slug, sns, draft, card, _ in targets:
            o, l_ = plan_one(root, a, slug, sns, draft, card)
            plans += o
            lines += [f"== {slug}"] + l_
        if a.plan:
            print(json.dumps(plans, ensure_ascii=False, indent=1))
        else:
            print("\n".join(lines) or "올릴 것 없음")
            print(f"\n→ 「올려」 뒤 보낼 요청 {len(plans)}건 ({len({x['slug'] for x in plans})}편)")

    # 모음 다시 만들기
    if test_paths:
        when = datetime.now(JST).strftime("%Y-%m-%dT%H:%M")
        slug, sns, _, card, _ = targets[0]
        out = sns_digest.build(root, when[:10], [(when, slug, card, sns)], sns.parent / f"digest-{when[:10]}.md")
        print(f"날짜별 모음 (시험): {out}", file=sys.stderr)
    else:
        for d in {t[4] for t in targets if t[4]}:
            print(f"날짜별 모음: {sns_digest.build(root, d)}", file=sys.stderr)


if __name__ == "__main__":
    main()
