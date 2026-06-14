from __future__ import annotations

import json
import os
from typing import Protocol
from urllib import error, request

from .schema import RetrievalResult, RouteResult, ToolResult


SYSTEM_PROMPT = (
    "너는 제조 기업 시스템 연계형 RAG-Agent이다. "
    "답변은 한국어로 작성하고, 문서 근거와 DB 조회 결과를 구분해 설명한다. "
    "근거가 부족한 내용은 추정하지 말고 한계로 표시한다. "
    "운영 DB에 대한 임의 SQL을 제안하지 말고, 제공된 Tool 조회 결과만 근거로 사용한다."
)


class AnswerGenerator(Protocol):
    def generate(
        self,
        question: str,
        route: RouteResult,
        retrievals: list[RetrievalResult],
        tool_results: list[ToolResult],
    ) -> str:
        ...


class TemplateAnswerGenerator:
    """Deterministic Korean answer generator for MVP demos and tests."""

    def generate(
        self,
        question: str,
        route: RouteResult,
        retrievals: list[RetrievalResult],
        tool_results: list[ToolResult],
    ) -> str:
        sections = [
            f"질문: {question}",
            f"질문 유형: {route.route}",
            "판단 근거: " + " ".join(route.reasons),
        ]

        if tool_results:
            sections.append(self._format_tool_results(tool_results))

        if retrievals:
            sections.append(self._format_retrievals(retrievals))

        sections.append(self._format_conclusion(route, retrievals, tool_results))
        return "\n\n".join(sections)

    def _format_tool_results(self, tool_results: list[ToolResult]) -> str:
        lines = ["조회 결과"]
        for result in tool_results:
            lines.append(f"- {result.tool_name}: {result.summary}")
            for row in result.rows[:5]:
                lines.append(f"  - {compact_row(row)}")
            if len(result.rows) > 5:
                lines.append(f"  - 외 {len(result.rows) - 5}건")
        return "\n".join(lines)

    def _format_retrievals(self, retrievals: list[RetrievalResult]) -> str:
        lines = ["문서 근거"]
        for index, result in enumerate(retrievals, start=1):
            snippet = result.chunk.text.replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:237] + "..."
            lines.append(
                f"- [{index}] {result.chunk.title} "
                f"(score={result.score:.3f}) - {snippet}"
            )
        return "\n".join(lines)

    def _format_conclusion(
        self,
        route: RouteResult,
        retrievals: list[RetrievalResult],
        tool_results: list[ToolResult],
    ) -> str:
        evidence_parts = []
        if tool_results:
            evidence_parts.append("업무 DB 조회 결과")
        if retrievals:
            evidence_parts.append("문서 검색 근거")

        evidence = "와 ".join(evidence_parts) if evidence_parts else "제공된 근거"
        if route.route == "hybrid":
            answer = (
                f"요약: 이 질문은 정형 데이터와 문서 기준을 함께 요구하므로 {evidence}를 "
                "통합해 판단해야 합니다. 운영 적용 시에는 조회 조건, 사용자 권한, 최신 문서 "
                "버전을 함께 검증하는 것이 필요합니다."
            )
        elif route.route == "data":
            answer = (
                f"요약: 이 질문은 수치 또는 이력 조회 성격이 강하므로 {evidence}를 기준으로 "
                "답변합니다. 문서 기준이 필요한 후속 질문은 RAG 검색을 함께 수행하는 구성이 "
                "적합합니다."
            )
        else:
            answer = (
                f"요약: 이 질문은 업무 기준 설명 성격이 강하므로 {evidence}를 중심으로 답변합니다. "
                "실제 LOT, 설비, 생산 수량 확인이 필요하면 DB Tool을 추가 호출해야 합니다."
            )
        return answer


class OllamaAnswerGenerator:
    """Answer generator using a local Ollama server.

    Ollama must be running locally, usually at http://localhost:11434.
    No extra Python package is required because this class uses urllib.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        question: str,
        route: RouteResult,
        retrievals: list[RetrievalResult],
        tool_results: list[ToolResult],
    ) -> str:
        context = build_generation_context(route, retrievals, tool_results)
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"질문: {question}\n\n"
                        f"컨텍스트 JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
                        "위 컨텍스트만 사용해서 다음 형식으로 답변해줘:\n"
                        "1. 결론\n"
                        "2. DB 조회 결과\n"
                        "3. 문서 근거\n"
                        "4. 한계 및 확인 필요 사항"
                    ),
                },
            ],
        }

        raw_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=raw_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(
                "Ollama server request failed. "
                "Run `ollama serve` and make sure the model is pulled, for example "
                f"`ollama pull {self.model}`."
            ) from exc

        data = json.loads(body)
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError(f"Unexpected Ollama response: {body}")
        return str(content).strip()


class OpenAIAnswerGenerator:
    """Optional answer generator using the OpenAI Python SDK.

    The SDK is intentionally optional so the MVP can run offline. Install the
    OpenAI package and set OPENAI_API_KEY to enable this class.
    """

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        self.model = model

    def generate(
        self,
        question: str,
        route: RouteResult,
        retrievals: list[RetrievalResult],
        tool_results: list[ToolResult],
    ) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIAnswerGenerator")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use OpenAIAnswerGenerator") from exc

        client = OpenAI()
        context = build_generation_context(route, retrievals, tool_results)

        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"질문: {question}\n\n"
                        f"컨텍스트 JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
                    ),
                },
            ],
        )
        return response.output_text


def build_generation_context(
    route: RouteResult,
    retrievals: list[RetrievalResult],
    tool_results: list[ToolResult],
) -> dict[str, object]:
    return {
        "route": {
            "type": route.route,
            "reasons": route.reasons,
            "tool_calls": [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "reason": call.reason,
                }
                for call in route.tool_calls
            ],
        },
        "retrievals": [
            {
                "title": result.chunk.title,
                "source_path": result.chunk.source_path,
                "score": result.score,
                "text": result.chunk.text,
            }
            for result in retrievals
        ],
        "tool_results": [
            {
                "tool_name": result.tool_name,
                "arguments": result.arguments,
                "summary": result.summary,
                "rows": result.rows,
            }
            for result in tool_results
        ],
    }


def compact_row(row: dict[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in row.items())
