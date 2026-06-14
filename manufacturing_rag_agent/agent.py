from __future__ import annotations

from datetime import datetime, timedelta

from .config import AppConfig
from .documents import chunk_documents, load_documents
from .llm import AnswerGenerator, TemplateAnswerGenerator
from .router import QuestionRouter
from .schema import AgentResponse, RetrievalResult, ToolCall, ToolResult
from .tools import ManufacturingDatabase, ManufacturingToolRegistry
from .vector_store import TfidfVectorStore


class ManufacturingRagAgent:
    """Orchestrates routing, RAG retrieval, safe tool-calling, and answer generation."""

    def __init__(
        self,
        config: AppConfig | None = None,
        router: QuestionRouter | None = None,
        tool_registry: ManufacturingToolRegistry | None = None,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.router = router or QuestionRouter()
        self.tool_registry = tool_registry or ManufacturingToolRegistry(
            ManufacturingDatabase(self.config.db_path)
        )
        self.answer_generator = answer_generator or TemplateAnswerGenerator()

        documents = load_documents(self.config.knowledge_dir)
        chunks = chunk_documents(
            documents,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        self.vector_store = TfidfVectorStore(chunks)

    def ask(self, question: str) -> AgentResponse:
        route = self.router.classify(question)
        retrievals = self._retrieve_if_needed(question, route.route)
        tool_results = self._call_tools(route.tool_calls)
        answer = self.answer_generator.generate(question, route, retrievals, tool_results)

        return AgentResponse(
            question=question,
            route=route,
            answer=answer,
            retrievals=retrievals,
            tool_results=tool_results,
        )

    def _retrieve_if_needed(self, question: str, route_type: str) -> list[RetrievalResult]:
        if route_type not in {"document", "hybrid"}:
            return []

        return self.vector_store.search(
            query=question,
            top_k=self.config.top_k,
            min_score=self.config.min_relevance,
        )

    def _call_tools(self, calls: list[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        lot_equipment_ids: set[str] = set()
        lot_alarm_window: tuple[str, str] | None = None

        for call in calls:
            if (
                call.name == "get_equipment_alarms"
                and not call.arguments.get("equipment_id")
                and lot_equipment_ids
            ):
                results.append(
                    self._call_equipment_alarms_for_lot(
                        lot_equipment_ids,
                        call,
                        lot_alarm_window,
                    )
                )
                continue

            result = self.tool_registry.call(call.name, call.arguments)
            results.append(result)

            if call.name == "get_lot_history":
                lot_equipment_ids.update(
                    str(row["equipment_id"])
                    for row in result.rows
                    if row.get("equipment_id")
                )
                lot_alarm_window = _lot_alarm_window(result.rows)

        return results

    def _call_equipment_alarms_for_lot(
        self,
        equipment_ids: set[str],
        original_call: ToolCall,
        alarm_window: tuple[str, str] | None,
    ) -> ToolResult:
        rows = []
        for equipment_id in sorted(equipment_ids):
            arguments = {
                **original_call.arguments,
                "equipment_id": equipment_id,
            }
            if alarm_window:
                arguments["occurred_from"] = alarm_window[0]
                arguments["occurred_to"] = alarm_window[1]

            result = self.tool_registry.call(
                "get_equipment_alarms",
                arguments,
            )
            rows.extend(result.rows)

        rows.sort(key=lambda row: str(row.get("occurred_at", "")), reverse=True)
        return ToolResult(
            tool_name="get_equipment_alarms",
            arguments={
                "equipment_ids": sorted(equipment_ids),
                "occurred_from": alarm_window[0] if alarm_window else None,
                "occurred_to": alarm_window[1] if alarm_window else None,
                "limit_per_equipment": original_call.arguments.get("limit", 5),
            },
            rows=rows,
            summary=f"LOT 이력에 포함된 설비 {len(equipment_ids)}대의 알람 이력 {len(rows)}건을 조회했습니다.",
        )


def _lot_alarm_window(rows: list[dict[str, object]]) -> tuple[str, str] | None:
    starts = [_parse_time(str(row.get("start_time"))) for row in rows if row.get("start_time")]
    ends = [_parse_time(str(row.get("end_time"))) for row in rows if row.get("end_time")]
    starts = [value for value in starts if value]
    ends = [value for value in ends if value]
    if not starts or not ends:
        return None

    start = min(starts) - timedelta(hours=2)
    end = max(ends) + timedelta(hours=2)
    return start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
