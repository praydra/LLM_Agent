from __future__ import annotations

import re

from .schema import RouteResult, ToolCall


DOCUMENT_KEYWORDS = {
    "표준",
    "표준서",
    "작업표준",
    "매뉴얼",
    "절차",
    "기준",
    "조치",
    "원인",
    "설명",
    "방법",
    "보류",
    "재작업",
    "출하",
    "정비",
    "예방보전",
    "점검",
    "권한",
    "감사",
    "sop",
    "manual",
}

DATA_KEYWORDS = {
    "lot",
    "로트",
    "이력",
    "생산",
    "수량",
    "실적",
    "불량",
    "불량률",
    "품질",
    "설비",
    "알람",
    "비가동",
    "현황",
    "조회",
    "재고",
    "자재",
    "창고",
    "입고",
    "출고",
}


class QuestionRouter:
    """Rule-based MVP router for manufacturing questions."""

    def classify(self, question: str) -> RouteResult:
        normalized = question.lower()
        has_doc_signal = any(keyword in normalized for keyword in DOCUMENT_KEYWORDS)
        has_data_signal = any(keyword in normalized for keyword in DATA_KEYWORDS)

        tool_calls = self._infer_tool_calls(question)
        if tool_calls:
            has_data_signal = True

        if has_doc_signal and has_data_signal:
            route = "hybrid"
        elif has_data_signal:
            route = "data"
        else:
            route = "document"

        reasons = []
        if has_doc_signal:
            reasons.append("업무 기준, 표준서, 매뉴얼 또는 조치 설명이 필요합니다.")
        if has_data_signal:
            reasons.append("생산, 품질, LOT, 설비 등 정형 업무 데이터 조회가 필요합니다.")
        if not reasons:
            reasons.append("명확한 DB 조회 조건이 없어 문서 검색 중심으로 처리합니다.")

        return RouteResult(route=route, reasons=reasons, tool_calls=tool_calls)

    def _infer_tool_calls(self, question: str) -> list[ToolCall]:
        normalized = question.lower()
        calls: list[ToolCall] = []

        lot_id = extract_lot_id(question)
        if lot_id:
            calls.append(
                ToolCall(
                    name="get_lot_history",
                    arguments={"lot_id": lot_id},
                    reason="질문에서 LOT 식별자가 감지되었습니다.",
                )
            )

        date = extract_date(question)
        line = extract_line(question)
        item_code = extract_item_code(question)
        production_signal = any(keyword in normalized for keyword in ["생산", "실적"])
        production_signal = production_signal or (
            any(keyword in normalized for keyword in ["수량", "현황"])
            and any([date, line, item_code])
        )
        if production_signal:
            arguments = {}
            if date:
                arguments["date"] = date
            if line:
                arguments["line"] = line
            if item_code:
                arguments["item_code"] = item_code
            calls.append(
                ToolCall(
                    name="get_daily_production",
                    arguments=arguments,
                    reason="생산 실적 또는 현황 조회 의도가 감지되었습니다.",
                )
            )

        if any(keyword in normalized for keyword in ["불량", "불량률", "품질"]):
            start_date, end_date = extract_date_range(question)
            calls.append(
                ToolCall(
                    name="get_quality_summary",
                    arguments={
                        "start_date": start_date or date,
                        "end_date": end_date or date,
                        "line": line,
                    },
                    reason="품질 또는 불량률 집계 의도가 감지되었습니다.",
                )
            )

        equipment_id = extract_equipment_id(question)
        alarm_code = extract_alarm_code(question)
        if alarm_code or any(keyword in normalized for keyword in ["설비", "알람", "비가동"]):
            arguments = {"limit": 5}
            if equipment_id:
                arguments["equipment_id"] = equipment_id
            if alarm_code:
                arguments["alarm_code"] = alarm_code
            calls.append(
                ToolCall(
                    name="get_equipment_alarms",
                    arguments=arguments,
                    reason="설비 알람 또는 비가동 이력 조회 의도가 감지되었습니다.",
                )
            )

        material_code = extract_material_code(question)
        warehouse = extract_warehouse(question)
        if any(keyword in normalized for keyword in ["재고", "자재", "창고", "입고", "출고"]):
            arguments = {}
            if material_code:
                arguments["material_code"] = material_code
            if warehouse:
                arguments["warehouse"] = warehouse
            calls.append(
                ToolCall(
                    name="get_inventory_status",
                    arguments=arguments,
                    reason="ERP성 자재 재고 조회 의도가 감지되었습니다.",
                )
            )

        return _dedupe_calls(calls)


def extract_lot_id(text: str) -> str | None:
    match = re.search(r"LOT[-_][A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*", text, re.IGNORECASE)
    return match.group(0).upper().replace("_", "-") if match else None


def extract_date(text: str) -> str | None:
    match = re.search(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def extract_date_range(text: str) -> tuple[str | None, str | None]:
    dates = re.findall(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", text)
    normalized = [f"{year}-{int(month):02d}-{int(day):02d}" for year, month, day in dates]
    if len(normalized) >= 2:
        return normalized[0], normalized[1]
    if len(normalized) == 1:
        return normalized[0], normalized[0]
    return None, None


def extract_line(text: str) -> str | None:
    match = re.search(r"\bLINE[-_ ]?([A-Z0-9]+)\b", text, re.IGNORECASE)
    if match:
        return f"LINE-{match.group(1).upper()}"

    korean_match = re.search(r"([A-Z0-9])\s*라인", text, re.IGNORECASE)
    if korean_match:
        return f"LINE-{korean_match.group(1).upper()}"

    return None


def extract_item_code(text: str) -> str | None:
    match = re.search(r"\bITEM[-_ ]?([A-Z0-9]+)\b", text, re.IGNORECASE)
    return f"ITEM-{match.group(1).upper()}" if match else None


def extract_equipment_id(text: str) -> str | None:
    match = re.search(r"\b(?:EQP|설비)[-_ ]?([A-Z0-9]+)\b", text, re.IGNORECASE)
    return f"EQP-{match.group(1).upper()}" if match else None


def extract_alarm_code(text: str) -> str | None:
    match = re.search(r"\bALM[-_ ]?([A-Z0-9]+)\b", text, re.IGNORECASE)
    return f"ALM-{match.group(1).upper()}" if match else None


def extract_material_code(text: str) -> str | None:
    match = re.search(r"\bMAT[-_][A-Za-z0-9][-A-Za-z0-9_]*\b", text, re.IGNORECASE)
    return match.group(0).upper().replace("_", "-") if match else None


def extract_warehouse(text: str) -> str | None:
    match = re.search(r"\bWH[-_][A-Za-z0-9][-A-Za-z0-9_]*\b", text, re.IGNORECASE)
    return match.group(0).upper().replace("_", "-") if match else None


def _dedupe_calls(calls: list[ToolCall]) -> list[ToolCall]:
    seen: set[tuple[str, tuple[tuple[str, object], ...]]] = set()
    unique: list[ToolCall] = []
    for call in calls:
        key = (call.name, tuple(sorted(call.arguments.items())))
        if key not in seen:
            seen.add(key)
            unique.append(call)
    return unique
