from __future__ import annotations

import json
from io import StringIO
import csv

from curriculum_practice.services.test_bank_importer import TestBankImporter


KNOWN_CATEGORY_ID = "11111111-1111-1111-1111-111111111111"
UNKNOWN_CATEGORY_ID = "22222222-2222-2222-2222-222222222222"


def _row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category_id": KNOWN_CATEGORY_ID,
        "title": "识别客户预算",
        "stem": "客户说预算有限时如何追问？",
        "reference_answer": "先确认预算范围，再澄清优先级。",
        "scoring_criteria": {"dimensions": ["clarity", "structure"]},
        "scoring_dimensions": ["clarity", "structure"],
        "tags": ["discovery", "budget"],
        "difficulty": "medium",
        "department": "sales-enablement",
    }
    payload.update(overrides)
    return payload


def _importer() -> TestBankImporter:
    return TestBankImporter(known_category_ids={KNOWN_CATEGORY_ID})


def test_should_parse_csv_rfc4180_quoted_commas_and_quotes() -> None:
    criteria = json.dumps({"dimensions": ["clarity"]}, ensure_ascii=False)
    rows = [
        [
            "category_id",
            "title",
            "stem",
            "reference_answer",
            "scoring_criteria",
            "scoring_dimensions",
            "tags",
            "difficulty",
            "department",
        ],
        [
            KNOWN_CATEGORY_ID,
            '报价异议, "高级"处理',
            '客户说"太贵了, 再便宜点"时怎么办？',
            '先确认预算, 再解释"价值"。',
            criteria,
            '["clarity"]',
            '["objection","price"]',
            "hard",
            "sales-enablement",
        ],
    ]
    stream = StringIO()
    csv.writer(stream).writerows(rows)
    content = stream.getvalue()

    result = _importer().parse(content.encode(), filename="questions.csv")

    assert result.imported == 1
    assert result.failed == 0
    assert result.items[0].title == '报价异议, "高级"处理'
    assert result.items[0].stem == '客户说"太贵了, 再便宜点"时怎么办？'
    assert result.items[0].reference_answer == '先确认预算, 再解释"价值"。'
    assert result.items[0].tags == ["objection", "price"]


def test_should_parse_jsonl_markdown_content_with_newline_escapes() -> None:
    payload = _row(stem="## 场景\n\n客户：预算不够\n\n请回答。")
    content = json.dumps(payload, ensure_ascii=False) + "\n"

    result = _importer().parse(content.encode(), filename="questions.jsonl")

    assert result.imported == 1
    assert result.failed == 0
    assert result.items[0].stem == "## 场景\n\n客户：预算不够\n\n请回答。"


def test_should_report_missing_required_field() -> None:
    payload = _row(title="")
    content = json.dumps(payload, ensure_ascii=False) + "\n"

    result = _importer().parse(content.encode(), filename="questions.jsonl")

    assert result.imported == 0
    assert result.failed == 1
    assert result.errors[0].row == 1
    assert result.errors[0].field == "title"
    assert "required" in result.errors[0].message


def test_should_report_invalid_difficulty() -> None:
    payload = _row(difficulty="expert")

    result = _importer().parse(
        (json.dumps(payload, ensure_ascii=False) + "\n").encode(),
        filename="questions.jsonl",
    )

    assert result.imported == 0
    assert result.failed == 1
    assert result.errors[0].field == "difficulty"


def test_should_report_unknown_category() -> None:
    payload = _row(category_id=UNKNOWN_CATEGORY_ID)

    result = _importer().parse(
        (json.dumps(payload, ensure_ascii=False) + "\n").encode(),
        filename="questions.jsonl",
    )

    assert result.imported == 0
    assert result.failed == 1
    assert result.errors[0].field == "category_id"
    assert "unknown" in result.errors[0].message


def test_should_report_invalid_scoring_criteria_and_dimensions() -> None:
    payload = _row(
        scoring_criteria={"dimensions": []},
        scoring_dimensions=["clarity"],
    )

    result = _importer().parse(
        (json.dumps(payload, ensure_ascii=False) + "\n").encode(),
        filename="questions.jsonl",
    )

    assert result.imported == 0
    assert result.failed == 1
    assert result.errors[0].field == "scoring_criteria"


def test_should_report_mixed_valid_and_invalid_rows() -> None:
    content = "\n".join(
        [
            json.dumps(_row(title="有效题目"), ensure_ascii=False),
            json.dumps(_row(difficulty="invalid"), ensure_ascii=False),
            json.dumps(_row(category_id=UNKNOWN_CATEGORY_ID), ensure_ascii=False),
        ]
    )

    result = _importer().parse(content.encode(), filename="questions.jsonl")

    assert result.imported == 1
    assert result.failed == 2
    assert [error.row for error in result.errors] == [2, 3]
    assert result.items[0].title == "有效题目"
