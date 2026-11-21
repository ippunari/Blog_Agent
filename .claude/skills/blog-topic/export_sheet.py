#!/usr/bin/env python3
"""blog-topic: topics/ 순위표를 Google Sheets에 올릴 엑셀(.xlsx) 파일로 바꾼다.

- 맨 위 안내 1줄 → 칸 이름 → 추천 행(○, 굵게) → 다른 후보(구분마다 최대 3개, 「이월」 표시)
- 아침·저녁 모두 속보 AI / 속보 보안·개발 / 깊이 새 글 (D72)
- 칸 순서는 rules/blog-topic.md 「시트」
- 「선택」 칸에 드롭다운(○)을 건다. 추천은 ○가 들어 있고 사람은 옮기기만 한다
- 외부 라이브러리 없이 표준 라이브러리(zipfile)로 xlsx를 쓴다. --out이 .csv면 CSV로 쓴다

사용법:
  python3 -I export_sheet.py topics/2026-11-20-am.md --out "$SP/topics_sheet.xlsx"
"""
import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TABLES_AM = [("속보 AI", "## 속보 순위 — AI"), ("속보 보안·개발", "## 속보 순위 — 보안·개발"),
             ("깊이 새 글", "## 깊이 새 글 순위")]   # 아침·저녁 같은 3표, 개편 없음 (D72)
TABLES_PM = TABLES_AM
HEAD = ["구분", "선택", "대표 한마디", "추천 이유", "가제목", "마감", "실습", "글 종류", "메인 키워드", "총점", "이월", "ID",
        "1키워드1글", "서브 키워드", "전환", "자료부족", "수요", "경험", "수명", "원문 URL", "상세 파일", "선택자", "메모"]
WIDTH = [14, 6, 30, 40, 60, 11, 14, 18, 26, 6, 24, 5, 18, 70, 5, 7, 5, 5, 5, 50, 22, 10, 80]
NUMERIC = {"총점", "전환", "자료부족", "수요", "경험", "수명"}
NOTE = ("보기용 기록입니다 — 추천 ○ 주제는 이미 주제 카드가 만들어졌습니다(확인 없이 진행, D67). 시트를 고쳐도 반영되지 않습니다. "
        "바꾸려면 대화로 「select T05」(다른 후보 추가)·「중단 <slug>」, 대표 한마디도 대화로 알려 주세요.")
OTHERS = 3  # 구분마다 보여 줄 다른 후보 수
CHOICE = "○"
SCORE_RE = re.compile(r"전환\s*(\d)\s*/\s*자료부족\s*(\d)\s*/\s*수요\s*(\d)\s*/\s*경험\s*(\d)\s*/\s*수명\s*(\d)")
# styles.xml cellXfs 번호: 0 기본, 1 칸 이름, 2~5 구분 색, 6 안내, 7~10 구분 색 + 굵게(추천 행)
FILL = {"속보 AI": 2, "속보 보안·개발": 3, "깊이 새 글": 4, "깊이 개편": 5}
HEAD_STYLE, NOTE_STYLE, BOLD = 1, 6, 5


def read_rows(path):
    """반환: (추천 행 목록, 다른 후보 행 목록)"""
    text = Path(path).read_text(encoding="utf-8")
    slot = re.search(r"^slot:\s*(\w+)", text, re.M)
    tables = TABLES_PM if slot and slot.group(1) == "pm" else TABLES_AM
    details = {}
    for sec in re.split(r"\n(?=### T\d+)", text)[1:]:
        tid = re.match(r"### (T\d+)", sec).group(1)
        details[tid] = dict(re.findall(r"^- ([^:\n]+?):\s*(.*)$", sec.split("\n## ")[0], re.M))
    rec, others = [], []
    for label, title in tables:
        m = re.search(re.escape(title) + r"[^\n]*\n((?:\|.*\n)+)", text)
        if not m:
            continue
        n_other = 0
        for r in m.group(1).splitlines()[2:]:
            c = [x.strip() for x in r.strip().strip("|").split("|")]
            if len(c) < 10:
                continue
            mark, _, tid, tt, typ, kw, tot, dl, one, carry = c[:10]
            d = details.get(tid, {})
            sc = SCORE_RE.search(d.get("점수", ""))
            scores = list(sc.groups()) if sc else [""] * 5
            carry_txt = "-" if carry == "-" else "이월(" + carry.replace("topics/", "").replace(".md", "") + ")"
            chosen = mark in ("○", "☑")
            row = ([label, CHOICE if chosen else "", "", d.get("추천", "") if chosen else "", tt, dl, d.get("실습", ""),
                    typ, kw, tot, carry_txt, tid, one, d.get("서브 키워드", "")] + scores
                   + [d.get("원문 URL", ""), path, "", d.get("메모", "").replace("**", "")])
            if chosen:
                rec.append(row)
            elif n_other < OTHERS:
                others.append(row)
                n_other += 1
    return rec, others


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


def write_xlsx(rec, others, out):
    rows = rec + others
    last = len(rows) + 2
    data = [f'<row r="1">{cell("A1", NOTE, NOTE_STYLE, False)}</row>',
            '<row r="2">' + "".join(cell(f"{col(i)}2", h, HEAD_STYLE, False) for i, h in enumerate(HEAD)) + "</row>"]
    for n, r in enumerate(rows, start=3):
        st = FILL.get(r[0], 0) + (BOLD if n - 3 < len(rec) else 0)
        data.append(f'<row r="{n}">' + "".join(cell(f"{col(i)}{n}", v, st, HEAD[i] in NUMERIC)
                                               for i, v in enumerate(r)) + "</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(WIDTH))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="2" topLeftCell="A3" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{''.join(data)}</sheetData>"
        f'<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" '
        f'sqref="B3:B{last}"><formula1>"{CHOICE}"</formula1></dataValidation></dataValidations>'
        "</worksheet>")
    colors = ("D9D9D9", "E8F0FE", "FDECEA", "E6F4EA", "FFF4E5")  # 칸 이름, 속보 AI, 보안·개발, 새 글, 개편
    fills = "".join(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{c}"/></patternFill></fill>'
                    for c in colors)

    def xf(fill, font):
        return (f'<xf numFmtId="0" fontId="{font}" fillId="{fill}" borderId="0" xfId="0" '
                'applyFont="1" applyFill="1"/>')
    # fillId: 0 없음, 1 gray125, 2~6 = colors 순서
    xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>', xf(2, 1),
           xf(3, 0), xf(4, 0), xf(5, 0), xf(6, 0), xf(0, 1),
           xf(3, 1), xf(4, 1), xf(5, 1), xf(6, 1)]
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="10"/><name val="Arial"/></font>'
        '<font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
        f'<fills count="{2 + len(colors)}"><fill><patternFill patternType="none"/></fill>'
        f'<fill><patternFill patternType="gray125"/></fill>{fills}</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs>'
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
    rec, others = read_rows(a.file)
    if a.out.endswith(".csv"):
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([HEAD] + rec + others)
    else:
        write_xlsx(rec, others, a.out)
    print(f"추천={len(rec)} 다른 후보={len(others)} -> {a.out}")


if __name__ == "__main__":
    sys.exit(main())
