#!/usr/bin/env python3
"""blog-publish: 대표 이미지 후보를 만든다 (D63). 에이전트가 후보를 직접 열어 보고 하나를 고른 뒤 make_hero.py로 규격화.

만드는 곳 (--engine):
  codex (기본)  이 컴퓨터의 Codex CLI — 사람의 ChatGPT 계정으로 로그인된 것(구독 사용량, API 크레딧 아님). 후보 1장씩
  api           OpenAI 이미지 API — .env의 OPENAI_API_KEY (크레딧 필요, 사람이 직접 넣는다, 키는 출력하지 않는다). 후보 n장
프롬프트: publish/<slug>/hero_prompt.md 의 「## 생성용 프롬프트 (영어)」 절
ヒカリちゃん이 나오는 그림이면 사이트 참고 그림을 같이 보낸다 (edits API, 캐릭터 모양 맞추기)

사용법:
  python3 -I make_hero_ai.py <slug> [--engine codex|api] [--n 2] [--quality medium] [--model gpt-image-2.6-sunburst] [--dry-run]
결과: publish/<slug>/hero_cand_<번호>.png → 에이전트가 열어 보고 → make_hero.py publish/<slug>/hero_cand_N.png <slug> --alt "…"
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HIKARI_REF = "https://cms.ondi.jp/content/images/2026/10/hikari_welcome.png"
SIZE = "1536x800"          # 1.92:1 — 1200×630(1.905:1)에 가깝게, 16의 배수
FALLBACK_SIZE = "1536x1024"


def load_key(root):
    p = root / ".env"
    for ln in (p.read_text().splitlines() if p.exists() else []):
        m = re.match(r"\s*OPENAI_API_KEY\s*=\s*(.*?)\s*$", ln)
        if m:
            return m.group(1).strip("'\"")
    return ""


def sec(md, name):
    m = re.search(rf"^## {name}[^\n]*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


def article_summary(root, slug):
    """D64: 그림이 글 내용을 보여 주도록 초안의 제목·3行まとめ·H2를 프롬프트에 넣는다"""
    d = root / "drafts" / f"{slug}.md"
    if not d.exists():
        sys.exit(f"❌ {d} 없음 — 글 내용을 요약해 넣어야 한다")
    t = d.read_text()
    clean = lambda x: re.sub(r"\[S\d+\]|\*\*", "", x).strip()
    title = clean((re.search(r"(?m)^# (.+)$", t) or [None, ""])[1])
    box = re.search(r":::box 3行まとめ\n(.*?)\n:::", t, re.S)
    keys = [clean(re.sub(r"^\d+\.\s*", "", l)) for l in (box.group(1).splitlines() if box else []) if l.strip()]
    h2 = [clean(h) for h in re.findall(r"(?m)^## (.+)$", t)
          if not re.search(r"FAQ|よくある質問|SOURCES|메모", h)]
    return title, keys, h2


def prompt_of(md, summary):
    """D64: 내용이 주인공 — 주제 한 줄·장면 요소 3~5개(글의 요점과 짝)·라벨·ヒカリちゃん 역할이 있어야 만든다"""
    p, topic, els = sec(md, "생성용 프롬프트"), sec(md, "주제 한 줄"), sec(md, "장면 요소")
    labels_s, hk = sec(md, "라벨"), sec(md, "ヒカリちゃん")
    if len(p) < 40:
        sys.exit("❌ hero_prompt.md에 「## 생성용 프롬프트 (영어)」 절이 없거나 짧음 (SKILL 2장)")
    if not topic:
        sys.exit("❌ 「## 주제 한 줄」이 없음 — 그림만 봐도 글 내용이 보이게 (D64)")
    n = len(re.findall(r"(?m)^- \S", els))
    if not 3 <= n <= 5:
        sys.exit(f"❌ 「## 장면 요소」 {n}개 — 글의 요점(3行まとめ·H2)과 짝지은 구체 사물·상황 3~5개 (D64)")
    first = labels_s.splitlines()[0].strip() if labels_s else ""
    if not first:
        sys.exit("❌ 「## 라벨」이 없음 — 라틴 문자 짧은 라벨 0~5개(쉼표로) 또는 「없음」 (D64)")
    labels = [] if first == "없음" else [x.strip(" `「」") for x in first.split(",") if x.strip()]
    bad = [x for x in labels if not re.fullmatch(r"[A-Za-z][A-Za-z .\-]{0,11}", x)]
    if bad or len(labels) > 5:
        sys.exit(f"❌ 라벨 {bad or labels} — 라틴 문자 12자 이내·숫자 없이·5개까지 (일본어·숫자·날짜는 깨지고 틀리기 쉽다)")
    role = hk.splitlines()[0].strip() if hk else ""
    if role not in ("없음", "조연"):
        sys.exit("❌ 「## ヒカリちゃん」은 「없음」 또는 「조연」 — 주인공은 글 내용 (D64)")
    title, keys, h2 = summary
    art = (f" This image is the full-width header of a blog article. Article title (Japanese): {title}."
           + (f" Key points: {' / '.join(keys)}." if keys else "")
           + (f" Sections: {' / '.join(h2)}." if h2 else "")
           + " The ARTICLE CONTENT is the main subject — a reader should grasp what the article is about at a glance."
           + (" The character is a small supporting guide, not the focus." if role == "조연" else " No character."))
    guard = (" Strictly no text anywhere." if not labels else
             f" The ONLY text allowed is these short labels, each written once in plain bold letters on objects or signs: "
             + ", ".join(f'"{x}"' for x in labels) + ". No other text, numbers, logos, watermarks or signatures.")
    layout = (" Full-bleed, detailed scene that fills the entire frame edge to edge — no plain empty background or margins."
              " The website crops it from the top-left and covers the bottom with a content card: keep labels, key objects"
              " and faces out of the bottom 25% and the right 6% edge.")
    style = (" STYLE: clean, crisp digital illustration with smooth flat color areas and clear outlines, like a modern"
             " Japanese business blog header — no watercolor paper texture, grain, noise or speckles (the file must stay light).")
    return p + art + guard + " No real people." + layout + style, role == "조연"


def call(key, form, files, out_json):
    cfg = f'header = "Authorization: Bearer {key}"\n'   # 키가 명령줄(ps)에 보이지 않게 표준 입력으로
    endpoint = "edits" if files else "generations"
    args = ["curl", "-sS", "--max-time", "300", "-K", "-", "-o", out_json, "-w", "%{http_code}"]
    if files:
        for k, v in form.items():
            args += ["--form-string", f"{k}={v}"]
        for f in files:
            args += ["-F", f"image[]=@{f}"]
    else:
        tmp = Path(out_json).with_suffix(".req.json")
        tmp.write_text(json.dumps(form, ensure_ascii=False))
        args += ["-H", "Content-Type: application/json", "--data-binary", f"@{tmp}"]
    args += ["--", f"https://api.openai.com/v1/images/{endpoint}"]
    p = subprocess.run(args, input=cfg, capture_output=True, text=True)
    return p.stdout.strip(), p.stderr.strip()


def codex_make(prompt, ref, td, out):
    """Codex CLI(ChatGPT 로그인)의 이미지 생성 도구로 1장 → out"""
    st = subprocess.run(["codex", "login", "status"], capture_output=True, text=True)
    if "ChatGPT" not in (st.stdout + st.stderr):
        sys.exit("⚠ Codex가 ChatGPT 계정으로 로그인돼 있지 않음 — 사람이 터미널에서 `codex login` (또는 --engine api)")
    ask = ("Use your image generation tool to create ONE wide landscape image (as wide as possible, about 1.9:1)."
           + (" The attached image is the character reference — keep her look exactly." if ref else "")
           + f" Prompt: {prompt}\nAfter generating, copy the generated image file into the current directory as cand.png."
           " Do not do anything else.")
    args = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", td] + (["-i", ref] if ref else [])
    p = subprocess.run(args, input=ask, capture_output=True, text=True, timeout=900)
    c = Path(td) / "cand.png"
    if not c.exists() or c.stat().st_size < 10000:
        tail = (p.stdout + p.stderr).strip().splitlines()[-5:]
        sys.exit("❌ Codex가 이미지를 만들지 못함 — 사용량 한도일 수 있다 (내일 다시 또는 --engine api)\n  " + "\n  ".join(tail))
    out.write_bytes(c.read_bytes())
    c.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--engine", choices=["codex", "api"], default="codex")
    ap.add_argument("--n", type=int, default=None, help="후보 수 (codex 기본 1, api 기본 2)")
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--model", default="gpt-image-2.6-sunburst")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    d = root / "publish" / a.slug
    hp = d / "hero_prompt.md"
    if not hp.exists():
        sys.exit(f"❌ {hp} 없음 — 먼저 프롬프트를 쓴다 (SKILL 2장)")
    md = hp.read_text()
    prompt, use_ref = prompt_of(md, article_summary(root, a.slug))
    a.n = a.n or (1 if a.engine == "codex" else 2)
    form = {"model": a.model, "prompt": prompt, "n": str(a.n), "size": SIZE, "quality": a.quality, "output_format": "png"}
    if a.dry_run:
        how = "Codex(ChatGPT 구독)" if a.engine == "codex" else f"API {'edits' if use_ref else 'generations'} · {a.model} · {SIZE} · {a.quality}"
        print(f"[dry-run] {how} · 참고 그림 {'ヒカリちゃん' if use_ref else '없음'} · n={a.n}")
        print(f"  프롬프트 {len(prompt)}자:\n  {prompt}")
        return
    if a.engine == "codex":
        for old in d.glob("hero_cand_*.png"):
            old.unlink()
        with tempfile.TemporaryDirectory() as td:
            ref = None
            if use_ref:
                ref = str(Path(td) / "hikari_ref.png")
                subprocess.run(["curl", "-sS", "--max-time", "30", "-o", ref, "--", HIKARI_REF], check=True)
            for i in range(1, a.n + 1):
                codex_make(prompt, ref, td, d / f"hero_cand_{i}.png")
                print(f"  {d / f'hero_cand_{i}.png'}")
        print(f"후보 {a.n}장 — Codex(ChatGPT 구독 사용량)")
        print("→ 에이전트가 후보를 열어 본다: 글자·숫자·로고, 얼굴·손 이상, ① 블라인드 확인(그림만 한 문장으로 설명 → 주제가 나오는가) ② 키워드 글자 철자 ③ ヒカリちゃん 모양 → 괜찮으면 make_hero.py, 아니면 프롬프트를 고쳐 한 번 더")
        return
    key = load_key(root)
    if not re.fullmatch(r"sk-[A-Za-z0-9_\-]{20,}", key):
        sys.exit("⚠ .env에 OPENAI_API_KEY가 없거나 형식이 다름 — 사람이 hero_prompt.md로 이미지를 만든다 (2장)")
    with tempfile.TemporaryDirectory() as td:
        files = []
        if use_ref:
            ref = Path(td) / "hikari_ref.png"
            subprocess.run(["curl", "-sS", "--max-time", "30", "-o", str(ref), "--", HIKARI_REF], check=True)
            if ref.stat().st_size < 1000:
                sys.exit("❌ ヒカリちゃん 참고 그림을 못 받음")
            files = [str(ref)]
        out_json = str(Path(td) / "res.json")
        req = lambda: call(key, form if files else {**form, "n": a.n}, files, out_json)
        read = lambda: Path(out_json).read_text(errors="replace") if Path(out_json).exists() else ""
        code, err = req()
        if code == "400" and "size" in read():
            form["size"] = FALLBACK_SIZE   # 사용자 크기를 안 받으면 3:2로 만들고 make_hero.py가 가운데를 자른다
            code, err = req()
        body = read()
        if code != "200":
            try:
                e = json.loads(body).get("error", {})
                msg = f"{e.get('type', '')} {e.get('code', '')}: {e.get('message', '')}"
            except json.JSONDecodeError:
                msg = body[:300] or err
            sys.exit(f"❌ 이미지 API {code} — {msg}")
        data = json.loads(body)
    for old in d.glob("hero_cand_*.png"):
        old.unlink()
    outs = []
    for i, it in enumerate(data.get("data", []), 1):
        p = d / f"hero_cand_{i}.png"
        p.write_bytes(base64.b64decode(it["b64_json"]))
        outs.append(p)
    u = data.get("usage", {})
    print(f"후보 {len(outs)}장 — {a.model} {form['size']} {a.quality} (토큰 입력 {u.get('input_tokens', '?')} · 출력 {u.get('output_tokens', '?')})")
    for p in outs:
        print(f"  {p}")
    print("→ 에이전트가 각 후보를 열어 본다: 글자·숫자·로고, 얼굴·손 이상, ヒカリちゃん 모양(단발 남색 머리·주황 핀·민트 재킷), 글 내용과 맞는지 → 하나 골라 make_hero.py")


if __name__ == "__main__":
    main()
