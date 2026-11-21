#!/usr/bin/env python3
"""blog-distribute: 회차(아침·저녁)별 SNS 문안을 공유 드라이브에 올릴 시트(.xlsx)로 (D74, D76)

- 회차마다 1장 「BlogAgent SNS 문안 YYYY-MM-DD 아침|저녁」, 한 행 = 글 1편 × 플랫폼 1곳, 글 발행 순 → 플랫폼 순
- 사람은 ✋ 행(X·note)을 붙여 넣은 뒤 「게시 주소」 칸에 주소를 적는다 → 「다 올렸어 아침」으로 에이전트가 읽어 기록
- 첫 줄 안내 → 칸 이름(필터) → 행. 플랫폼별로 볼 때는 필터를 쓴다
- 보기용. 원본은 글별 sns.md, 시트를 고쳐도 반영되지 않는다 (고칠 것은 「메모」 칸이나 대화로)
- 외부 라이브러리 없이 표준 라이브러리로 (blog-topic export_sheet.py의 칸 함수를 같이 쓴다)

사용법:
  python3 -I sns_sheet.py 2026-11-21 --slot 아침 --out "$SP/sns_sheet.xlsx"
  python3 -I sns_sheet.py 2026-11-21 --slot 아침 --sns F --card F [--sns F --card F …] --out F   # 시험
"""
import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blog-topic"))
from sns_common import PLATFORMS, EXTRA, SLOTS, parse_sns, front, hero_url  # noqa: E402
from sns_digest import NAMES, status, entries_for, parse_date  # noqa: E402
from check_sns import x_weight  # noqa: E402
from export_sheet import col, cell  # noqa: E402

HEAD = ["발행", "제목", "slug", "플랫폼", "切り口", "게시", "상태", "본문", "링크·답글", "대표 이미지", "글자 수", "게시 주소", "메모"]
WIDTH = [7, 40, 26, 18, 10, 10, 30, 80, 50, 30, 9, 40, 40]
ST = HEAD.index("상태")
NOTE = ("① 읽기 → ② 대화로 「올려 {slot}」: ⏳(Threads·Facebook·LinkedIn)를 에이전트가 올립니다 → "
        "③ ✋(X·note)는 본문을 복사해 붙여 넣고 대표 이미지를 첨부, 올린 주소를 「게시 주소」 칸에 → ④ 「다 올렸어 {slot}」. "
        "문안은 보기용(원본은 로컬 sns.md) — 고칠 것은 「메모」 칸이나 대화로.")
STYLE = {"✅": 3, "⏳": 4, "✋": 5, "❌": 6}   # cellXfs 번호 (아래 styles)


def rows_for(items):
    out = []
    for when, slug, card, sns in items:
        c = front(card.read_text())
        if not sns.exists():
            out.append([when[11:16], "", slug, "", "", "", "문안 없음", "", "", "", "", "", ""])
            continue
        text = sns.read_text()
        head, posts = parse_sns(text)
        rec = sns.parent / "sns_posted.json"
        done = json.loads(rec.read_text()) if rec.exists() else {}
        title = next((ln[len("# SNS 문안: "):] for ln in text.splitlines() if ln.startswith("# SNS 문안: ")), slug)
        for p in PLATFORMS:
            secs = posts.get(p, {})
            body = secs.get("本文", "")
            if p == "note" and secs.get("タイトル"):
                body = f"【タイトル】{secs['タイトル']}\n\n{body}"
            extra = secs.get(EXTRA[p][0], "") if p in EXTRA else ""
            img = (hero_url(sns, head) or "(대표 이미지 주소 없음 — blog-publish 업로드 확인)") if p in ("x", "note") else ""
            mark, desc = status(p, done)
            n = f"{x_weight(body)}/280" if p == "x" else str(len(secs.get("本文", "")))
            r = done.get(p) or {}
            out.append([when[11:16], title, slug, NAMES[p], secs.get("切り口", ""), "✋ 사람" if p in ("x", "note") else "자동",
                        f"{mark} {desc}", body, extra, img, n, r.get("url", "") if not r.get("error") else "", ""])
    return out


def write_xlsx(rows, out, date, slot=""):
    last = len(rows) + 2
    data = [f'<row r="1">{cell("A1", NOTE.format(slot=slot), 1, False)}</row>',
            '<row r="2">' + "".join(cell(f"{col(i)}2", h, 2, False) for i, h in enumerate(HEAD)) + "</row>"]
    for n, r in enumerate(rows, start=3):
        st = STYLE.get(r[ST][:1], 0)
        data.append(f'<row r="{n}">' + "".join(cell(f"{col(i)}{n}", v, st if i == ST else 7, False)
                                               for i, v in enumerate(r)) + "</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(WIDTH))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="2" topLeftCell="A3" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             f"<cols>{cols}</cols><sheetData>{''.join(data)}</sheetData>"
             f'<autoFilter ref="A2:{col(len(HEAD) - 1)}{last}"/></worksheet>')
    colors = ("D9D9D9", "E6F4EA", "E8F0FE", "FFF4E5", "FDECEA")   # 칸 이름, ✅, ⏳, ✋, ❌
    fills = "".join(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{c}"/></patternFill></fill>' for c in colors)
    al = '<alignment vertical="top" wrapText="1"/>'

    def xf(fill, font, wrap=True):
        return (f'<xf numFmtId="0" fontId="{font}" fillId="{fill}" borderId="0" xfId="0" applyFont="1" applyFill="1"'
                + (f' applyAlignment="1">{al}</xf>' if wrap else "/>"))
    # 0 기본, 1 안내(굵게), 2 칸 이름, 3~6 상태 색, 7 본문(줄바꿈)
    xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>', xf(0, 1, False), xf(2, 1),
           xf(3, 0), xf(4, 0), xf(5, 0), xf(6, 0), xf(0, 0)]
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
              f'<fills count="{2 + len(colors)}"><fill><patternFill patternType="none"/></fill>'
              f'<fill><patternFill patternType="gray125"/></fill>{fills}</fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs></styleSheet>')
    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{ct}.sheet.main+xml"/>'
            f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{ct}.worksheet+xml"/>'
            f'<Override PartName="/xl/styles.xml" ContentType="{ct}.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{rel}">'
            f'<sheets><sheet name="SNS {date} {slot}" sheetId="1" r:id="rId1"/></sheets>'
            '<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'
            f"'SNS {date} {slot}'!$A$2:${col(len(HEAD) - 1)}${last}</definedName></definedNames></workbook>",
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{rel}/styles" Target="styles.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
        "xl/styles.xml": styles,
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            z.writestr(name, body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?")
    ap.add_argument("--slot", choices=SLOTS, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--sns", action="append"); ap.add_argument("--card", action="append")
    a = ap.parse_args()
    date = parse_date(a.date)
    if a.sns and a.card:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        items = [(now, Path(c).stem, Path(c), Path(f)) for f, c in zip(a.sns, a.card)]
    else:
        items = entries_for(Path(a.root), date, a.slot)
    rows = rows_for(items)
    write_xlsx(rows, a.out, date, a.slot)
    print(f"{len(items)}편 · {len(rows)}행 → {a.out}  (Drive 제목: BlogAgent SNS 문안 {date} {a.slot})")


if __name__ == "__main__":
    main()
