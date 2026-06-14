from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "sample_data" / "manufacturing_sample.db"
DEFAULT_QUESTION_PATH = PROJECT_ROOT / "sample_data" / "test_questions.json"
sys.path.insert(0, str(PROJECT_ROOT))

from manufacturing_rag_agent import AppConfig, ManufacturingRagAgent


def ensure_sample_db() -> None:
    if DB_PATH.exists():
        return
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_sample_db.py")], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the manufacturing RAG-Agent test question set")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTION_PATH), help="Question-set JSON path")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions")
    parser.add_argument("--show-answer", action="store_true", help="Print generated answer snippets")
    args = parser.parse_args()

    ensure_sample_db()
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[: args.limit]

    agent = ManufacturingRagAgent(config=AppConfig(db_path=DB_PATH))

    passed = 0
    for item in questions:
        response = agent.ask(item["question"])
        actual_tools = [result.tool_name for result in response.tool_results]
        route_ok = response.route.route == item["expected_route"]
        tools_ok = all(tool in actual_tools for tool in item["expected_tools"])
        status = "PASS" if route_ok and tools_ok else "FAIL"
        passed += int(status == "PASS")

        print(
            f"{status} {item['id']} "
            f"route={response.route.route}/{item['expected_route']} "
            f"tools={actual_tools}"
        )
        print(f"  Q. {item['question']}")
        print(f"  Focus. {item['evaluation_focus']}")
        if args.show_answer:
            snippet = response.answer.replace("\n", " ")
            print(f"  A. {snippet[:260]}{'...' if len(snippet) > 260 else ''}")

    print("-" * 80)
    print(f"Summary: {passed}/{len(questions)} checks passed")


if __name__ == "__main__":
    main()
