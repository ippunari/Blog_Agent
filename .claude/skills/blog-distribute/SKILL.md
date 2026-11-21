---
name: blog-distribute
description: BlogAgent 10단계 SNS 배포. 발행 직후(blog-publish 「발행했어」에 이어서) 발행 완료 카드의 최종 글·설계안 SNS 포인트로 X·Threads·note·LinkedIn·Facebook 문안을 플랫폼마다 새로 써서 publish/done/YYYY-MM/&lt;slug&gt;/sns.md에 두고 check_sns.py로 점검한다. 사람이 ◆ 확인하고 「올려 &lt;slug&gt;」 하면 sns_post.py가 키가 있는 곳(X·Threads·LinkedIn·Facebook 페이지)에 게시하고, note·키 없는 곳은 사람이 붙여 넣는다. "SNS", "blog-distribute", "배포", "SNS 문안", "올려" 요청 때 쓴다.
argument-hint: "<slug> | 올려 [<slug>|오늘|YYYY-MM-DD] [x,threads,linkedin,facebook]"
---

# blog-distribute (SNS 배포)

먼저 읽는다: `rules/common.md`(특히 3·4·7장), `rules/blog-distribute.md`, `rules/voice-hikari.md`(5·7장). 규칙과 이 문서가 다르면 rules가 원본.

## 0. 언제
- **발행 직후 바로** (D66). blog-publish 「발행했어 <slug> <URL>」에서 after_publish.py가 통과하면 이어서 이 스킬을 실행한다. 예약 글은 `--verify-live`로 공개가 확인된 직후
- 단독 실행 `/blog-distribute <slug>`: **발행 완료 카드**(`briefs/done/YYYY-MM/<slug>.md`)만 받는다. 없으면 멈추고 blog-publish를 안내한다
- 인자 slug가 없으면 `briefs/done/*/` 중 `url:`은 있고 `sns:`가 없는 카드를 최근 발행 순으로

## 1. 입력 (모두 done/YYYY-MM/ 안, 경로는 sns_common.paths)
- 카드: `url`(공개 주소)·`type`·`cta`·`rep_comment`
- 최종 글 `drafts/done/YYYY-MM/<slug>.md`: 제목·메타(og_title·excerpt)·3行まとめ·본문 — **SNS 문안의 사실은 여기에 있는 것만** (철칙 4. 조사 노트에서 새 사실을 가져오지 않는다)
- 설계안 `outlines/done/YYYY-MM/<slug>.md` 「SNS 포인트」: 수치·의견(편집부)·질문
- 대표 이미지 `publish/done/YYYY-MM/<slug>/<slug>_hero.webp`

## 2. 문안 쓰기 (일본어, 플랫폼마다 새로)
UTM 링크: `<url>?utm_source={x|threads|note|linkedin|facebook}&utm_medium=social&utm_campaign=<slug>` — 플랫폼마다 자기 이름

| 플랫폼 | 길이 | 쓰는 법 | 링크 자리 |
|---|---|---|---|
| X | 전각 140자 (X 가중치 280) | SNS 포인트의 수치나 질문으로 시작, 해시태그 1~2, 대표 이미지 첨부 | `### 返信`(답글)에 짧은 한 줄 + 링크 |
| Threads | 500자 이내 | ヒカリちゃん 대화체(「ヒカリです。」로 시작 가능), 짧은 문단 | 본문 끝에 링크 1개 |
| note | 1,000~2,000자 | 요약판: 인사 → 무슨 일 → ■ 소제목 3~4개(글의 판단·차별 포인트) → 「ブログでは〜までまとめています」 → `全文はブログで` + 링크 → 해시태그 3~5. `### タイトル`도 쓴다 | 본문 안 |
| LinkedIn | 300~600자 | 회사 관점: 핵심 판단·수치, 번호 2~3개. 대표 한마디(카드 `rep_comment`)가 있을 때만 첫머리에 「代表ヤンのひとこと」로 그대로 | `### 最初のコメント`에 링크 |
| Facebook | 200~400자 | 중소기업 사장층에게 말을 거는 첫 줄 → 할 일 1~2개 → 「記事にまとめました」 | `### リンク`에 URL만 (링크 미리보기) |

