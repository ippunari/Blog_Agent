---
name: blog-publish
description: BlogAgent 9단계 발행 (Ghost 초안 업로드까지 — 발행은 사람). 「발행 준비」 주제 카드의 다듬은 초안 drafts/&lt;slug&gt;.md를 사이트 ヒカリちゃん 기사 템플릿 HTML(스타일 카드 + 본문 카드: 각주·まとめ 말풍선·판정표·FAQ·SOURCES·CTA)로 바꾸고, Ghost 입력값·미리보기 체크리스트(ghost.md)·대표 이미지 프롬프트를 publish/&lt;slug&gt;/에 만들고, .env에 키가 있으면 ghost_upload.py로 Ghost에 초안(draft)으로 올린다. 사람이 ◆ Ghost 미리보기 확인 후 발행·예약하면, 「발행했어 &lt;slug&gt; &lt;URL&gt;」로 공개 글 점검·역링크 조각·카드 발행 완료·done 폴더 이동까지. "발행", "blog-publish", "Ghost에 올릴 파일", "발행했어", "예약했어", "대표 이미지", "Ghost에 올려", "초안 올려" 요청 때 쓴다.
argument-hint: "[slug] | 발행했어 <slug> <URL> | 예약했어 <slug> <URL> <YYYY-MM-DD HH:MM> | 이미지 <slug> <파일>"
---

# blog-publish (발행 — Ghost 초안까지)

## 0. 먼저 읽기 (매번)
1. `rules/common.md` — 1장 CTA, 6장 SEO 9~12(이미지·구조화 데이터·날짜·태그), 7장 운영 보안
2. `rules/blog-publish.md` — 변환·이미지·Ghost 설정·미리보기·발행 시간·발행 후
- 규칙과 이 파일이 다르면 **rules가 원본**이다. 규칙끼리 충돌하면 사람에게 묻는다

## 철칙 (발행 단계)
- **에이전트는 발행하지 않는다.** Ghost에는 **초안(draft)까지만** 올린다 (`ghost_upload.py`, D62). 발행·예약 버튼은 ◆ 미리보기를 본 사람이 누른다 (철칙 2)
- `.env` 키 파일을 열거나 출력하지 않는다 — 스크립트만 읽는다
- **글을 고치지 않는다.** 변환만 한다 — 문장·사실·메타는 초안 그대로. 고칠 것이 보이면 멈추고 앞 단계로 (사실 → blog-factcheck, 문장 → blog-polish)
- 이미지에 실존 인물·타사 로고를 넣지 않는다. 대표 ヤン 사진은 「代表ヤンのひとこと」 상자의 사이트 아바타만
- API 키·관리자 계정 정보를 파일·대화에 남기지 않는다 (common.md 7장)
- 작업 파일은 로컬에만 (`publish/`는 git에 올리지 않는다, D42). 보고는 **한국어**, 글은 **일본어**

## 1. 카드 고르기
- 인자 slug → 그 카드. 인자 없음 → `briefs/*.md`(하위 폴더 제외)에서 `status: 발행 준비` 중 ① 속보 먼저, 마감이 가까운 순 ② 일반은 `selected_at` 순. 시작 전에 한 줄로 알린다
- 속보는 마감을 본다. 지났으면 만들지 않는다 (스크립트도 멈춘다) — D34대로 **사람에게 묻지 않고 깊이 있는 글로 돌린다** (D79): 카드 `route: 일반`·`kind: 새 글`·`deadline: 없음`·`converted_from: 속보 (YYYY-MM-DD 마감 지남)`·`status: 조사 대기` → 보고 맨 앞에 「속보 마감 지남 → 깊이 있는 글로 돌림」. 노트·설계안·초안은 옮기지 않는다 (blog-research가 일반 범위를 보충하고 설계부터 다시)

