# BlogAgent

> 상태: 규칙 확정(v1, 2026-11-19). 모든 규칙은 **운영하며 보강**한다. 스킬 제작은 다음 단계.

## 개요
영어·한국어·일본어·중국어권의 AI·보안 뉴스를 모아 주제를 고르고, AI 뉴스·사용법·보안·개발 글을 써서 회사 블로그(Ghost, https://atatakaidigital.com/ja/blog)에 발행한 뒤, X·Threads·note·LinkedIn·Facebook과 주간 뉴스레터로 퍼뜨리는 에이전트. 단계마다 스킬 하나로 만든다.

## 목표
- 검색 유입을 늘리고 **구독 → 문의 → 고객**으로 잇는다
- 현재 상황: 방문·유입이 거의 없음, 고객은 대표 지인 경로뿐, 데이터(GSC/GA4) 거의 없음
- 새 도메인에서 사실상 처음부터 시작 (옛 도메인은 폐쇄, HowtoAI 글은 옛 사이트에서 옮겨 옴)
- 3개월 목표: 한 달 운영 후 데이터를 보고 정한다

## 대상 독자
- IT 담당자가 없는 일본 중소기업의 사장·실무자
- 생성AI를 업무에 써 보고 싶은 사람 / AI 도입을 검토하는 사람
- 홈페이지·메일 보안이 걱정되는 사람
- 개발을 맡기고 싶은데 견적·준비가 불안한 사람

## 연결할 서비스
- AI 도입 지원(상담·교육·구축) — 새로 시작
- PHP Free 30초 무료 점검 / 60분 무료 상담
- 빠른 개발(迅速開発) 견적·상담
- 뉴스레터 구독 (모든 글의 기본 출구)
- 자체 제품(ユトレル, ワタレル) 글은 당분간 쓰지 않음

## 작업 흐름 (개정판)
◆ = 사람이 확인·결정하는 지점

| 단계 | 스킬 | 하는 일 |
|---|---|---|
| 0 | `rules/common.md` | 전략·공통 규칙 (모든 스킬이 참조) |
| 1 | blog-collect | 4개 언어권 출처·질문 입구 수집, 매일 2회 |
| 2 | blog-topic | 점수 매기기 → 추천에 ○를 넣은 시트 ◆ 사람이 확인·수정 (아침 4 · 저녁 2) |
| 3 | blog-perspective | 보안·개발 깊이 글만 대표에게 질문 3개 ◆ 대표가 시트에 한국어로 답 |
| 4 | blog-research | 1차 출처·보충 자료 / 사용법은 ◆ 사람이 직접 써 보기 |
| 5 | blog-outline | 키워드·제목·훅·목차·CTA·내부 링크·SNS 포인트 |
| 6 | blog-draft | 섹션별 초안, 문장마다 출처 표시 |
| 7 | blog-factcheck | 수치·날짜·고유명사·인용 대조, SOURCES |
| 8 | blog-polish | 문장 다듬기 → 바뀐 사실 재대조 → SEO·AEO·AIO 점검 → 메타 |
| 9 | blog-publish | 이미지 → ◆ 미리보기 확인 → Ghost 예약 발행 |
| 10 | blog-distribute | 5개 SNS용으로 다시 쓰기 ◆ 확인 후 게시 |
| 11 | blog-newsletter | 주간 뉴스레터 ◆ 테스트 발송 확인 후 발송 |
| 12 | blog-measure | 주간 리포트·월간 개선안 ◆ 반영 승인 |

### 두 가지 경로
- **속보** (발표 72시간 이내, 아침 2 + 저녁 2): 대표 코멘트 없음 / 조사 30분 이내 / 발행 직전 공식 발표 재확인 / ◆ 미리보기 확인 즉시 발행. 해외 화제는 일본어 자료가 없을 때, 보안 소식은 대응이 필요할 때
- **깊이 있는 글** (6개월 이상 유효, 하루 2 = 새 글 1 + 기존 글 개편 1): AI 실습 글 중심 + 보안·개발 대책. 보안·개발 글만 대표 코멘트를 다음 영업일 오전까지 기다림 / 전체 단계 수행 / 평일 오전 8시(JST) 예약 발행

## 역할 분담 (D36)
- **에이전트가 할 수 있는 일은 모두 에이전트가 한다**: 수집·주제 추천·조사·직접 실습(할 수 있는 도구)·다른 사람의 검증·후기 수집·설계·초안·사실 대조·다듬기·SNS 문안·뉴스레터 원고·리포트
- **사람이 하는 일은 셋뿐**: ◆ 확인·결정(주제 ○ 확인, 미리보기, 게시·발송 승인 — 철칙 2) / 대표 코멘트 / 에이전트가 못 하는 실습(계정·기기가 필요한 것)
- 에이전트가 한 실습과 다른 사람의 정보는 **누가 했는지 그대로** 쓴다 (철칙 1·4·5)

## 발행 리듬
평일 하루 6편 (D31). 사람 시간은 잠정 — 운영하며 실제 시간을 재서 고친다

| 항목 | 주당 | 사람 시간 |
|---|---|---|
| 속보 (아침 2 + 저녁 2) | 20편 | 각 15분 (미리보기 확인) → 5시간 |
| 깊이 있는 글 (새 글 1 + 개편 1) | 10편 | 각 2시간 → 20시간 + 사람 실습 |
| 주제 확인 (시트) | 10회 | 각 5분 → 1시간 |
| 뉴스레터 | 1회 (금요일 오전 8시) | 30분 |
| SNS 확인 (5곳 × 30편) | 150건 | 약 15시간 |
| **합계** | | **약 주 41시간** — ⚠ 담당자 증원 전제 |

## 규칙 파일
| 파일 | 내용 |
|---|---|
| [rules/common.md](rules/common.md) | 글 종류·CTA·도입부·필자·문체·SEO/AEO/AIO·운영 보안 |
| [rules/blog-collect.md](rules/blog-collect.md) | 수집 |
| [rules/blog-topic.md](rules/blog-topic.md) | 주제 선정 |
| [rules/blog-perspective.md](rules/blog-perspective.md) | 대표 코멘트 |
| [rules/blog-research.md](rules/blog-research.md) | 조사 |
| [rules/blog-outline.md](rules/blog-outline.md) | 설계 |
| [rules/blog-draft.md](rules/blog-draft.md) | 초안 |
| [rules/blog-factcheck.md](rules/blog-factcheck.md) | 사실 대조 |
| [rules/blog-polish.md](rules/blog-polish.md) | 다듬기 |
| [rules/blog-publish.md](rules/blog-publish.md) | 발행 |
| [rules/blog-distribute.md](rules/blog-distribute.md) | SNS 배포 |
| [rules/blog-newsletter.md](rules/blog-newsletter.md) | 뉴스레터 |
| [rules/blog-measure.md](rules/blog-measure.md) | 측정 |
| [decisions.md](decisions.md) | 규칙을 정한 이유 (규칙을 바꾸기 전에 확인) |

## 작업 파일 위치 (예정)
- `candidates/YYYY-MM-DD-am|pm.md` 수집 후보 원본 → 공유 드라이브 `03_Blog/candidates`에 보기용 Google 문서 사본 / 상위 후보는 Google Sheets(회사 계정 공유)
- `topics/YYYY-MM-DD-am|pm.md` 주제 후보 순위표 (시트 연동 전 임시), `briefs/<slug>.md` 선택된 주제 카드
- `research/<slug>.md` 조사 노트
- `drafts/<slug>.md` 초안
- `factcheck/<slug>.md` 대조 보고서
- `reports/YYYY-Www.md` 주간 리포트

## 스킬 제작 순서
작업 흐름 순서대로 만든다. 앞 스킬의 실제 결과를 다음 스킬이 받아 쓰면서 연결을 확인한다 (이유: [decisions.md](decisions.md) D23)

| 순서 | 스킬 | 먼저 할 준비 | 연동 전 임시 방식 | 상태 |
|---|---|---|---|---|
| 1 | blog-collect | 후보 기록 형식 | 파일로만 저장 | ☑ |
| 2 | blog-topic | Google Sheets 칸 구성 | 회차마다 새 시트를 Drive에 올려 사람이 선택 | ☐ |
| 3 | blog-perspective | — | 대표 답을 대화로 받음 | ☐ |
| 4 | blog-research | — | — | ☐ |
| 5 | blog-outline | — | — | ☐ |
| 6 | blog-draft | **ヤン 목소리 가이드, 용어집** | — | ☐ |
| 7 | blog-factcheck | — | — | ☐ |
| 8 | blog-polish | 자동 교정 도구 설치 | — | ☐ |
| 9 | blog-publish | Ghost 스태프 계정·API(초안 권한) | Ghost에 붙여 넣을 파일로 출력 | ☐ |
| 10 | blog-distribute | SNS 계정·2단계 인증 | 게시할 글을 파일로 출력, 사람이 올림 | ☐ |
| 11 | blog-newsletter | Ghost 뉴스레터 설정 | 원고 파일로 출력 | ☐ |
| 12 | blog-measure | Search Console·GA4 | 데이터가 쌓이면 실행 | ☐ |
| 13 | 전체 연결 | — | 속보 경로·일반 경로로 묶기 | ☐ |

만드는 방법 (모든 스킬 공통)
- 스킬 하나에 세션 하나 (컨텍스트 절약)
- 실제 주제 1개를 처음부터 끝까지 이어서 통과시킨다. 새 스킬은 앞 스킬이 만든 실제 결과 파일로 시험한다
- 스킬은 `.claude/skills/<스킬명>/SKILL.md`에 만들고, 본문에서 `rules/common.md`와 해당 `rules/<스킬명>.md`를 읽게 한다
- 만들면서 규칙이 바뀌면 `rules/` 해당 파일 + 변경 이력 + `decisions.md` 갱신
- 완성하면 위 표의 상태를 ☑로 바꾸고, 커밋해서 GitHub(비공개 저장소 https://github.com/ippunari/Blog_Agent)에 push한다
- 9~11은 ⚠ 대표 + 기술 보안팀 확인 전에는 임시 방식(파일 출력)으로만

## 남은 일
- [ ] ⚠ **대표 + 기술 보안팀 확인**: AI 크롤러 허용(잠정: 모두 허용), 법률·평판 항목(명예훼손, 스텔스 마케팅 규제, 특정전자메일법, 개인정보보호법, 이미지 권리)
- [ ] ヤン 목소리 가이드: 기존 ヤン 글 5~10편 분석 → 말투 가이드·예문
- [ ] 용어집 작성 (독자에게 익숙한 말 기준)
- [ ] 사이트 1회 설정: Search Console·GA4·사이트맵, OGP, 필자 프로필 페이지(ヤン, ひかりちゃん), Ghost 스태프 계정 2개
- [ ] Google Sheets 후보 시트 칸 구성
- [ ] AI 무료 입구 (나중에)
- [ ] 3개월 목표 (한 달 운영 후)
- [x] 1번 blog-collect 완성 (2026-11-19) → 다음: 2번 blog-topic

## 변경 이력
- 2026-11-19 v1: 규칙 1~17 확정
