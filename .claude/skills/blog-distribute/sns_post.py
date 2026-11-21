#!/usr/bin/env python3
"""blog-distribute: 사람이 「올려 <slug>」 한 뒤에만 SNS에 게시한다 (철칙 2, D66). 기본은 dry-run — `--go`가 있어야 보낸다

키: 프로젝트 폴더의 .env (git 제외, 권한 600) — 사람이 직접 넣는다. 이 스크립트는 키를 출력하지 않는다
  SNS_ACCOUNT_LABEL=test|company        어느 계정인지 (기록·보고에 남긴다. 계정을 바꿀 때는 .env 값만 바꾼다)
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET   (X 개발자 앱, 읽기+쓰기, OAuth 1.0a)
  THREADS_USER_ID / THREADS_TOKEN       (Meta 앱 Threads API, threads_basic·threads_content_publish. 60일 토큰)
  LINKEDIN_TOKEN / LINKEDIN_AUTHOR_URN  (urn:li:person:… 개인 또는 urn:li:organization:… 회사 페이지)
  LINKEDIN_VERSION=YYYYMM               (선택, 기본 아래 LI_VERSION)
  FB_PAGE_ID / FB_PAGE_TOKEN            (회사 페이지 토큰, pages_manage_posts. 개인 계정은 API로 게시 불가)
  FB_GRAPH_VERSION=vNN.0                (선택, 기본 아래 FB_VERSION)
  note는 공식 API가 없어 보내지 않는다 — 사람이 붙여 넣는다

보낼 수 있는 요청 (ALLOWED, 이 밖은 코드가 멈춘다): 글 만들기·답글·첫 댓글·이미지 올리기, 방금 올린 글의 주소 읽기.
  삭제·수정·예약·DM·팔로우·다른 경로는 없다
막는 것: 프로젝트 루트 SNS_STOP 파일(긴급 정지) / 같은 slug·플랫폼 두 번 (--force 플랫폼) / 플랫폼당 하루 DAILY_CAP건 /
  check_sns.py 오류 / .env 권한이 600이 아님

사용법:
  python3 -I sns_post.py <slug>                       # dry-run: 보낼 내용만 (키 없어도 됨)
  python3 -I sns_post.py <slug> --go                  # 「올려」를 받은 뒤 (slug 자리에 파일 이름·경로·글 주소도 됨)
  python3 -I sns_post.py 오늘 | 2026-11-21            # 그날 발행한 글 중 아직 안 올린 것 목록 + dry-run
  python3 -I sns_post.py 오늘 --go                    # 목록을 보여 주고 사람이 「응」 한 뒤
  python3 -I sns_post.py <slug> --go --only x,threads
  python3 -I sns_post.py <slug> --sns F --draft F --card F --url U --offline [--go]   # 시험 (SNS_ACCOUNT_LABEL=test만 --go)
기록: sns.md 옆 sns_posted.json, 발행 완료 카드의 sns_posted_at·sns_platforms
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blog-publish"))
from sns_common import parse_sns, paths, set_front, front, is_date, to_slug  # noqa: E402
import sns_digest  # noqa: E402
from check_sns import check, report  # noqa: E402
from ghost_upload import load_env  # noqa: E402

JST = timezone(timedelta(hours=9))
API_PLATFORMS = ["x", "threads", "linkedin", "facebook"]
DAILY_CAP = 10                       # common.md 7장 B 하루 게시 상한
LI_VERSION = "202610"                # LinkedIn-Version (월 단위, 약 1년 지원) — 만료되면 .env LINKEDIN_VERSION
FB_VERSION = "v24.0"                 # Graph API 버전 — 만료되면 .env FB_GRAPH_VERSION
KEYS = {"x": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"],
        "threads": ["THREADS_USER_ID", "THREADS_TOKEN"],
        "linkedin": ["LINKEDIN_TOKEN", "LINKEDIN_AUTHOR_URN"],
        "facebook": ["FB_PAGE_ID", "FB_PAGE_TOKEN"]}
ALLOWED = [("POST", r"https://api\.x\.com/2/tweets"),
           ("POST", r"https://api\.x\.com/2/media/upload"),
           ("POST", r"https://graph\.threads\.net/v1\.0/\d+/threads"),
           ("POST", r"https://graph\.threads\.net/v1\.0/\d+/threads_publish"),
           ("GET", r"https://graph\.threads\.net/v1\.0/\d+\?fields=permalink"),
           ("POST", r"https://api\.linkedin\.com/rest/posts"),
           ("POST", r"https://api\.linkedin\.com/rest/socialActions/urn%3Ali%3A(share|ugcPost)%3A\d+/comments"),
           ("POST", r"https://graph\.facebook\.com/v\d+\.\d+/\d+/feed"),
           ("GET", r"https://graph\.facebook\.com/v\d+\.\d+/\d+_\d+\?fields=permalink_url")]
# 보낼 수 있는 칸 (예약·비공개·수정 칸은 없다)
FIELDS = {"x_tweet": {"text", "media", "reply"}, "threads": {"media_type", "text", "creation_id"},
          "linkedin_post": {"author", "commentary", "visibility", "distribution", "lifecycleState", "isReshareDisabledByAuthor"},
          "linkedin_comment": {"actor", "object", "message"}, "facebook": {"message", "link"}, "x_media": {"media_category"}}


class Stop(Exception):
    pass


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Client:
    def __init__(self, env, dry):
        self.env, self.dry = env, dry
        self.secrets = [v for k, v in env.items() if v and len(v) >= 8 and any(t in k for t in ("TOKEN", "SECRET", "KEY", "URN"))]

    def redact(self, s):
        for v in self.secrets:
            s = s.replace(v, "***")
        return s

    def send(self, method, url, kind, secret_cfg=(), fields=None, json_body=None, file=None, want_header=None):
        """모든 요청이 지나는 곳 — 허용 목록·칸 검사 뒤 curl. 비밀값은 표준 입력 설정(-K -)으로만 넘긴다"""
        if method not in ("GET", "POST") or not any(m == method and re.fullmatch(rx, url) for m, rx in ALLOWED):
            raise Stop(f"허용하지 않은 요청: {method} {self.redact(url)}")
        keys = set(fields or {}) | set(json_body or {})
        if keys - FIELDS[kind]:
            raise Stop(f"허용하지 않은 칸 ({kind}): {sorted(keys - FIELDS[kind])}")
        if self.dry:
            shown = json_body if json_body is not None else fields
            print(f"  [dry-run] {method} {url}\n           {json.dumps(shown, ensure_ascii=False)[:600]}" + (f"\n           file={file}" if file else ""))
            return 200, {"id": "DRYRUN"}, "DRYRUN"
        args = ["curl", "-sS", "--max-time", "60", "-K", "-", "-X", method, "-w", "\n%{http_code}" + (f"\n%header{{{want_header}}}" if want_header else "")]
        tmp = None
        if json_body is not None:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump(json_body, tmp, ensure_ascii=False); tmp.close()
            args += ["-H", "Content-Type: application/json", "--data-binary", "@" + tmp.name]
        for k, v in (fields or {}).items():
            args += ["--form-string", f"{k}={v}"]
        if file:
            args += ["-F", f"media=@{file};type=image/jpeg"]
        args += ["--", url]
        try:
            p = subprocess.run(args, input="".join(c + "\n" for c in secret_cfg), capture_output=True, text=True)
        finally:
            if tmp:
                Path(tmp.name).unlink(missing_ok=True)
        lines = p.stdout.split("\n")
        hdr = lines.pop() if want_header else ""
        code = lines.pop() if lines else ""
        out = "\n".join(lines)
        try:
            data = json.loads(out) if out.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": self.redact(out[:300])}
        if not code.startswith("2"):
            raise Stop(f"{method} {url.split('?')[0]} → {code} {self.redact(json.dumps(data, ensure_ascii=False))[:400]} {self.redact(p.stderr[:200])}")
        return int(code), data, hdr.strip()


# ---- X (OAuth 1.0a 사용자 인증) ----
def oauth1(env, method, url):
    pe = lambda s: urllib.parse.quote(str(s), safe="~")  # noqa: E731
    o = {"oauth_consumer_key": env["X_API_KEY"], "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": env["X_ACCESS_TOKEN"], "oauth_version": "1.0"}
    base = "&".join([method, pe(url), pe("&".join(f"{pe(k)}={pe(v)}" for k, v in sorted(o.items())))])
    key = f"{pe(env['X_API_SECRET'])}&{pe(env['X_ACCESS_SECRET'])}"
    o["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "header = " + q("Authorization: OAuth " + ", ".join(f'{pe(k)}="{pe(v)}"' for k, v in sorted(o.items())))


def post_x(c, env, posts, hero):
    auth = (lambda m, u: [oauth1(env, m, u)]) if not c.dry else (lambda m, u: [])
    media = None
    if hero and Path(hero).exists():
        jpg = Path(tempfile.mkdtemp()) / "hero.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(hero), "--out", str(jpg)], capture_output=True)
        u = "https://api.x.com/2/media/upload"
        _, d, _ = c.send("POST", u, "x_media", auth("POST", u), fields={"media_category": "tweet_image"}, file=jpg)
        media = (d.get("data") or {}).get("id") or d.get("media_id_string") or d.get("id")
    u = "https://api.x.com/2/tweets"
    body = {"text": posts["x"]["本文"]}
    if media:
        body["media"] = {"media_ids": [str(media)]}
    _, d, _ = c.send("POST", u, "x_tweet", auth("POST", u), json_body=body)
    tid = (d.get("data") or {}).get("id") or d.get("id")
    rec = {"id": tid, "url": f"https://x.com/i/web/status/{tid}"}
    try:
        _, d2, _ = c.send("POST", u, "x_tweet", auth("POST", u), json_body={"text": posts["x"]["返信"], "reply": {"in_reply_to_tweet_id": str(tid)}})
        rec["reply_id"] = (d2.get("data") or {}).get("id") or d2.get("id")
    except Stop as e:
        rec["reply_error"] = str(e)
    return rec


# ---- Threads ----
def post_threads(c, env, posts, hero):
    uid = env.get("THREADS_USER_ID") or "0"
    tok = [f"form-string = {q('access_token=' + env['THREADS_TOKEN'])}"] if not c.dry else []
    base = f"https://graph.threads.net/v1.0/{uid}"
    _, d, _ = c.send("POST", base + "/threads", "threads", tok, fields={"media_type": "TEXT", "text": posts["threads"]["本文"]})
    cid = d.get("id")
    for i in range(4):  # 컨테이너가 준비될 때까지 잠깐 기다린다
        try:
            _, d2, _ = c.send("POST", base + "/threads_publish", "threads", tok, fields={"creation_id": str(cid)})
            break
        except Stop:
            if i == 3:
                raise
            time.sleep(5)
    mid = d2.get("id")
    rec = {"id": mid, "url": ""}
    if not c.dry:
        try:
            _, d3, _ = c.send("GET", f"https://graph.threads.net/v1.0/{mid}?fields=permalink", "threads",
                              [f"header = {q('Authorization: Bearer ' + env['THREADS_TOKEN'])}"])
            rec["url"] = d3.get("permalink", "")
        except Stop:
            pass
    return rec


# ---- LinkedIn ----
LI_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def li_text(s):
    """LinkedIn commentary는 little text 형식 — 예약 기호 앞에 \\ (안 하면 글이 잘리거나 거절된다)"""
    return LI_RESERVED.sub(r"\\\1", s)


def post_linkedin(c, env, posts, hero):
    ver = env.get("LINKEDIN_VERSION") or LI_VERSION
    hd = ([f"header = {q('Authorization: Bearer ' + env['LINKEDIN_TOKEN'])}"] if not c.dry else []) + \
         [f"header = {q('LinkedIn-Version: ' + ver)}", 'header = "X-Restli-Protocol-Version: 2.0.0"']
    author = env.get("LINKEDIN_AUTHOR_URN", "urn:li:person:DRYRUN")
    body = {"author": author, "commentary": li_text(posts["linkedin"]["本文"]), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    _, _, urn = c.send("POST", "https://api.linkedin.com/rest/posts", "linkedin_post", hd, json_body=body, want_header="x-restli-id")
    if c.dry:
        urn = "urn:li:share:0"
    rec = {"id": urn, "url": f"https://www.linkedin.com/feed/update/{urn}/"}
    try:
        cu = f"https://api.linkedin.com/rest/socialActions/{urllib.parse.quote(urn, safe='')}/comments"
        c.send("POST", cu, "linkedin_comment", hd, json_body={"actor": author, "object": urn, "message": {"text": posts["linkedin"]["最初のコメント"]}})
        rec["comment"] = "ok"
    except Stop as e:
        rec["comment_error"] = str(e)
    return rec


# ---- Facebook 페이지 ----
def post_facebook(c, env, posts, hero):
    ver = env.get("FB_GRAPH_VERSION") or FB_VERSION
    tok = [f"form-string = {q('access_token=' + env['FB_PAGE_TOKEN'])}"] if not c.dry else []
    page = env.get("FB_PAGE_ID", "0")
    _, d, _ = c.send("POST", f"https://graph.facebook.com/{ver}/{page}/feed", "facebook", tok,
                     fields={"message": posts["facebook"]["本文"], "link": posts["facebook"]["リンク"].strip()})
    pid = d.get("id", "")
    rec = {"id": pid, "url": ""}
    if not c.dry and pid:
        try:
            _, d2, _ = c.send("GET", f"https://graph.facebook.com/{ver}/{pid}?fields=permalink_url", "facebook",
                              [f"header = {q('Authorization: Bearer ' + env['FB_PAGE_TOKEN'])}"])
            rec["url"] = d2.get("permalink_url", "")
        except Stop:
            pass
    return rec


POSTERS = {"x": post_x, "threads": post_threads, "linkedin": post_linkedin, "facebook": post_facebook}


def posted_today(root, platform):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    n = 0
    for f in list((root / "publish").glob("**/sns_posted.json")):
        try:
            rec = json.loads(f.read_text()).get(platform) or {}
        except json.JSONDecodeError:
            continue
        if str(rec.get("posted_at", "")).startswith(today):
            n += 1
    return n


def pending(root, sns, env):
    """아직 안 올렸고 보낼 수 있는(키가 있는) 플랫폼"""
    rec = sns.parent / "sns_posted.json"
    done = json.loads(rec.read_text()) if rec.exists() else {}
    return [p for p in API_PLATFORMS if p not in done and all(env.get(k) for k in KEYS[p])]


def post_one(root, a, env, label, sns, draft, card, test_paths):
    dry = not a.go
    E, W, _ = check(sns, draft, card, a.url, a.offline)
    if E:
        report(E, W)
        print("❌ check_sns.py 오류가 있어 이 글은 보내지 않는다")
        return
    head, posts = parse_sns(sns.read_text())
    hero = head.get("hero")
    rec_path = sns.parent / "sns_posted.json"
    done = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    only = [p for p in a.only.split(",") if p] or API_PLATFORMS
    force = {p for p in a.force.split(",") if p}
    c = Client(env, dry)
    results = {}
    for p in only:
        if p not in POSTERS:
            print(f"- {p}: 이 스크립트로 보내지 않음 (note는 사람이 붙여 넣기)")
            continue
        missing = [k for k in KEYS[p] if not env.get(k)]
        if p in done and p not in force:
            print(f"- {p}: 이미 올림 {done[p].get('url') or done[p].get('id')} — 다시 올리려면 사람이 --force {p}")
            continue
        if missing and not dry:
            print(f"- {p}: 키 없음 {missing} → 건너뜀 (사람이 붙여 넣기)")
            continue
        if not dry and posted_today(root, p) >= DAILY_CAP:
            print(f"- {p}: 오늘 {DAILY_CAP}건 상한 → 건너뜀")
            continue
        print(f"- {p}:" + (f" (키 없음 {missing} — 실제로는 건너뜀)" if missing else ""))
        try:
            rec = POSTERS[p](c, env, posts, hero)
        except Stop as e:
            print(f"  ❌ {e}")
            continue
        if dry:
            continue
        rec.update({"posted_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M%z"), "account": label})
        done[p] = rec
        results[p] = rec
        rec_path.write_text(json.dumps(done, ensure_ascii=False, indent=1))
        print(f"  ✅ {rec.get('url') or rec.get('id')}" + "".join(f"\n  ⚠ {k}: {v}" for k, v in rec.items() if k.endswith("_error")))
    print("- note: 사람이 붙여 넣기 (날짜별 모음 sns/YYYY-MM-DD.md, 편집기에서 예약 가능)")
    if results and not test_paths:
        set_front(card, {"sns_posted_at": datetime.now(JST).strftime("%Y-%m-%dT%H:%M%z"),
                         "sns_platforms": ",".join(sorted(done)) + f" ({label})"})
        print(f"카드에 기록: {card}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="slug·파일 이름·글 주소, 또는 날짜(YYYY-MM-DD·오늘)")
    ap.add_argument("--go", action="store_true", help="실제로 보낸다 (사람의 「올려」 뒤에만)")
    ap.add_argument("--only", default="", help="x,threads,linkedin,facebook 중 일부")
    ap.add_argument("--force", default="", help="이미 올린 플랫폼을 다시 (사람이 지시했을 때만)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--sns"); ap.add_argument("--draft"); ap.add_argument("--card"); ap.add_argument("--url")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    test_paths = bool(a.sns and a.draft and a.card)
    if (root / "SNS_STOP").exists():
        sys.exit("⛔ SNS_STOP 파일이 있어 아무것도 보내지 않는다 (긴급 정지 — 지우면 다시 보낸다)")
    envp = root / ".env"
    env = load_env(root)
    label = env.get("SNS_ACCOUNT_LABEL", "")
    if a.go:
        if not envp.exists() or stat.S_IMODE(os.stat(envp).st_mode) & 0o077:
            sys.exit("❌ .env가 없거나 권한이 600이 아님 (chmod 600 .env)")
        if label not in ("test", "company"):
            sys.exit("❌ .env에 SNS_ACCOUNT_LABEL=test 또는 company 를 넣어 주세요 (어느 계정인지 기록)")
        if (a.offline or test_paths) and label != "test":
            sys.exit("❌ --offline·시험 경로로는 시험 계정(SNS_ACCOUNT_LABEL=test)에만 올린다")
    print(f"{'' if a.go else '[dry-run] '}계정: {label or '(SNS_ACCOUNT_LABEL 없음)'}{' ⚠ 시험 계정' if label == 'test' else ''}")

    if test_paths:
        sns, draft, card = Path(a.sns), Path(a.draft), Path(a.card)
        post_one(root, a, env, label, sns, draft, card, True)
        when = datetime.now(JST).strftime("%Y-%m-%dT%H:%M")
        out = sns_digest.build(root, when[:10], [(when, to_slug(a.target), card, sns)], sns.parent / f"digest-{when[:10]}.md")
        print(f"날짜별 모음 (시험): {out}")
        return

    if is_date(a.target):
        date = sns_digest.parse_date(a.target)
        items = sns_digest.entries_for(root, date)
        todo = [(w, s, c, f) for w, s, c, f in items if f.exists() and pending(root, f, env)]
        nosns = [s for _, s, _, f in items if not f.exists()]
        print(f"{date} 발행 {len(items)}편 → 올릴 것 {len(todo)}편" + (f" / 문안 없음: {', '.join(nosns)}" if nosns else ""))
        for w, s, c, f in todo:
            print(f"  {w[11:16]} {s}: {', '.join(pending(root, f, env))}")
        for w, s, c, f in (todo if a.go else items):
            if not f.exists():
                continue
            print(f"\n== {s}")
            post_one(root, a, env, label, f, root / "drafts" / "done" / c.parent.name / f"{s}.md", c, False)
        print(f"\n날짜별 모음: {sns_digest.build(root, date)}")
        return

    slug = to_slug(a.target)
    P = paths(root, slug)
    post_one(root, a, env, label, P["sns"], P["draft"], P["card"], False)
    date = front(P["card"].read_text()).get("published_at", "")[:10]
    if date:
        print(f"날짜별 모음: {sns_digest.build(root, date)}")


if __name__ == "__main__":
    main()
