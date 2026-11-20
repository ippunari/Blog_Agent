---
name: blog-status
description: BlogAgent 진행 현황. briefs/ 주제 카드를 읽어 slug·경로·상태·마감·조사 노트/초안/대조 보고서 유무를 표 하나로 보여 준다. 읽기만 하고 아무 파일도 바꾸지 않는다. "현황", "진행 상황", "blog-status", "어디까지 했어" 요청 때 쓴다.
argument-hint: "[--all]"
---

# blog-status (진행 현황)

## 하는 일
```bash
python3 -I .claude/skills/blog-status/status.py        # 진행 중 카드 표 + 상태별 건수
python3 -I .claude/skills/blog-status/status.py --all  # 발행 완료·중단 목록도
```
- 결과 표를 **그대로** 사용자에게 보여 준다. 정렬은 속보 먼저 → 마감 가까운 순 → 선택 순 (blog-research가 다음에 고를 순서와 같다)
- 마감: `⚠지남`, `⚠N시간 남음`(12시간 미만), `(시각 미확인)` 표시
- 노트·초안·대조 칸: 같은 slug의 `research/`·`drafts/`·`factcheck/` 파일이 맨 위 폴더에 있으면 ✓
- 출처 칸: `시트`(시트에서 고름) / `직접`(blog-topic 직접 모드). `origin:`이 없는 예전 카드는 `시트`
- 「카드 없이 남은 조사 노트」 경고가 나오면 정리가 빠진 것이다 — 사람에게 알리고, 옮기는 것은 사람의 확인을 받은 뒤

## 표 다음에 덧붙일 것 (한국어, 짧게)
- 마감이 지났거나 12시간 미만인 속보 → 「먼저 처리할 것」
- 다음에 할 일 1줄 (예: 「조사 대기 맨 위: `/blog-research wordpress-715-security-update`」)

## 하지 않는 것
- 카드·노트를 고치거나 옮기기 (상태는 각 단계 스킬이 바꾼다, BlogAgent.md 「주제 카드의 상태와 정리」)
