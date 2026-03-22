from __future__ import annotations

from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import common.knowledge.processor as processor_module
from common.knowledge.processor import DocumentProcessor


def _build_minimal_xlsx_bytes() -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="签约案例" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">
  <si><t>客户名称</t></si>
  <si><t>项目内容</t></si>
  <si><t>石犀科技</t></si>
  <si><t>销售训练系统</t></si>
  <si><t>行业</t></si>
  <si><t>医疗</t></si>
</sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>2</v></c>
      <c r="B2" t="s"><v>3</v></c>
    </row>
    <row r="3">
      <c r="A3" t="s"><v>4</v></c>
      <c r="B3" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>""",
        )

    return buffer.getvalue()


@pytest.mark.asyncio
async def test_parse_xlsx_extracts_sheet_rows(monkeypatch, tmp_path):
    file_path = tmp_path / "sales_cases.xlsx"
    file_path.write_bytes(_build_minimal_xlsx_bytes())

    processor = DocumentProcessor()
    monkeypatch.setattr(processor_module, "ALLOWED_UPLOAD_DIR", str(tmp_path))

    parsed = await processor._parse_document(str(file_path), "xlsx")

    assert parsed is not None
    assert parsed.metrics["sheet_count"] == 1
    assert parsed.metrics["table_row_count"] == 3
    assert parsed.metrics["paragraph_count"] == 0
    assert parsed.warnings == ["[SPREADSHEET_ONLY_CONTENT]"]
    assert [element.element_type for element in parsed.elements] == [
        "table_row",
        "table_row",
        "table_row",
    ]
    assert parsed.elements[0].metadata["sheet_name"] == "签约案例"
    assert parsed.elements[1].text == "石犀科技 | 销售训练系统"
    assert "行业 | 医疗" in parsed.content
