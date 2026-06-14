from __future__ import annotations

import argparse
import json

from .agent import ManufacturingRagAgent
from .config import AppConfig
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator, TemplateAnswerGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Manufacturing RAG-Agent MVP")
    parser.add_argument("--question", required=True, help="Korean manufacturing work question")
    parser.add_argument("--knowledge-dir", default=None, help="Knowledge base directory")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    parser.add_argument("--top-k", type=int, default=4, help="Number of RAG chunks")
    provider_group = parser.add_mutually_exclusive_group()
    provider_group.add_argument(
        "--use-openai",
        action="store_true",
        help="Use OpenAIAnswerGenerator instead of deterministic template output",
    )
    provider_group.add_argument(
        "--use-ollama",
        action="store_true",
        help="Use local Ollama instead of deterministic template output",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        help="Ollama model name. Defaults to OLLAMA_MODEL or qwen2.5:7b",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama base URL. Defaults to OLLAMA_BASE_URL or http://localhost:11434",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=int,
        default=120,
        help="Ollama request timeout in seconds",
    )
    parser.add_argument("--json", action="store_true", help="Print full response JSON")
    args = parser.parse_args()

    config = AppConfig.from_strings(
        knowledge_dir=args.knowledge_dir,
        db_path=args.db_path,
        top_k=args.top_k,
    )
    if args.use_openai:
        generator = OpenAIAnswerGenerator()
    elif args.use_ollama:
        generator = OllamaAnswerGenerator(
            model=args.ollama_model,
            base_url=args.ollama_url,
            timeout_seconds=args.ollama_timeout,
        )
    else:
        generator = TemplateAnswerGenerator()
    agent = ManufacturingRagAgent(config=config, answer_generator=generator)
    response = agent.ask(args.question)

    if args.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(response.answer)


if __name__ == "__main__":
    main()
