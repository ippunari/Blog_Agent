#!/usr/bin/env python3
"""사람 실습 문서 만들기: 카드 + 조사 노트 「직접 써 본 결과」의 체크리스트 → Google 문서로 올릴 md.

- 팀원이 읽고 바로 결과를 적을 수 있게: 안내 → 주제 → 참고 링크 → 체크리스트(노트 그대로) → 결과 적는 칸
- 참고 링크: 카드 「출처」 + 노트 핵심 사실표(출처명·등급·확인일) + 「다른 사람의 검증」의 URL. 중복 제거, D등급 제외, C등급은 「참고」로 따로
- 노트의 원문 문장은 넣지 않는다 (URL·출처명만)
- 개인 이름 칸은 두지 않는다 (「팀원」으로 기록, D45)

사용: python3 -I export_trial.py briefs/<slug>.md research/<slug>.md --due "2026-11-27 17:00" --out "$SP/trial_<slug>.md"
"""
import argparse
import re
import sys
from pathlib import Path


def front(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    out = {}
    if m:
        for ln in m.group(1).splitlines():
            k, sep, v = ln.partition(":")
            if sep:
                out[k.strip()] = v.strip()
    return out


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


URL_RE = re.compile(r"https?://[^\s)|<>」、，]+")


def norm_url(u):
    return re.split(r"[?#]", u.strip())[0].rstrip("/")


def links(card, note):
    """[(구분, 이름, URL, 메모)] — 공식·보도(A·B, 카드 출처) / 참고(C·다른 사람의 검증)"""
    seen, main, ref = set(), [], []

    def add(bucket, name, url, memo=""):
        k = norm_url(url)
        if k in seen:
            return
        seen.add(k)
        bucket.append((name, url, memo))

    # 노트 핵심 사실표: | ID | 사실 | 원문 | 출처명 | URL | 등급 | 발표일 | 확인일 |
    for ln in note.splitlines():
        if re.match(r"^\| S\d+ \|", ln):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 8 and c[4].startswith("http"):
                g = c[5]
                if g in ("A", "B"):
                    add(main, c[3], c[4], f"{g}등급 · 확인 {c[7]}")
                elif g == "C":
                    add(ref, c[3], c[4], f"C등급(단서) · 확인 {c[7]}")
    # 카드 「출처」
    sm = re.search(r"^## 출처[^\n]*\n(.*?)(?=^## |\Z)", card, re.S | re.M)
    for ln in (sm.group(1).splitlines() if sm else []):
        label = ln.strip("- ").split(":")[0].strip()
        for u in URL_RE.findall(ln):
            add(main, label, u, "주제 카드")
    # 다른 사람의 검증
    vm = re.search(r"^## 다른 사람의 검증[^\n]*\n(.*?)(?=^## |\Z)", note, re.S | re.M)
    for ln in (vm.group(1).splitlines() if vm else []):
        for u in URL_RE.findall(ln):
            if "D등급" in ln or "| D |" in ln:
                continue
            add(ref, re.sub(r"https?://\S+", "", ln).strip("-| ").strip()[:40] or "다른 사람의 검증", u, "다른 사람의 검증")
    return main, ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card")
    ap.add_argument("note")
    ap.add_argument("--out", required=True)
    ap.add_argument("--due", required=True, help="실습 기한 (올린 날 + 1주, 예: 2026-11-27 17:00)")
    a = ap.parse_args()
    card, note = Path(a.card).read_text(), Path(a.note).read_text()
    f = front(card)
    if f.get("trial", "").split("|")[0].strip() != "사람":
        print("오류: 카드가 trial: 사람이 아님", file=sys.stderr)
        return 1
    checklist = section(note, "직접 써 본 결과")
    if "◆" not in checklist:
        print("오류: 노트 「직접 써 본 결과」에 「◆ 사람 실습 대기」 체크리스트가 없음", file=sys.stderr)
        return 1
    title = re.search(r"^# 주제 카드:\s*(.+)$", card, re.M)
    main_links, ref_links = links(card, note)
    lk = ["## 참고 링크 (보면서 실습하세요)",
          "- 조사한 날 기준입니다. 열었을 때 내용이 크게 다르거나, 이상한 페이지·다운로드로 넘어가면 실습을 멈추고 알려 주세요",
          "- 로그인이 필요한 페이지는 회사 계정으로 엽니다", ""]
    lk += [f"- {n}: {u} ({m})" for n, u, m in main_links] or ["- (공식 링크 없음)"]
    if ref_links:
        lk += ["", "참고 (개인 블로그·후기 등 — 그대로 믿지 말고 비교용으로):"]
        lk += [f"- {n}: {u} ({m})" for n, u, m in ref_links]
    link_block = "\n".join(lk)
    m = re.search(r"^- 메인 키워드:\s*(.+)$", card, re.M)
    out = f"""> **BlogAgent 실습 문서** — 이 문서대로 실습하고, 맨 아래 「결과」 칸에 적어 주세요. 다 적으면 대화창에 「실습 끝났어 {f.get('slug', '')}」라고 알려 주세요.
> **기한: {a.due} (JST)** — 어렵다면 기한 전에 알려 주세요 (연장 / 실습 없이 쓰기 / 중단 중에서 정합니다).
> 고객 정보·회사 내부 정보는 입력하지 않습니다. 캡처의 이메일·이름·계정 ID는 가려 주세요. 이 문서에 개인 이름은 적지 않습니다.

# 실습: {title.group(1).strip() if title else f.get('slug', '')}

- slug: {f.get('slug', '')}
- 글 종류: {f.get('type', '')}
- 메인 키워드: {m.group(1).strip() if m else '-'}
- 조사 끝난 날: {f.get('research', '-')}

{link_block}

## 체크리스트 (조사 노트에서)
{checklist}

## 결과 (실습한 분이 적는 칸)
- 실습한 날짜:
- 쓴 도구·요금제·버전:
- 해 본 작업과 입력한 내용 (그대로):
- 나온 결과 (그대로, 길면 앞뒤와 요점):
- 잘 안 된 것·실패 (꼭 적어 주세요):
- 찍은 화면 (파일 이름 또는 이 문서에 붙이기):
- 그 밖에 느낀 점:
"""
    Path(a.out).write_text(out)
    print(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
