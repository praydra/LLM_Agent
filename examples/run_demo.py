from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "sample_data" / "manufacturing_sample.db"
sys.path.insert(0, str(PROJECT_ROOT))

from manufacturing_rag_agent import AppConfig, ManufacturingRagAgent


def ensure_sample_db() -> None:
    if DB_PATH.exists():
        return
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_sample_db.py")], check=True)


def main() -> None:
    ensure_sample_db()
    agent = ManufacturingRagAgent(config=AppConfig(db_path=DB_PATH))

    questions = [
        "LOT-2026-A001 이력과 관련 알람 조치 기준을 알려줘",
        "2026-06-03 LINE-A 생산 현황과 불량률을 알려줘",
        "MAT-RESIN-A WH-RAW 재고와 할당 가능 수량은?",
        "LOT-2026-B015는 재작업이 있었는데 QMS 보류 기준상 어떻게 판단해야 해?",
        "ALM-101 과열 알람이 발생했을 때 작업자가 확인해야 할 절차는?",
    ]

    for question in questions:
        print("=" * 80)
        print(agent.ask(question).answer)


if __name__ == "__main__":
    main()
