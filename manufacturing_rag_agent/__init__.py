"""MVP package for a manufacturing RAG-Agent.

The package is intentionally small and dependency-light so it can be copied into
another application and adapted to real MES, ERP, QMS, or equipment APIs.
"""

from .agent import ManufacturingRagAgent
from .config import AppConfig
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator, TemplateAnswerGenerator
from .tools import ManufacturingDatabase, ManufacturingToolRegistry

__all__ = [
    "AppConfig",
    "ManufacturingDatabase",
    "ManufacturingRagAgent",
    "ManufacturingToolRegistry",
    "OllamaAnswerGenerator",
    "OpenAIAnswerGenerator",
    "TemplateAnswerGenerator",
]
