#!/usr/bin/env python3
"""blog-publish: Ghost에 **초안(draft)만** 올린다 (D62). 발행·예약은 사람이 Ghost 미리보기를 본 뒤 누른다 (철칙 2).

키: 프로젝트 폴더의 .env (git에 올라가지 않음) — 사람이 직접 넣는다. 이 스크립트는 키를 출력하지 않는다
  GHOST_ADMIN_URL=https://cms.ondi.jp
  GHOST_ADMIN_API_KEY=<id>:<secret>   (Ghost 설정 → Integrations → 사용자 통합의 Admin API Key)

이 키는 관리자 권한 전체라서, 스크립트가 보낼 수 있는 요청을 아래로만 묶는다 (ALLOWED):
  GET  posts/<id>, posts/slug/<slug>, tags, users — 읽기 (필자 계정 찾기 포함)
  POST posts (status=draft)                     — 새 초안
  PUT  posts/<id> (status=draft, 지금도 draft일 때만) — 우리가 만든 초안 갱신
  POST images/upload                            — 대표 이미지 (+ SNS용 JPEG 사본 → ghost_post.json hero_jpg_url, D76)
  발행·예약 상태, newsletter·email, 삭제, 다른 경로는 코드에 없다

사용법:
  python3 -I ghost_upload.py <slug>            # publish/<slug>/ 파일로 초안 만들기 (이미 올렸으면 그 초안만 갱신)
  python3 -I ghost_upload.py <slug> --dry-run  # 네트워크 없이 보낼 내용만 확인
기록: publish/<slug>/ghost_post.json (post id·uuid·올린 시각) — 다음 갱신 때 같은 초안을 찾는다
"""
import argparse
import base64
import hashlib
import hmac
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
AUTHOR_SLUG = "hikari"   # 필자는 모두 ヒカリちゃん (D38) — Ghost 스태프 「ひかり」
ALLOWED = {("GET", r"posts/[0-9a-f]{24}/"), ("GET", r"posts/slug/[a-z0-9_-]+/"), ("GET", r"tags/"), ("GET", r"users/"),
           ("POST", r"posts/"), ("PUT", r"posts/[0-9a-f]{24}/"), ("POST", r"images/upload/")}
POST_FIELDS = {"title", "slug", "html", "status", "custom_excerpt", "meta_title", "meta_description", "og_title",
               "og_description", "twitter_title", "twitter_description", "tags", "feature_image",
               "feature_image_alt", "updated_at", "authors"}


def load_env(root):
    p = root / ".env"
    env = {}
    if p.exists():
        for ln in p.read_text().splitlines():
            m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*?)\s*$", ln)
            if m and not ln.lstrip().startswith("#"):
                env[m.group(1)] = m.group(2).strip("'\"")
    return env


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def token(key):
    kid, secret = key.split(":")
    now = int(time.time())
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}, separators=(",", ":")).encode())
    p = b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}, separators=(",", ":")).encode())
    sig = hmac.new(bytes.fromhex(secret), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64(sig)}"


class Ghost:
    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/ghost/api/admin/"
        self.key = key

    def api(self, method, path, query="", body=None, file=None):
        if not any(m == method and re.fullmatch(rx, path) for m, rx in ALLOWED):
            sys.exit(f"❌ 허용하지 않은 요청: {method} {path} (초안 만들기·갱신·이미지 올리기만)")
        if body is not None:
            for post in body.get("posts", []):
                if post.get("status") != "draft" or set(post) - POST_FIELDS:
                    sys.exit(f"❌ 초안이 아니거나 허용하지 않은 칸: status={post.get('status')} {sorted(set(post) - POST_FIELDS)}")
        # 키·토큰이 명령줄(ps)에 보이지 않게 curl 설정을 표준 입력으로 넘긴다
        cfg = [f'header = "Authorization: Ghost {token(self.key)}"', 'header = "Accept-Version: v5.0"']
        args = ["curl", "-sS", "--max-time", "60", "-K", "-", "-X", method, "-w", "\n%{http_code}"]
        tmp = None
        if body is not None:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump(body, tmp, ensure_ascii=False); tmp.close()
            args += ["-H", "Content-Type: application/json", "--data-binary", "@" + tmp.name]
        if file is not None:
            args += ["--form-string", "purpose=image", "--form-string", f"ref={file.name}", "-F", f"file=@{file};type={MIME.get(file.suffix.lower(), 'application/octet-stream')}"]
        args += ["--", self.base + path + query]
        try:
            p = subprocess.run(args, input="\n".join(cfg) + "\n", capture_output=True, text=True)
        finally:
            if tmp:
                Path(tmp.name).unlink(missing_ok=True)
        out, _, code = p.stdout.rpartition("\n")
        try:
            data = json.loads(out) if out.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": out[:300]}
        return code, data