## 2. 대표 이미지 — 프롬프트 → ChatGPT(Codex) 이미지 생성 → 에이전트가 고름 (D63)
기본은 이 컴퓨터의 Codex CLI(사람의 ChatGPT 계정 로그인 — 구독 사용량, 비용 없음). `--engine api`는 OpenAI API 크레딧이 있을 때. 둘 다 안 되면 사람이 프롬프트로 만든다 (D50)
- `publish/<slug>/hero_prompt.md`에 쓴다 (한국어 설명 + 생성용 영어 프롬프트):
  - **주인공은 글 내용** (D64) — ヒカリちゃん이 아니다. 글을 요약해 그림으로: 아래 절을 이 이름 그대로 쓴다 (make_hero_ai.py가 확인하고, 초안의 제목·3行まとめ·H2를 프롬프트에 자동으로 붙인다)
    - `## 주제 한 줄` 메인 키워드 + 글이 말하는 것
    - `## 장면 요소` `- ` 목록 3~5개: 글의 요점(3行まとめ·H2)마다 짝지은 구체 사물·상황 — 왼쪽에서 오른쪽으로 글의 흐름(무슨 일 → 영향 → 대응 → 확인)처럼. 「노트북의 체크 표시」처럼 어느 글에나 맞는 것은 안 된다
    - `## 라벨` 사물·간판에 붙일 라틴 문자 짧은 말 0~5개(쉼표로, 12자 이내, 예: `PHP, UPDATE, CHECK`) 또는 「없음」. 일본어·숫자·날짜·로고 모양 금지
    - `## ヒカリちゃん` 「없음」 또는 「조연」(작게 안내 — 이때만 참고 그림을 보낸다)
    - 화면: 사이트 글 머리 전체를 채우는 **가장자리까지 꽉 찬 장면**(빈 배경·여백 없이). 위·왼쪽 기준 21:9로 잘리고 아래에 본문 카드가 겹친다 → 라벨·핵심 사물·얼굴은 아래 25%·오른쪽 끝 6% 밖 (배치 문구는 스크립트가 붙인다). 실존 인물·실제 제품 화면·공포 표현 금지
  - 톤: 사이트 기존 대표 이미지와 같게 — 밝고 따뜻한 빛, **깔끔한 일러스트(매끈한 색면·선명한 선)**, 1.9:1. 수채 종이 질감·잔무늬는 파일이 무거워져(200KB 초과) 쓰지 않는다 (스타일 문구는 스크립트가 붙인다)
  - ヒカリちゃん이 조연이면 참고 그림 `https://cms.ondi.jp/content/images/2026/10/hikari_welcome.png`(어깨까지 단발 남색 머리·주황 머리핀·민트 재킷·남색 바지)를 스크립트가 같이 보낸다
  - alt 후보(일본어, 보이는 것을 설명) 1개
- 만들기 (키가 있을 때):
```bash
python3 -I .claude/skills/blog-publish/make_hero_ai.py <slug> --dry-run   # 보낼 프롬프트 확인
python3 -I .claude/skills/blog-publish/make_hero_ai.py <slug>             # Codex로 후보 1장 → publish/<slug>/hero_cand_1.png (1~2분)
```
  - ヒカリちゃん이 나오면 사이트 참고 그림을 같이 보낸다(edits). 프롬프트 끝에 글자·숫자·로고·실존 인물 금지 문구가 자동으로 붙는다
  - **후보를 모두 직접 열어 본다**: ① 블라인드 확인 — 글을 모른다고 치고 그림만 한 문장으로 설명해 적는다. 글의 주제와 요점(무슨 일·무엇을 하라는지)이 그 문장에 없으면 다시 ② 라벨 철자, 그 밖의 글자·숫자·로고, 얼굴·손 이상, ヒカリちゃん 모양(단발 남색 머리·주황 핀·민트 재킷), 글 내용과 맞는지 → 가장 나은 것 하나 → 아래 make_hero.py. 둘 다 안 되면 프롬프트를 고쳐 한 번만 다시 (그래도 안 되면 사람에게)
  - 사람이 ◆ 미리보기에서 「다시 만들어」 하면 이 단계부터 다시 → 3장 → 3-2 (같은 초안에 대표 이미지가 바뀐다)
