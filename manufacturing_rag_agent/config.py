from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the MVP RAG-Agent."""

    knowledge_dir: Path = PROJECT_ROOT / "sample_data" / "knowledge_base"
    db_path: Path = PROJECT_ROOT / "sample_data" / "manufacturing_sample.db"
    chunk_size: int = 180
    chunk_overlap: int = 35
    top_k: int = 4
    min_relevance: float = 0.03

    @classmethod
    def from_strings(
        cls,
        knowledge_dir: str | None = None,
        db_path: str | None = None,
        chunk_size: int = 180,
        chunk_overlap: int = 35,
        top_k: int = 4,
        min_relevance: float = 0.03,
    ) -> "AppConfig":
        return cls(
            knowledge_dir=Path(knowledge_dir) if knowledge_dir else cls.knowledge_dir,
            db_path=Path(db_path) if db_path else cls.db_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=top_k,
            min_relevance=min_relevance,
        )
