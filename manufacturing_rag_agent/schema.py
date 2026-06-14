from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RouteType = Literal["document", "data", "hybrid"]


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    source_path: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    arguments: dict[str, Any]
    rows: list[dict[str, Any]]
    summary: str


@dataclass(frozen=True)
class RouteResult:
    route: RouteType
    reasons: list[str]
    tool_calls: list[ToolCall]


@dataclass(frozen=True)
class AgentResponse:
    question: str
    route: RouteResult
    answer: str
    retrievals: list[RetrievalResult]
    tool_results: list[ToolResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "route": {
                "type": self.route.route,
                "reasons": self.route.reasons,
                "tool_calls": [
                    {
                        "name": call.name,
                        "arguments": call.arguments,
                        "reason": call.reason,
                    }
                    for call in self.route.tool_calls
                ],
            },
            "answer": self.answer,
            "retrievals": [
                {
                    "score": round(result.score, 4),
                    "title": result.chunk.title,
                    "source_path": result.chunk.source_path,
                    "text": result.chunk.text,
                }
                for result in self.retrievals
            ],
            "tool_results": [
                {
                    "tool_name": result.tool_name,
                    "arguments": result.arguments,
                    "summary": result.summary,
                    "rows": result.rows,
                }
                for result in self.tool_results
            ],
        }