- 사람이 원본을 주면 (「이미지 <slug> <파일>」) 또는 고른 후보:
```bash
python3 -I .claude/skills/blog-publish/make_hero.py <원본> <slug> --alt "<일본어 alt>"
```
  → `publish/<slug>/<slug>_hero.webp` 1800×945 WebP 200KB 이하 + `hero_alt.txt` + `hero_site_preview.png`. **사이트 표시 미리보기를 직접 열어** 주제 장치·키워드 글자·얼굴이 흰 띠(본문 카드)와 잘린 곳 밖에 있는지 본다 — 가리면 프롬프트 배치를 고쳐 다시
- 이미지가 아직 없어도(자동 생성 실패·한도 포함) **기다리지 않고** 3장·3-2장(업로드)으로 간다 — 모든 글 (D79). ghost.md에 「아직 없음」, 보고에 「대표 이미지 필요 — hero_prompt.md」. 이미지가 생기면 「이미지 <slug> <파일>」 → 3장 → 3-2장으로 같은 초안 갱신

## 2-2. 본문 이미지 (에이전트, D55) — 사람은 ◆ 미리보기에서 남김/뺌만
rules/blog-publish.md 「본문 이미지」. 속보 1~2장, 일반 2~4장. 섹션 내용과 직접 관련된 것만 (꾸밈용 금지)
- **설계안 「## 그림 자리」 표부터** 만든다 (D96): 그 섹션·종류·보여 줄 것·쓸 사실 그대로. 다듬은 초안에서 그 섹션이 빠졌거나 사실이 바뀌었으면 건너뛰고 ghost.md에 「그림 자리 n 건너뜀 — 이유」. 표에 없는 그림은 더 맞는 자리가 보일 때만 더한다 (장수 상한 안에서). 「없음」이면 억지로 찾지 않는다
```bash
I=.claude/skills/blog-publish/find_images.py
python3 -I $I add-diagram publish/<slug>/img/<이름>.svg <slug> --section N --alt "…" --caption "…出典：…（図：編集部作成）"
python3 -I $I search "<영어 검색어>"            # Commons 후보 (라이선스·상표 제한·부적절 맥락은 자동으로 거름)
python3 -I $I add-commons "File:…" <slug> --section N --alt "…" --caption "…（イメージ）"
python3 -I $I add-usgov <이미지URL> <slug> --page <실린 페이지> --agency CISA --section N --alt "…" --caption "…"
```
- **편집부 그림 먼저**: 노트 사실(날짜·판 번호·순서·비교)을 SVG로. 사이트 색(남색 #18394b·주황 #df7138·민트 #dde9e3·크림 #fbf6ea), viewBox로 크기 맞춤, 글자는 일본어. 그림 안에 출처 줄을 넣지 않는다(캡션에). 노트에 없는 사실·날짜는 넣지 않는다 (철칙 4)
- **사진**: 후보 썸네일을 내려받아 **직접 열어 본다** — 알아볼 수 있는 얼굴·로고·글자, 사건·정치 맥락이 있으면 쓰지 않는다. 캡션은 사실을 새로 말하지 않는 설명(「〜（イメージ）」)
- alt는 보이는 것을 일본어로 (10자 이상)
- 사람이 「이미지 N 빼」 → `python3 -I $I drop <slug> N` → 3장 다시

## 3. 파일 만들기
- **글 머리 보드 값** `publish/<slug>/board.json` 을 먼저 쓴다 (D65) — 흰 보드 자체는 사이트가 모든 공개 글에 자동으로 그리고, 그 안의 분류 줄·태그 알약은 본문 카드 맨 앞 `hta-top`에서 읽는다. 기존 글과 같은 말투로:
  - `kind` 분류 줄의 굵은 말 1개 (예: 보안 `速報`·`改善編 05`·`判定表`·`チェックリスト`, AI `答え合わせ`·`実践編`·`最新版`)
  - `cat` 태그 알약 「·」로 2~4개 (예: `WordPress · PHPのバージョン · サーバー会社別`)
  - `no` 번호 표시 (보안 `PHPフリー NEWS`·`PHPフリー FIX 05`, AI `HowtoAI 103` — 기존 최대 번호 + 1)
  - `topic` AI 축만: 분류 줄 가운데 말 (예: `AI × 実務`·`ChatGPT`·`AIニュース`)
  - 분류 줄 앞부분·읽는 시간·更新日은 스크립트가 넣는다 (tags.json `board`)
```bash
B=.claude/skills/blog-publish/build_publish.py
python3 -I $B drafts/<slug>.md --check-links
```
- 만드는 것 (`publish/<slug>/`): `card1-style.html`(템플릿 CSS) · `card2-body.html`(본문) · `preview.html` · `ghost.md`(입력값·체크리스트)
- 변환 (rules/blog-publish.md 「초안 표시 변환」): `[S]` 삭제 — 본문에 각주 번호를 내지 않는다(출처는 문장 속 「IPAによると」 같은 출처명 + 글 끝 SOURCES, D51). 쓰인 S번호가 SOURCES에 있는지만 확인 / `[EXP]`·`[OP]`·`<!-- 차별 -->` 삭제 / `<!-- NN Label -->` → 섹션 번호 라벨 / `:::box 3行まとめ` → 요약 상자, `わかること`·`こんな方に` → 독자 상자, `:::guide` → 案内(ヒカリちゃん 그림), `:::matome` → まとめ 말풍선, `:::rep` → 대표 말풍선, `:::note` → 주의 상자, 글 끝 `:::cta` → CTA 상자(보조는 아래 한 줄)·옆 칸 버튼, 중간 `:::cta` → 중간 CTA / FAQ → 접지 않는 Q&A + FAQPage JSON-LD / SOURCES → 출처 목록(발행처「제목」（발표일·확인일） 도메인)
- 오류(❌)가 있으면 파일을 쓰지 않는다. 변환 문제(스크립트)면 고치고, 초안 문제면 멈추고 앞 단계로
- **눈으로 보기**: Chrome 헤드리스로 데스크톱 1280px·휴대폰 375px(iframe 감싸기) 화면을 찍어 직접 본다 — 표 넘침, 상자 깨짐, 남은 표시, CTA 버튼, 그림
```bash
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; P=$PWD/publish/<slug>; SP=<스크래치패드>
"$C" --headless=new --disable-gpu --hide-scrollbars --user-data-dir=$SP/chrome --window-size=1280,6000 --screenshot=$SP/pv-d.png "file://$P/preview.html"
echo "<html><body style='margin:0'><iframe src='file://$P/preview.html' style='width:375px;height:10000px;border:0'></iframe></body></html>" > $SP/m.html
"$C" --headless=new --disable-gpu --hide-scrollbars --user-data-dir=$SP/chrome --allow-file-access-from-files --window-size=600,10000 --screenshot=$SP/pv-m.png "file://$SP/m.html"
```
  (긴 그림은 Pillow로 2,000~2,500px씩 잘라서 본다)
- 카드 머리에 `publish: publish/<slug>/ (YYYY-MM-DD)` 추가. 상태는 「발행 준비」 그대로 (◆ 미리보기 대기)

## 3-2. Ghost에 초안 올리기 (D62)
```bash
U=.claude/skills/blog-publish/ghost_upload.py
python3 -I $U <slug> --dry-run   # 보낼 칸 확인 (네트워크 없음)
python3 -I $U <slug>             # 초안 만들기 — 다시 돌리면 같은 초안만 갱신 (publish/<slug>/ghost_post.json)
```
- `.env`에 키가 없으면 「키 없음」으로 멈춘다 → 4장에서 사람이 ghost.md대로 붙여 넣는다
- 태그는 `tags.json`의 실제 slug만 (없는 태그는 붙이지 않고 ⚠). 사이트 태그가 바뀌면 tags.json을 고친다
- 카드에 `site_axis:`가 있으면 태그·글 머리 보드는 그 축으로 (사람이 정한 카드만, D68). 주제 축에 태그·보드가 없으면 멈추고 묻는다
- 대표 이미지·본문을 고쳐 3장을 다시 돌렸으면 이 단계도 다시 (같은 초안 갱신). 이미 사람이 발행·예약한 글이면 스크립트가 멈춘다
- **사람 실습 자리 표시**(`:::trial`)가 있는 초안도 올린다 (D79): build_publish.py가 Ghost 제목에만 `[실습 필요] `를 붙이고(meta_title·og_title·slug는 그대로) 본문에 「◆ 실습 필요」 상자를 넣는다 → ghost_upload.py가 카드를 `status: 실습 대기`·`ghost_draft: <편집 화면>`으로 바꾼다
- 「실습 끝났어」 뒤 섹션을 채워 3장부터 다시 돌리면 제목 표시·상자가 빠지고, ghost_upload.py가 같은 초안을 갱신하며 카드를 「발행 준비」로 되돌린다

## 4. ◆ 사람에게 넘기기 (보고하고 기다린다)
- **실습 대기 카드**(제목 `[실습 필요]`)는 보고 맨 앞에 「사람 실습 필요 — 실습 문서 <trial_doc>, 기한 <trial_due>, Ghost 초안 <ghost_draft>. 이 상태로 발행하지 않는다 — 결과를 적고 「실습 끝났어 <slug>」」. 미리보기·발행은 채운 뒤
보고 (한국어, 짧게): 카드 / 마감(속보) / 만든 파일 경로 / 점검 결과 / 대표 이미지 상태(프롬프트 경로) / 발행 시각 / **사람이 할 일** = (초안이 올라갔으면) Ghost 편집 화면 주소에서 미리보기 → `ghost.md` 5장 체크리스트 → 「Publish only」로 발행·예약 → 「발행했어 <slug> <URL>」 (키가 없으면 ghost.md 1~3장대로 붙여 넣기부터)
- 사람이 미리보기에서 고칠 점을 말하면: 사실·문장이면 앞 단계, 표시·디자인이면 스크립트·템플릿을 고쳐 3장 다시

## 5. 발행 후 (「발행했어」·「예약했어」)
```bash
A=.claude/skills/blog-publish/after_publish.py
python3 -I $A <slug> <URL>                                # 공개됨
python3 -I $A <slug> <URL> --scheduled "YYYY-MM-DD HH:MM"  # 예약
python3 -I $A <slug> --verify-live                        # 예약 글이 공개된 뒤
```
- URL·slug 확인 → 공개 글 점검(제목·SOURCES·남은 표시·**실습 자리 표시 `[실습 필요]`·「◆ 실습 필요」(D79)**·FAQPage 1개·og:image) → 역링크 넣을 곳 다시 확인(`--verify-links`) → `backlinks.md` → 카드 `published_at`·`url`·`status: 발행 완료` → 카드·노트·설계·초안·보고서·publish 폴더를 `done/YYYY-MM/`로
- 점검 오류면 아무것도 옮기지 않는다 → 사람에게 무엇을 Ghost에서 고칠지 알린다
- 보고: 점검 결과 / **역링크 붙이기**(`publish/done/YYYY-MM/<slug>/backlinks.md` — 사람이 기존 글 카드에 붙인다, 위치 문제는 묻는다) / Search Console 색인 요청(연결 뒤, 지금은 남은 일)
- **점검이 통과하면 이어서 바로 blog-distribute를 실행한다** (SNS 문안 → ◆ 확인 → 「올려」, D66). 예약 글은 `--verify-live` 통과 뒤

## 하지 않는 것
- Ghost에서 발행·예약·삭제, 이메일 발송 (Publish only) — 초안 올리기만 한다 (D62)
- 문장·사실·메타 고치기 (blog-polish·blog-factcheck), 새 태그 만들기 (기존 태그만 — 없으면 묻는다)
- 기존 글 직접 고치기 — 역링크는 조각만 만들고 사람이 붙인다
- 발행 파일을 공유 드라이브·git에 올리기 (로컬, D42)