지킬 것
- **복사 금지**: 블로그 본문 문장을 그대로 옮기지 않는다, 플랫폼끼리도 같은 문장 없이 (30자 이상 같은 구간 = 오류). 「」 짧은 인용(1~2문장)은 예외
- 사실/의견 나누기: 의견은 「編集部では〜」 (대표 의견을 지어내지 않는다, 철칙 1). 해 보지 않은 것을 「試しました」라고 하지 않는다
- 글 종류의 CTA 결: 보안 글은 겁주지 않고 할 일과 함께 / AI 글은 뉴스레터가 주 CTA지만 SNS에서는 글 링크만 (구독 입구가 생기면 규칙에서 정한다)
- 금지: common.md 4장 과장·공포·AI 문투, 「〜ね/〜よ」 끝맺음(질문 문장은 예외), 계정 ID(@…)·개인 이름

## 3. sns.md 만들기 → 점검
`publish/done/YYYY-MM/<slug>/sns.md` (형식은 `sns_common.py` 머리 설명):
~~~
---
slug: <slug>
url: <카드 url>
created_at: YYYY-MM-DDTHH:MM+09:00
hero: <대표 이미지 절대 경로>
---
# SNS 문안: <글 제목>
## x
### 本文
```text … ```
### 返信
```text … ```
## threads … ## note (### タイトル / ### 本文) … ## linkedin (### 本文 / ### 最初のコメント) … ## facebook (### 本文 / ### リンク)
~~~
```bash
D=.claude/skills/blog-distribute
python3 -I $D/check_sns.py <slug>     # 오류 0까지 고친다 (공개 URL 200도 확인)
python3 -I $D/sns_post.py <slug>      # dry-run: 플랫폼별로 실제 보낼 요청 내용
```
- 통과하면 카드에 `sns: publish/done/YYYY-MM/<slug>/sns.md (YYYY-MM-DD)`를 적는다 (`sns_common.set_front`)
- 통과하면 `check_sns.py`가 **날짜별 모음 `sns/YYYY-MM-DD.md`**(발행일 기준)를 다시 만든다 — 그날 글의 문안을 발행 순으로, 플랫폼마다 ✅ 올림 / ⏳ 「올려」 대기 / ✋ 붙여 넣기. 보기용이라 손으로 고치지 않는다 (원본은 글별 sns.md). 따로 만들 때: `python3 -I $D/sns_digest.py [YYYY-MM-DD|오늘]`

## 4. ◆ 사람 확인 요청 (한국어, 짧게)
- 맨 위에 **slug**를 적는다 (「`<slug>` — 문안 5개」) → 문안 5개를 **플랫폼별로 그대로** 보여 준다(사람이 바로 읽게) + 날짜별 모음 파일 경로
- 자동으로 올라갈 곳 / 사람이 붙여 넣을 곳(note, 키가 없는 플랫폼, Facebook 개인 계정 공유)
- 계정 표시: `.env`의 `SNS_ACCOUNT_LABEL`이 `test`면 「⚠ 시험 계정으로 올라갑니다」
- X 비용: 링크 답글이 있어 글 1편 약 $0.22 (본문 $0.015 + 링크 글 $0.20, 2026-11 X 요금)
- 「고쳐」 → 고친 뒤 3장 점검부터 다시 / 「올려」 → 5장
- 끝에 한 줄: 「올려」(이 글) · 「올려 오늘」(오늘 글 전부)

