# yomiyasu (외부 도구, 판 고정)

- 출처: https://github.com/nanaism/yomiyasu (MIT — `LICENSE`, Unicode 데이터 — `UNICODE-LICENSE.txt`)
- 판: v3.4.1 · commit `da57eccea63b94bbd07c5f09bc93d948a7b6a180` (2026-11-25)
- 가져온 것: `skills/yomiyasu/scripts/`의 `yomiyasu_lint.py`·`yomiyasu_diff.py`·`markdown_visibility.py`만 (고치지 않음). 지시문(SKILL.md)·`yomiyasu_check.py`(기록을 씀)·`yomiyasu_hook.py`는 가져오지 않았다
- 안전 점검 (2026-11-28): 표준 라이브러리만. 인터넷·다른 프로그램 실행·파일 쓰기 없음. 동적 import는 옆의 markdown_visibility.py만
- 쓰는 곳: `../../check_polish.py` (lint는 본문 사본을 표준 입력으로, diff는 `--meaning-diff`) — D101
- 판을 올릴 때: 새 판의 같은 3개 파일을 다시 안전 점검 → 이 파일의 판·commit을 고치고 → 우리 초안 2편으로 시험 → decisions.md에 기록