def err_msg(data):
    e = (data.get("errors") or [{}])[0]
    return f"{e.get('type', '')}: {e.get('message', '')} {e.get('context') or ''}".strip() or str(data)[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    d = root / "publish" / a.slug
    gj, c1, c2 = d / "ghost.json", d / "card1-style.html", d / "card2-body.html"
    for f in (gj, c1, c2):
        if not f.exists():
            sys.exit(f"❌ {f} 없음 — 먼저 build_publish.py (3장)")
    g = json.loads(gj.read_text())
    if g["slug"] != a.slug:
        sys.exit(f"❌ ghost.json slug {g['slug']} ≠ {a.slug}")
    if any(f.stat().st_mtime < c2.stat().st_mtime - 5 for f in (gj,)):
        sys.exit("❌ ghost.json이 card2보다 오래됨 — build_publish.py를 다시")
    post = {"title": g["title"], "slug": a.slug, "html": c1.read_text() + "\n" + c2.read_text(), "status": "draft"}
    for k in ("custom_excerpt", "meta_title", "meta_description", "og_title", "og_description",
              "twitter_title", "twitter_description"):
        if g.get(k):
            post[k] = g[k]
    hero = d / g["feature_image_file"] if g.get("feature_image_file") else None
    rec_p = d / "ghost_post.json"
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}

    if a.dry_run:
        print(f"[dry-run] {'갱신 ' + rec['id'] if rec else '새 초안'} · status=draft · slug={a.slug}")
        print(f"  제목 {g['title']}\n  본문 {len(post['html']):,}자 (HTML 카드 2개)\n  태그 slug {g['tag_slugs']} (기존 태그만)")
        print(f"  대표 이미지 {hero.name if hero and hero.exists() else '없음'}")
        print(f"  칸: {sorted(post)}")
        return

    env = load_env(root)
    url, key = env.get("GHOST_ADMIN_URL", ""), env.get("GHOST_ADMIN_API_KEY", "")
    if not url or not re.fullmatch(r"[0-9a-f]{24}:[0-9a-f]{64}", key):
        sys.exit("⚠ .env에 GHOST_ADMIN_URL·GHOST_ADMIN_API_KEY가 없거나 형식이 다름 — 파일 출력(ghost.md)대로 사람이 붙여 넣는다")
    gh = Ghost(url, key)

    # 태그: 기존 태그만 붙인다 (새 태그를 만들지 않는다)
    code, data = gh.api("GET", "tags/", "?limit=all&fields=id,slug,name")
    if code != "200":
        sys.exit(f"❌ 태그 목록을 못 읽음 ({code}) {err_msg(data)}")
    have = {t["slug"]: t for t in data.get("tags", [])}
    post["tags"] = [{"id": have[s]["id"]} for s in g["tag_slugs"] if s in have]
    missing = [s for s in g["tag_slugs"] if s not in have]

    # 필자: ヒカリちゃん 스태프 계정 (없으면 Ghost 기본값 그대로 두고 알린다)
    code, data = gh.api("GET", "users/", "?limit=all&fields=id,slug,name,status")
    hk = next((u for u in data.get("users", []) if u["slug"] == AUTHOR_SLUG and u.get("status") == "active"), None)
    if hk:
        post["authors"] = [{"id": hk["id"]}]

    # 대상 초안 정하기
    if rec:
        code, data = gh.api("GET", f"posts/{rec['id']}/", "?fields=id,uuid,status,updated_at,slug")
        if code != "200":
            sys.exit(f"❌ 기록된 초안 {rec['id']}을 못 찾음 ({code}) — Ghost에서 지웠다면 ghost_post.json을 지우고 다시")
        cur = data["posts"][0]
        if cur["status"] != "draft":
            sys.exit(f"❌ 이 글은 이미 {cur['status']} — 초안이 아니면 고치지 않는다 (Ghost에서 사람이 고친다)")
    else:
        code, data = gh.api("GET", f"posts/slug/{a.slug}/", "?fields=id,status")
        if code == "200":
            sys.exit(f"❌ slug {a.slug} 글이 Ghost에 이미 있음 ({data['posts'][0]['status']}) — 우리 기록이 없어 덮어쓰지 않는다. 사람에게 묻는다")

    hero_jpg_url = rec.get("hero_jpg_url", "")
    if hero and hero.exists():
        code, data = gh.api("POST", "images/upload/", file=hero)
        if code not in ("200", "201"):
            sys.exit(f"❌ 대표 이미지 올리기 실패 ({code}) {err_msg(data)}")
        post["feature_image"] = data["images"][0]["url"]
        if g.get("feature_image_alt"):
            post["feature_image_alt"] = g["feature_image_alt"]
        # SNS용 JPEG 사본 (Threads·LinkedIn 이미지 글, X·note 첨부 — webp를 받지 않는 곳이 있다, D76)
        jpg = Path(tempfile.mkdtemp()) / f"{a.slug}_hero.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(hero), "--out", str(jpg)],
                       capture_output=True)
        if jpg.exists():
            code, data = gh.api("POST", "images/upload/", file=jpg)
            hero_jpg_url = data["images"][0]["url"] if code in ("200", "201") else ""
            if not hero_jpg_url:
                print(f"⚠ SNS용 JPEG 올리기 실패 ({code}) — SNS 이미지는 사람이 붙인다")

    if rec:
        post["updated_at"] = cur["updated_at"]
        code, data = gh.api("PUT", f"posts/{rec['id']}/", "?source=html", body={"posts": [post]})
    else:
        code, data = gh.api("POST", "posts/", "?source=html", body={"posts": [post]})
    if code not in ("200", "201"):
        sys.exit(f"❌ 초안 {'갱신' if rec else '만들기'} 실패 ({code}) {err_msg(data)}")
    p = data["posts"][0]
    if p["status"] != "draft":
        print(f"⚠⚠ 상태가 {p['status']} — 즉시 Ghost에서 확인 (초안이어야 함)")
    now = datetime.now(JST)
    rec_p.write_text(json.dumps({"id": p["id"], "uuid": p["uuid"], "slug": p["slug"], "status": p["status"],
                                 "uploaded_at": f"{now:%Y-%m-%dT%H:%M%z}", "hero_jpg_url": hero_jpg_url,
                                 "first_uploaded_at": rec.get("first_uploaded_at", f"{now:%Y-%m-%dT%H:%M%z}")},
                                ensure_ascii=False, indent=1) + "\n")
    print(f"{'갱신' if rec else '새 초안'} 통과 — status={p['status']} slug={p['slug']}")
    if p["slug"] != a.slug:
        print(f"⚠ Ghost가 slug를 {p['slug']}로 바꿈 — 같은 slug 글이 있다. 사람에게 알린다")
    print(f"필자: {', '.join(x['name'] for x in p.get('authors', [])) or '?'}")
    if not hk:
        print(f"⚠ Ghost 스태프 「{AUTHOR_SLUG}」가 없거나 잠김 — 필자가 기본 계정으로 들어감. 사람에게 알린다")
    if missing:
        print(f"⚠ 기존 태그에 없음: {missing} — 붙이지 않았다 (새 태그는 사람이 정한다)")
    if not post.get("feature_image"):
        print("⚠ 대표 이미지 없음 — 만든 뒤 다시 올리면 이 초안에 들어간다")
    editor = f"{url.rstrip('/')}/ghost/#/editor/post/{p['id']}"
    print(f"편집 화면: {editor}")
    card_status(root / "briefs" / f"{a.slug}.md", bool(g.get("trial_pending")), editor)
    if g.get("trial_pending"):
        print("→ ◆ 실습 필요 — 팀원이 실습 문서에 결과 → 「실습 끝났어 <slug>」 → 섹션 채워 같은 초안 갱신 뒤 미리보기·발행 (D79)")
    else:
        print("→ ◆ Ghost 미리보기에서 ghost.md 5장 체크리스트 확인 → 사람이 「Publish only」로 발행·예약")


def card_status(card_p, pending, editor):
    """D79: 실습 자리 표시가 있는 초안을 올리면 카드 「실습 대기」, 채운 뒤 다시 올리면 「발행 준비」로 되돌린다"""
    if not card_p.exists():
        print(f"⚠ 카드 {card_p} 없음 — 상태를 바꾸지 못함")
        return
    ct = card_p.read_text()
    cur = (re.search(r"(?m)^status:\s*(.*)$", ct) or [None, ""])[1].split("(")[0].strip()
    new = "실습 대기" if pending else ("발행 준비" if cur == "실습 대기" else None)
    if new and new != cur:
        ct = re.sub(r"(?m)^status:.*$", f"status: {new}", ct, count=1)
        print(f"카드 status: {cur} → {new}")
    line = f"ghost_draft: {editor}"
    ct = re.sub(r"(?m)^ghost_draft: .*$", line, ct, count=1) if re.search(r"(?m)^ghost_draft: ", ct) else \
        re.sub(r"\n---\n", "\n" + line + "\n---\n", ct, count=1)
    card_p.write_text(ct)


if __name__ == "__main__":
    main()
