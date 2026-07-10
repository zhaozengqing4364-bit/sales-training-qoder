from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from sales_trainer.schemas import (
    CustomerFaqCard,
    CustomerFaqDuplicateGroup,
    CustomerFaqEvidenceCase,
    CustomerFaqImportParseResponse,
)

QUESTION_RE: Final = re.compile(r"^(?P<number>\d+)\.\s*问题：(?P<question>.+?)\s*$")
SCENARIO_RE: Final = re.compile(
    r"^场景[一二三四五六七八九十\d]+[:：](?P<scenario>.+?)\s*$"
)
DETAIL_PREFIX: Final = "详细答案："

CASE_NAMES: Final = (
    "深圳航空",
    "深航空",
    "劲牌集团",
    "汕头大学",
    "华中农业大学",
    "深圳市大数据资源管理中心",
    "罗湖政数局",
    "广州海事法院",
    "深圳市慢性病防治中心",
    "深智城",
    "广汽",
    "华盛证券",
    "招商前海湾",
    "南昌住建局",
    "广东信丰物流",
    "江门妇幼",
    "龙华区中心医院",
    "南山医疗集团",
    "宝安区人民医院",
    "招联金融",
    "深圳大学城",
    "百佳华集团",
)

DUPLICATE_GROUP_SPECS: Final = (
    (
        "waf_boundary",
        "WAF 与石犀边界",
        (10, 23),
        "两题均解释石犀与传统 WAF 的协同关系。",
    ),
    (
        "captcha_vip",
        "验证码/VIP 兼容问题",
        (46, 61),
        "两题均讨论代理模式下验证码加载失败。",
    ),
    (
        "sql_injection",
        "SQL 注入检测",
        (48, 69),
        "两题均讨论 API 请求中的 SQL 注入识别。",
    ),
    (
        "inactive_api",
        "失活 API 识别",
        (27, 72),
        "两题均讨论长期无访问 API 的识别与清理。",
    ),
    ("multi_cloud", "多云统一治理", (35, 74, 92), "多题均讨论多云/跨云管理。"),
    ("logistics_pii", "物流个人信息保护", (44, 65), "两题均讨论物流行业敏感信息保护。"),
    ("university_library", "高校图书馆", (41, 62), "两题均讨论高校图书馆系统治理。"),
    ("ransomware", "勒索防护", (33, 77), "两题均讨论通过 API 暴露面收缩辅助勒索防护。"),
)

HIGH_RISK_KEYWORDS: Final = (
    "价格",
    "报价",
    "50Gbps",
    "10Gbps",
    "50万QPS",
    "QPS",
    "5090",
    "准确率超91%",
    "3分钟",
    "版本",
    "路线",
    "自动IP封禁",
    "SDK",
    "TLS 1.3",
    "降级",
    "毫秒级",
    "<1ms",
)


@dataclass(frozen=True, slots=True)
class _RawQuestion:
    number: int
    scenario: str
    question: str
    answer: str


def parse_customer_faq_material(raw_text: str) -> CustomerFaqImportParseResponse:
    questions = _extract_questions(raw_text)
    duplicate_lookup = _duplicate_lookup()
    cards = [
        _card_from_question(item, duplicate_group_key=duplicate_lookup.get(item.number))
        for item in questions
    ]
    duplicate_groups: list[CustomerFaqDuplicateGroup] = []
    for group_key, title, numbers, reason in DUPLICATE_GROUP_SPECS:
        card_keys = [
            _card_key(number)
            for number in numbers
            if any(card.source_question_number == number for card in cards)
        ]
        if len(card_keys) < 2:
            continue
        duplicate_groups.append(
            CustomerFaqDuplicateGroup(
                group_key=group_key,
                title=title,
                card_keys=card_keys,
                reason=reason,
            )
        )
    evidence_cases = _evidence_cases(cards)
    high_risk_count = sum(1 for card in cards if card.difficulty_level == "high_risk")
    escalation_count = sum(1 for card in cards if card.escalation_required)
    return CustomerFaqImportParseResponse(
        cards=cards,
        duplicate_groups=duplicate_groups,
        evidence_cases=evidence_cases,
        total_questions=len(cards),
        high_risk_count=high_risk_count,
        escalation_count=escalation_count,
    )


