from __future__ import annotations

import re
from pathlib import Path

from .schema import Chunk, Document


SUPPORTED_EXTENSIONS = {".md", ".txt"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[가-힣]+")


def load_documents(knowledge_dir: Path) -> list[Document]:
    """Load Markdown and text documents from a knowledge-base directory."""

    if not knowledge_dir.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")

    documents: list[Document] = []
    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        title = extract_title(text) or path.stem.replace("_", " ")
        documents.append(
            Document(
                doc_id=path.stem,
                title=title,
                source_path=str(path),
                text=text,
            )
        )

    if not documents:
        raise ValueError(f"No knowledge documents found in {knowledge_dir}")

    return documents


def extract_title(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            return line[:80]
    return None


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 180,
    chunk_overlap: int = 35,
) -> list[Chunk]:
    """Chunk documents using token windows while preserving readable text."""

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    for document in documents:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", document.text) if p.strip()]
        windows = _build_windows(paragraphs, chunk_size, chunk_overlap)
        for index, chunk_text in enumerate(windows, start=1):
            chunks.append(
                Chunk(
                    chunk_id=f"{document.doc_id}:{index}",
                    doc_id=document.doc_id,
                    title=document.title,
                    source_path=document.source_path,
                    text=chunk_text,
                )
            )

    return chunks


def _build_windows(paragraphs: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        token_count = len(tokenize(paragraph))
        if current and current_tokens + token_count > chunk_size:
            windows.append("\n\n".join(current))
            current = _tail_overlap(current, chunk_overlap)
            current_tokens = sum(len(tokenize(p)) for p in current)

        current.append(paragraph)
        current_tokens += token_count

    if current:
        windows.append("\n\n".join(current))

    return windows


def _tail_overlap(paragraphs: list[str], overlap_tokens: int) -> list[str]:
    if overlap_tokens <= 0:
        return []

    kept: list[str] = []
    total = 0
    for paragraph in reversed(paragraphs):
        count = len(tokenize(paragraph))
        if kept and total + count > overlap_tokens:
            break
        kept.append(paragraph)
        total += count
    return list(reversed(kept))