## 5. 「올려」
| 사람이 쓴 말 | 대상 | 실행 |
|---|---|---|
| 「올려」 | **방금 문안을 보여 준 글** (이 대화에서 마지막으로 보여 준 slug). 보여 준 글이 없거나 여러 편이면 slug 목록을 보여 주고 묻는다 | `sns_post.py <slug> --go` |
| 「올려 <slug>」 | 그 글. slug 자리에 파일 이름(`briefs/x.md`)·경로·글 주소(UTM 붙어도 됨)도 받는다 | `sns_post.py <그대로> --go` |
| 「올려 오늘」·「올려 YYYY-MM-DD」 | 그날 발행한 글 중 아직 안 올린 것 전부 | ① `sns_post.py 오늘` (dry-run)으로 「N편 × 플랫폼」 목록을 보여 준다 → ② 사람이 한 번 더 「응」 → `sns_post.py 오늘 --go` |
| 뒤에 `x,threads`처럼 플랫폼 | 그 플랫폼만 | `--only x,threads` |

- **사람의 「올려」 없이 `--go`를 붙이지 않는다** (철칙 2). 「확인했어」 「좋아」처럼 게시 지시인지 애매하면 묻는다
- 날짜로 올릴 때는 한 번에 여러 편이 나가므로 ① 목록 → ② 「응」 두 단계를 건너뛰지 않는다
- 결과: 플랫폼별 게시 주소 → `sns_posted.json`·카드 `sns_posted_at`·`sns_platforms` (스크립트가 적는다)
- 답글·첫 댓글만 실패하면(`reply_error`·`comment_error`) 본문은 이미 올라간 것 — 사람에게 그 링크 한 줄을 손으로 붙이도록 알린다. 다시 `--go` 하지 않는다(중복 게시)
- 이미 올린 플랫폼을 다시 올리는 것(`--force <플랫폼>`)은 사람이 명시했을 때만
- 보고: 올라간 주소 / 사람이 붙여 넣을 것 — **날짜별 모음 `sns/YYYY-MM-DD.md`의 ✋ 항목**(note 제목·본문·見出し画像, 키 없는 플랫폼, Facebook 개인 계정 공유) / 실패와 이유

## 시험 (발행 전 글로)
```bash
python3 -I $D/check_sns.py <slug> --sns $SP/sns.md --draft drafts/<slug>.md --card briefs/<slug>.md --url <예정 URL> --offline
python3 -I $D/sns_post.py  <slug> (같은 인자) [--go — SNS_ACCOUNT_LABEL=test일 때만]
```
- 시험 경로에서는 카드를 고치지 않는다. 출력은 스크래치패드

## 계정·키 (사람이 직접, .env 권한 600)
- 키 이름은 `sns_post.py` 머리 설명. 대화·파일·커밋·명령줄에 키를 쓰지 않는다
- **시험 계정 → 회사 계정**: `.env`의 값과 `SNS_ACCOUNT_LABEL=company`만 바꾼다(코드는 그대로). X·Threads는 그 계정으로 새 토큰, LinkedIn 회사 페이지는 `urn:li:organization:…` + LinkedIn 심사(Community Management API)를 통과한 앱의 토큰, Facebook은 페이지 토큰(개인 계정은 API로 게시 불가)
- Threads·LinkedIn 토큰은 60일 — 만료 오류(190 / 401)가 나면 사람에게 새 토큰을 부탁한다
- 긴급 정지: 프로젝트 루트에 `SNS_STOP` 파일 → 아무것도 보내지 않는다

## 하지 않는 것
- 사람의 「올려」 없이 게시, 예약 게시, 삭제·수정·DM·팔로우 (스크립트에 없다)
- note 자동 게시 (공식 API 없음 — 비공식 방법은 약관 위험)
- 블로그 본문·메타 고치기 (blog-polish), 본문에 없는 사실 쓰기
- sns.md·날짜별 모음을 공유 드라이브·git에 올리기 (로컬, D42)
- 날짜별 모음 파일을 손으로 고치기 (원본 sns.md를 고치면 다시 만들어진다)