def _extract_questions(raw_text: str) -> list[_RawQuestion]:
    current_scenario = "未分组"
    current_number: int | None = None
    current_question: str | None = None
    current_answer_lines: list[str] = []
    result: list[_RawQuestion] = []

    def flush() -> None:
        nonlocal current_number, current_question, current_answer_lines
        if current_number is None or current_question is None:
            return
        answer = "\n".join(current_answer_lines).strip()
        if answer.startswith(DETAIL_PREFIX):
            answer = answer[len(DETAIL_PREFIX) :].strip()
        if answer:
            result.append(
                _RawQuestion(
                    number=current_number,
                    scenario=current_scenario,
                    question=current_question.strip(),
                    answer=answer,
                )
            )
        current_number = None
        current_question = None
        current_answer_lines = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        scenario_match = SCENARIO_RE.match(line)
        if scenario_match:
            flush()
            current_scenario = scenario_match.group("scenario").strip()
            continue
        question_match = QUESTION_RE.match(line)
        if question_match:
            flush()
            current_number = int(question_match.group("number"))
            current_question = question_match.group("question")
            current_answer_lines = []
            continue
        if current_number is not None:
            current_answer_lines.append(line)
    flush()
    return result


def _card_from_question(
    item: _RawQuestion,
    *,
    duplicate_group_key: str | None,
) -> CustomerFaqCard:
    category = _category_for(item.question, item.answer)
    escalation_required = _requires_escalation(item.question, item.answer)
    difficulty_level = (
        "high_risk"
        if escalation_required
        else (
            "advanced"
            if category in {"部署架构", "交付问题", "技术限制"}
            else "newcomer"
        )
    )
    key_points = _key_points(item.answer)
    evidence_cases = _cases_in_text(item.answer)
    return CustomerFaqCard(
        card_key=_card_key(item.number),
        source_question_number=item.number,
        question=item.question,
        short_answer=_short_answer(item.answer),
        detailed_answer=item.answer,
        scenario=item.scenario,
        category=category,
        customer_intent=_customer_intent(category),
        key_points=key_points,
        evidence_cases=evidence_cases,
        forbidden_claims=_forbidden_claims(
            item.question, item.answer, escalation_required
        ),
        escalation_required=escalation_required,
        difficulty_level=difficulty_level,
        tags=_tags(item.question, item.answer, category, escalation_required),
        duplicate_group_key=duplicate_group_key,
        status="published",
    )


def _card_key(number: int) -> str:
    return f"customer_faq_q{number:03d}"


def _duplicate_lookup() -> dict[int, str]:
    result: dict[int, str] = {}
    for group_key, _, numbers, _ in DUPLICATE_GROUP_SPECS:
        for number in numbers:
            result[number] = group_key
    return result


def _category_for(question: str, answer: str) -> str:
    text = f"{question}\n{answer}"
    if any(keyword in text for keyword in ("价格", "报价", "授权续期")):
        return "商务政策"
    if any(
        keyword in text
        for keyword in ("部署", "镜像", "代理", "K8S", "容器", "多云", "QinQ", "TLS")
    ):
        return "部署架构"
    if any(keyword in text for keyword in ("WAF", "竞品", "替代")):
        return "竞品关系"
    if any(
        keyword in text
        for keyword in ("政府", "医疗", "金融", "高校", "物流", "证券", "医院", "教育")
    ):
        return "行业案例"
    if any(
        keyword in text for keyword in ("POC", "测试", "交付", "升级", "报告", "续期")
    ):
        return "交付问题"
    if any(
        keyword in text
        for keyword in ("SQL", "DDoS", "SDK", "验证码", "IP", "User-Agent")
    ):
        return "技术限制"
    if any(
        keyword in text
        for keyword in ("合规", "审计", "等保", "数据安全法", "个人信息保护法")
    ):
        return "合规审计"
    return "产品能力"


