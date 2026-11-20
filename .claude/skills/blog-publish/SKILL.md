---
name: blog-publish
description: BlogAgent 9단계 발행 (임시 방식 — 파일 출력). 「발행 준비」 주제 카드의 다듬은 초안 drafts/&lt;slug&gt;.md를 사이트 ヒカリちゃん 기사 템플릿 HTML(스타일 카드 + 본문 카드: 각주·まとめ 말풍선·판정표·FAQ·SOURCES·CTA)로 바꾸고, Ghost 입력값·미리보기 체크리스트(ghost.md)·대표 이미지 프롬프트를 publish/&lt;slug&gt;/에 만든다. 사람이 Ghost에 붙여 ◆ 미리보기 확인 후 발행·예약하면, 「발행했어 &lt;slug&gt; &lt;URL&gt;」로 공개 글 점검·역링크 조각·카드 발행 완료·done 폴더 이동까지. "발행", "blog-publish", "Ghost에 올릴 파일", "발행했어", "예약했어", "대표 이미지" 요청 때 쓴다.
argument-hint: "[slug] | 발행했어 <slug> <URL> | 예약했어 <slug> <URL> <YYYY-MM-DD HH:MM> | 이미지 <slug> <파일>"
---

# blog-publish (발행 — 임시 방식)

## 0. 먼저 읽기 (매번)
1. `rules/common.md` — 1장 CTA, 6장 SEO 9~12(이미지·구조화 데이터·날짜·태그), 7장 운영 보안
2. `rules/blog-publish.md` — 변환·이미지·Ghost 설정·미리보기·발행 시간·발행 후
- 규칙과 이 파일이 다르면 **rules가 원본**이다. 규칙끼리 충돌하면 사람에게 묻는다

## 철칙 (발행 단계)
- **에이전트는 발행하지 않는다.** ⚠ 대표 + 기술 보안팀 확인 전에는 Ghost API를 쓰지 않고 파일만 만든다 (D23). 발행·예약 버튼은 ◆ 미리보기를 본 사람이 누른다 (철칙 2)
- **글을 고치지 않는다.** 변환만 한다 — 문장·사실·메타는 초안 그대로. 고칠 것이 보이면 멈추고 앞 단계로 (사실 → blog-factcheck, 문장 → blog-polish)
- 이미지에 실존 인물·타사 로고를 넣지 않는다. 대표 ヤン 사진은 「代表ヤンのひとこと」 상자의 사이트 아바타만
- API 키·관리자 계정 정보를 파일·대화에 남기지 않는다 (common.md 7장)
- 작업 파일은 로컬에만 (`publish/`는 git에 올리지 않는다, D42). 보고는 **한국어**, 글은 **일본어**

## 1. 카드 고르기
- 인자 slug → 그 카드. 인자 없음 → `briefs/*.md`(하위 폴더 제외)에서 `status: 발행 준비` 중 ① 속보 먼저, 마감이 가까운 순 ② 일반은 `selected_at` 순. 시작 전에 한 줄로 알린다
- 속보는 마감을 본다. 지났으면 만들지 않고 D34대로 사람에게 (스크립트도 멈춘다)

## 2. 대표 이미지 프롬프트 (에이전트) → 이미지 (사람)
이 환경에는 이미지 생성 도구가 없다 → 에이전트가 프롬프트를 쓰고 사람이 만든다 (D50)
- `publish/<slug>/hero_prompt.md`에 쓴다 (한국어 설명 + 생성용 영어 프롬프트):
  - 장면: 글의 핵심 행동 하나 (예: 「ホームページのPHPの番号を確かめる」). 숫자·글자·로고·실존 인물·실제 제품 화면을 넣지 않는다
  - 톤: 사이트 기존 대표 이미지와 같게 — 밝은 사무실, 따뜻한 자연광, 식물·나무 책상, 부드러운 수채 느낌 일러스트, 16:9보다 넓게(1.9:1)
  - ヒカリちゃん이 나오면 참고 그림 `https://cms.ondi.jp/content/images/2026/10/hikari_welcome.png`(어깨까지 단발 남색 머리·주황 머리핀·민트 재킷·남색 바지)를 같이 넣으라고 적는다
  - alt 후보(일본어, 보이는 것을 설명) 1개
- 사람이 원본을 주면 (「이미지 <slug> <파일>」):
```bash
python3 -I .claude/skills/blog-publish/make_hero.py <원본> <slug> --alt "<일본어 alt>"
```
  → `publish/<slug>/<slug>_hero.webp` 1200×630 WebP 200KB 이하 + `hero_alt.txt`. 이미지를 직접 열어 보고 글자·로고·사람 얼굴 이상을 확인한다
- 이미지가 아직 없어도 3장으로 간다 (ghost.md에 「아직 없음」). 속보는 기다리지 않는다 — 사람에게 이미지가 필요하다고 보고에 적는다

## 2-2. 본문 이미지 (에이전트, D55) — 사람은 ◆ 미리보기에서 남김/뺌만
rules/blog-publish.md 「본문 이미지」. 속보 1~2장, 일반 2~4장. 섹션 내용과 직접 관련된 것만 (꾸밈용 금지)
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

## 4. ◆ 사람에게 넘기기 (보고하고 기다린다)
보고 (한국어, 짧게): 카드 / 마감(속보) / 만든 파일 경로 / 점검 결과 / 대표 이미지 상태(프롬프트 경로) / 발행 시각 / **사람이 할 일** = `ghost.md` 순서대로 Ghost에 초안 → 미리보기 체크리스트 → 발행·예약 → 「발행했어 <slug> <URL>」
- 사람이 미리보기에서 고칠 점을 말하면: 사실·문장이면 앞 단계, 표시·디자인이면 스크립트·템플릿을 고쳐 3장 다시

## 5. 발행 후 (「발행했어」·「예약했어」)
```bash
A=.claude/skills/blog-publish/after_publish.py
python3 -I $A <slug> <URL>                                # 공개됨
python3 -I $A <slug> <URL> --scheduled "YYYY-MM-DD HH:MM"  # 예약
python3 -I $A <slug> --verify-live                        # 예약 글이 공개된 뒤
```
- URL·slug 확인 → 공개 글 점검(제목·SOURCES·남은 표시·FAQPage 1개·og:image) → 역링크 넣을 곳 다시 확인(`--verify-links`) → `backlinks.md` → 카드 `published_at`·`url`·`status: 발행 완료` → 카드·노트·설계·초안·보고서·publish 폴더를 `done/YYYY-MM/`로
- 점검 오류면 아무것도 옮기지 않는다 → 사람에게 무엇을 Ghost에서 고칠지 알린다
- 보고: 점검 결과 / **역링크 붙이기**(`publish/done/YYYY-MM/<slug>/backlinks.md` — 사람이 기존 글 카드에 붙인다, 위치 문제는 묻는다) / Search Console 색인 요청(연결 뒤, 지금은 남은 일) / 다음 단계 blog-distribute

## 하지 않는 것
- Ghost API로 올리기·발행·예약 (확인 전, D23), 이메일 발송 (Publish only)
- 문장·사실·메타 고치기 (blog-polish·blog-factcheck), 새 태그 만들기 (기존 태그만 — 없으면 묻는다)
- 기존 글 직접 고치기 — 역링크는 조각만 만들고 사람이 붙인다
- 발행 파일을 공유 드라이브·git에 올리기 (로컬, D42)
