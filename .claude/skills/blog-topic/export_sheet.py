#!/usr/bin/env python3
"""blog-topic: topics/ 순위표를 Google Sheets에 올릴 엑셀(.xlsx) 파일로 바꾼다.

- 순위표 3개(속보 — AI / 속보 — 보안·개발 / 일반 글)의 행을 한 시트에 「구분」 칸으로 나눠 담는다
- 칸 순서는 rules/blog-topic.md 「시트 칸 구성」
- 「선택」 칸은 비워 두고 드롭다운(○)을 건다. 사람이 시트에서 고른다
- 첫 줄 고정, 구분별 행 색, 칸 너비
- 외부 라이브러리 없이 표준 라이브러리(zipfile)로 xlsx를 쓴다. --out이 .csv면 CSV로 쓴다

사용법:
  python3 -I export_sheet.py topics/2026-11-19-pm.md --out "$SP/topics_sheet.xlsx"
"""
import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TABLES = [("속보 AI", "## 속보 순위 — AI"), ("속보 보안·개발", "## 속보 순위 — 보안·개발"), ("일반", "## 일반 글 순위")]
HEAD = ["구분", "선택", "순위", "ID", "가제목", "글 종류", "메인 키워드", "총점", "마감", "1키워드1글",
        "서브 키워드", "전환", "자료부족", "수요", "경험", "수명", "원문 URL", "상세 파일", "선택자", "메모"]
WIDTH = [14, 6, 5, 5, 60, 18, 26, 6, 11, 18, 70, 5, 7, 5, 5, 5, 50, 22, 10, 80]
NUMERIC = {"순위", "총점", "전환", "자료부족", "수요", "경험", "수명"}
STYLE = {"head": 1, "속보 AI": 2, "속보 보안·개발": 3, "일반": 4}  # styles.xml cellXfs 번호
CHOICE = "○"
SCORE_RE = re.compile(r"전환\s*(\d)\s*/\s*자료부족\s*(\d)\s*/\s*수요\s*(\d)\s*/\s*경험\s*(\d)\s*/\s*수명\s*(\d)")


def read_rows(path):
    text = Path(path).read_text(encoding="utf-8")
    details = {}
    for sec in re.split(r"\n(?=### T\d+)", text)[1:]:
        tid = re.match(r"### (T\d+)", sec).group(1)
        details[tid] = dict(re.findall(r"^- ([^:\n]+?):\s*(.*)$", sec.split("\n## ")[0], re.M))
    rows = []
    for label, title in TABLES:
        m = re.search(re.escape(title) + r"[^\n]*\n((?:\|.*\n)+)", text)
        if not m:
            continue
        for r in m.group(1).splitlines()[2:]:
            c = [x.strip() for x in r.strip().strip("|").split("|")]
            if len(c) < 9:
                continue
            _, rank, tid, tt, typ, kw, tot, dl, one = c[:9]
            d = details.get(tid, {})
            s = SCORE_RE.search(d.get("점수", ""))
            scores = list(s.groups()) if s else [""] * 5
            rows.append([label, "", rank, tid, tt, typ, kw, tot, dl, one, d.get("서브 키워드", "")]
                        + scores + [d.get("원문 URL", ""), path, "", d.get("메모", "").replace("**", "")])
    return rows


def col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(ref, v, style, numeric):
    if numeric and re.fullmatch(r"\d+", v):
        return f'<c r="{ref}" s="{style}"><v>{v}</v></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(v)}</t></is></c>'


def write_xlsx(rows, out):
    last = len(rows) + 1
    data = ['<row r="1">' + "".join(cell(f"{col(i)}1", h, STYLE["head"], False) for i, h in enumerate(HEAD)) + "</row>"]
    for n, r in enumerate(rows, start=2):
        st = STYLE.get(r[0], 0)
        data.append(f'<row r="{n}">' + "".join(cell(f"{col(i)}{n}", v, st, HEAD[i] in NUMERIC)
                                               for i, v in enumerate(r)) + "</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(WIDTH))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{''.join(data)}</sheetData>"
        f'<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" '
        f'sqref="B2:B{last}"><formula1>"{CHOICE}"</formula1></dataValidation></dataValidations>'
        "</worksheet>")
    fills = "".join(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{c}"/></patternFill></fill>'
                    for c in ("D9D9D9", "E8F0FE", "FDECEA", "E6F4EA"))
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="10"/><name val="Arial"/></font>'
        '<font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
        f'<fills count="6"><fill><patternFill patternType="none"/></fill>'
        f'<fill><patternFill patternType="gray125"/></fill>{fills}</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1"/></cellXfs>'
        "</styleSheet>")
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>",
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="주제 후보" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>",
        "xl/worksheets/sheet1.xml": sheet,
        "xl/styles.xml": styles,
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            z.writestr(name, body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = read_rows(a.file)
    if a.out.endswith(".csv"):
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([HEAD] + rows)
    else:
        write_xlsx(rows, a.out)
    print(f"rows={len(rows)} -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