def _requires_escalation(question: str, answer: str) -> bool:
    text = f"{question}\n{answer}"
    return any(keyword in text for keyword in HIGH_RISK_KEYWORDS)


def _short_answer(answer: str) -> str:
    normalized = re.sub(r"\s+", " ", answer).strip()
    for separator in ("。", "；", ";"):
        if separator in normalized:
            first = normalized.split(separator, 1)[0].strip()
            if len(first) >= 20:
                return f"{first}{separator}"
    return normalized[:220]


def _key_points(answer: str) -> list[str]:
    points: list[str] = []
    for line in answer.splitlines():
        normalized = line.strip().lstrip("⦁·- ").strip()
        if (
            not normalized
            or normalized.startswith("例如")
            or normalized.startswith("案例")
        ):
            continue
        if "：" in normalized:
            normalized = normalized.split("：", 1)[0].strip()
        if normalized and normalized not in points:
            points.append(normalized[:120])
        if len(points) >= 5:
            break
    if points:
        return points
    return [_short_answer(answer).rstrip("。；;")]


def _cases_in_text(text: str) -> list[str]:
    cases: list[str] = []
    for case_name in CASE_NAMES:
        if case_name in text and case_name not in cases:
            cases.append(case_name)
    return cases


def _forbidden_claims(
    question: str, answer: str, escalation_required: bool
) -> list[str]:
    claims = ["不得把历史案例效果直接承诺给当前客户。"]
    text = f"{question}\n{answer}"
    if "价格" in text or "报价" in text:
        claims.append("不得给出固定价格或折扣承诺，需按项目范围正式报价。")
    if any(keyword in text for keyword in ("QPS", "Gbps", "毫秒", "<1ms", "50万")):
        claims.append("不得承诺固定性能指标，需以客户环境压测结果为准。")
    if any(keyword in text for keyword in ("版本", "路线", "SDK", "TLS")):
        claims.append("不得承诺未确认的版本路线、SDK 或协议兼容能力。")
    if escalation_required:
        claims.append("遇到客户追问落地细节时，应升级售前或技术确认。")
    return list(dict.fromkeys(claims))


def _tags(
    question: str, answer: str, category: str, escalation_required: bool
) -> list[str]:
    text = f"{question}\n{answer}"
    tags = [category]
    for keyword in (
        "API",
        "WAF",
        "镜像",
        "代理",
        "信创",
        "护网",
        "分类分级",
        "医疗",
        "政府",
        "金融",
        "教育",
        "物流",
        "POC",
        "DLP",
        "SIEM",
    ):
        if keyword in text and keyword not in tags:
            tags.append(keyword)
    if escalation_required:
        tags.append("需售前确认")
    return tags[:10]


def _customer_intent(category: str) -> str:
    mapping = {
        "商务政策": "客户想确认预算、采购边界和推进方式。",
        "部署架构": "客户担心部署复杂度、稳定性和现网影响。",
        "竞品关系": "客户想判断石犀和既有安全设备的边界。",
        "行业案例": "客户需要同类行业证据来降低决策风险。",
        "交付问题": "客户关注 POC、上线、升级和运维成本。",
        "技术限制": "客户在确认具体能力边界和限制条件。",
        "合规审计": "客户想知道能否支撑监管、等保和审计材料。",
    }
    return mapping.get(category, "客户想快速理解产品能解决什么问题。")


def _evidence_cases(cards: list[CustomerFaqCard]) -> list[CustomerFaqEvidenceCase]:
    case_questions: dict[str, list[int]] = {}
    for card in cards:
        if card.source_question_number is None:
            continue
        for case_name in card.evidence_cases:
            case_questions.setdefault(case_name, []).append(card.source_question_number)
    return [
        CustomerFaqEvidenceCase(
            case_key=_normalize_case_key(case_name),
            title=case_name,
            summary=f"材料中用于支撑客户问答口径的{case_name}案例。",
            source_question_numbers=sorted(set(numbers)),
        )
        for case_name, numbers in sorted(case_questions.items())
    ]


def _normalize_case_key(case_name: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", case_name).strip("_")
    return value or "case"
