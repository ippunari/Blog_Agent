#!/usr/bin/env python3
"""blog-topic: 속보 마감 계산 (D88).

- 기본 마감 = 원래 공표 일시 + 72시간
- 그 시각이 업무 시간(평일 9~18시 JST, 일본 공휴일 제외) 밖이면 → 그 뒤 첫 업무일 12:00
  (사람이 Ghost 초안 미리보기를 보고 발행할 수 있는 시각이어야 한다 — 철칙 2·D62)
- work_hours_left(now, deadline): 지금부터 마감까지 남은 업무 시간(시간). 추천은 3시간 이상 (6시간 규칙을 바꿈)

사용법:
  python3 -I deadline.py "2026-11-26 03:54"            → 마감
  python3 -I deadline.py "2026-11-26 03:54" --now "2026-11-28 00:20"  → 마감 + 남은 업무 시간
python3 -I deadline.py --carry topics --now "2026-11-30 08:00"  → 깊이 이월로 볼 topics 파일 (최근 5 업무일, D92)
blog-research·check_topics.py도 이 파일을 쓴다 (마감·업무일 계산은 한 곳에서)
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
WORK_START, WORK_END, NOON = 9, 18, 12
CARRY_WORKDAYS = 5      # 깊이 이월: 순위표 날짜 다음 날부터 오늘까지 업무일이 이 수 이하 (D92)
NEED_HOURS = 3          # 추천에 필요한 남은 업무 시간 (잠정 — 운영하며 실제로 재서 고친다, D88)
# 일본 공휴일 (内閣府 「国民の祝日」). blog-publish/build_publish.py JP_HOLIDAYS와 같은 목록 — 둘 다 고친다
JP_HOLIDAYS = {
    "2026-01-01", "2026-01-12", "2026-02-11", "2026-02-23", "2026-03-20", "2026-04-29", "2026-05-03", "2026-05-04",
    "2026-05-05", "2026-05-06", "2026-07-20", "2026-08-11", "2026-09-21", "2026-09-22", "2026-09-23", "2026-10-12",
    "2026-11-03", "2026-11-23",
    "2027-01-01", "2027-01-11", "2027-02-11", "2027-02-23", "2027-03-21", "2027-03-22", "2027-04-29", "2027-05-03",
    "2027-05-04", "2027-05-05", "2027-07-19", "2027-08-11", "2027-09-20", "2027-09-23", "2027-10-11", "2027-11-03",
    "2027-11-23",
}


def parse(s):
    """「2026-11-26 03:54」「2026-11-26T03:54+09:00」「2026-11-26」(0시) → JST datetime"""
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?", s)
    if not m:
        raise ValueError(f"날짜 형식이 아님: {s}")
    y, mo, d, h, mi = m.groups()
    return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=JST)


def is_workday(d):
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in JP_HOLIDAYS


def in_work_hours(t):
    t = t.astimezone(JST)
    return is_workday(t) and WORK_START <= t.hour + t.minute / 60 < WORK_END


def deadline(published):
    """원래 공표 일시 → 마감. 반환 (마감, 연장했나)"""
    base = (parse(published) if isinstance(published, str) else published) + timedelta(hours=72)
    if in_work_hours(base):
        return base, False
    d = base.replace(hour=NOON, minute=0, second=0, microsecond=0)
    if d <= base or not is_workday(d):
        d += timedelta(days=1)
        while not is_workday(d):
            d += timedelta(days=1)
    return d, True


def work_hours_left(now, dl):
    """now부터 dl까지 업무 시간(시간, 소수)"""
    now, dl = now.astimezone(JST), dl.astimezone(JST)
    total, day = 0.0, now.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < dl:
        if is_workday(day):
            s = max(now, day.replace(hour=WORK_START))
            e = min(dl, day.replace(hour=WORK_END))
            if e > s:
                total += (e - s).total_seconds() / 3600
        day += timedelta(days=1)
    return total


def workdays_since(d, now):
    """d(날짜) 다음 날부터 now 날짜까지의 업무일 수"""
    d, now = d.astimezone(JST).date(), now.astimezone(JST).date()
    n, cur = 0, d + timedelta(days=1)
    while cur <= now:
        if cur.weekday() < 5 and cur.strftime("%Y-%m-%d") not in JP_HOLIDAYS:
            n += 1
        cur += timedelta(days=1)
    return n


def carry_files(topics_dir, now, limit=CARRY_WORKDAYS):
    """깊이 이월로 볼 topics 파일 (YYYY-MM-DD-am|pm.md, 최근 limit 업무일, 오래된 순)"""
    out = []
    for f in sorted(os.listdir(topics_dir)):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(am|pm)\.md", f)
        if m and workdays_since(parse(m.group(1)), now) <= limit:
            out.append(os.path.join(topics_dir, f))
    return out


def holiday_years():
    return {h[:4] for h in JP_HOLIDAYS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("published", nargs="?", help="원래 공표 일시 (JST) 예: 2026-11-26 03:54")
    ap.add_argument("--now", help="지금 시각 (생략하면 현재)")
    ap.add_argument("--carry", metavar="TOPICS_DIR", help="깊이 이월로 볼 topics 파일 목록 (최근 5 업무일, D92)")
    a = ap.parse_args()
    if a.carry:
        now = parse(a.now) if a.now else datetime.now(JST)
        for f in carry_files(a.carry, now):
            print(f)
        return
    if not a.published:
        ap.error("공표 일시 또는 --carry가 필요하다")
    if not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}", a.published):
        sys.exit("오류: 공표 시각이 없음 — 날짜만이면 「확인된 가장 늦은 시각」(그날 공표가 있었다는 가장 이른 흔적: "
                 "문서 갱신 시각·첫 보도 시각, 없으면 그날 23:59 발표 회사 시간대)을 JST로 바꿔 넣는다 (D94)")
    dl, ext = deadline(a.published)
    now = parse(a.now) if a.now else datetime.now(JST)
    if str(dl.year) not in holiday_years():
        print(f"경고: {dl.year}년 일본 공휴일이 JP_HOLIDAYS에 없음 — 목록을 더한다", file=sys.stderr)
    left = work_hours_left(now, dl)
    print(f"마감: {dl.isoformat(timespec='minutes')}" + (" (업무 시간 밖이라 연장, D88)" if ext else ""))
    print(f"남은 업무 시간: {left:.1f}시간" + ("" if left >= NEED_HOURS else f" — {NEED_HOURS}시간 미만: 추천하지 않는다"))


if __name__ == "__main__":
    main()
