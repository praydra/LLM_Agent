from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .schema import ToolResult


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    handler: Callable[..., ToolResult]


class ManufacturingDatabase:
    """Safe read-only manufacturing data access layer.

    Replace this class with real MES, ERP, QMS, or equipment API clients in a
    production integration. Keep the public methods stable so the Agent can
    continue calling predefined tools instead of generating arbitrary SQL.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_lot_history(self, lot_id: str) -> ToolResult:
        rows = self._fetch_all(
            """
            SELECT lot_id, process, equipment_id, start_time, end_time, result,
                   defect_code, operator
            FROM lot_history
            WHERE lot_id = ?
            ORDER BY start_time
            """,
            (lot_id,),
        )
        return ToolResult(
            tool_name="get_lot_history",
            arguments={"lot_id": lot_id},
            rows=rows,
            summary=f"{lot_id} LOT 공정 이력 {len(rows)}건을 조회했습니다.",
        )

    def get_daily_production(
        self,
        date: str | None = None,
        line: str | None = None,
        item_code: str | None = None,
    ) -> ToolResult:
        where = []
        params: list[Any] = []
        if date:
            where.append("date = ?")
            params.append(date)
        if line:
            where.append("line = ?")
            params.append(line)
        if item_code:
            where.append("item_code = ?")
            params.append(item_code)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._fetch_all(
            f"""
            SELECT date, line, item_code,
                   SUM(produced_qty) AS produced_qty,
                   SUM(defect_qty) AS defect_qty,
                   ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(produced_qty), 0), 2)
                     AS defect_rate_pct
            FROM daily_production
            {where_sql}
            GROUP BY date, line, item_code
            ORDER BY date, line, item_code
            """,
            tuple(params),
        )
        return ToolResult(
            tool_name="get_daily_production",
            arguments={"date": date, "line": line, "item_code": item_code},
            rows=rows,
            summary=f"생산 실적 {len(rows)}건을 조회했습니다.",
        )

    def get_quality_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        line: str | None = None,
    ) -> ToolResult:
        where = []
        params: list[Any] = []
        if start_date:
            where.append("date >= ?")
            params.append(start_date)
        if end_date:
            where.append("date <= ?")
            params.append(end_date)
        if line:
            where.append("line = ?")
            params.append(line)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._fetch_all(
            f"""
            SELECT line,
                   SUM(produced_qty) AS produced_qty,
                   SUM(defect_qty) AS defect_qty,
                   ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(produced_qty), 0), 2)
                     AS defect_rate_pct
            FROM daily_production
            {where_sql}
            GROUP BY line
            ORDER BY defect_rate_pct DESC
            """,
            tuple(params),
        )
        return ToolResult(
            tool_name="get_quality_summary",
            arguments={"start_date": start_date, "end_date": end_date, "line": line},
            rows=rows,
            summary=f"품질 요약 {len(rows)}건을 조회했습니다.",
        )

    def get_equipment_alarms(
        self,
        equipment_id: str | None = None,
        alarm_code: str | None = None,
        occurred_from: str | None = None,
        occurred_to: str | None = None,
        limit: int = 5,
    ) -> ToolResult:
        safe_limit = max(1, min(int(limit), 50))
        where = []
        params: list[Any] = []
        if equipment_id:
            where.append("equipment_id = ?")
            params.append(equipment_id)
        if alarm_code:
            where.append("alarm_code = ?")
            params.append(alarm_code)
        if occurred_from:
            where.append("occurred_at >= ?")
            params.append(occurred_from)
        if occurred_to:
            where.append("occurred_at <= ?")
            params.append(occurred_to)
        params.append(safe_limit)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._fetch_all(
            f"""
            SELECT alarm_id, equipment_id, occurred_at, alarm_code, severity,
                   message, action, downtime_min
            FROM equipment_alarm
            {where_sql}
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return ToolResult(
            tool_name="get_equipment_alarms",
            arguments={
                "equipment_id": equipment_id,
                "alarm_code": alarm_code,
                "occurred_from": occurred_from,
                "occurred_to": occurred_to,
                "limit": safe_limit,
            },
            rows=rows,
            summary=f"설비 알람 이력 {len(rows)}건을 조회했습니다.",
        )

    def get_inventory_status(
        self,
        material_code: str | None = None,
        warehouse: str | None = None,
    ) -> ToolResult:
        where = []
        params: list[Any] = []
        if material_code:
            where.append("material_code = ?")
            params.append(material_code)
        if warehouse:
            where.append("warehouse = ?")
            params.append(warehouse)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._fetch_all(
            f"""
            SELECT material_code, warehouse, available_qty, reserved_qty,
                   available_qty - reserved_qty AS allocatable_qty,
                   updated_at
            FROM inventory_status
            {where_sql}
            ORDER BY material_code, warehouse
            """,
            tuple(params),
        )
        return ToolResult(
            tool_name="get_inventory_status",
            arguments={"material_code": material_code, "warehouse": warehouse},
            rows=rows,
            summary=f"자재 재고 {len(rows)}건을 조회했습니다.",
        )

    def _fetch_all(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {self.db_path}. Run scripts/build_sample_db.py first."
            )

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


class ManufacturingToolRegistry:
    """Registry for predefined safe tools."""

    def __init__(self, database: ManufacturingDatabase) -> None:
        self.database = database
        self._tools: dict[str, RegisteredTool] = {
            "get_lot_history": RegisteredTool(
                name="get_lot_history",
                description="LOT별 공정, 설비, 품질 판정 이력을 조회합니다.",
                handler=database.get_lot_history,
            ),
            "get_daily_production": RegisteredTool(
                name="get_daily_production",
                description="일자, 라인, 품목 기준 생산 수량과 불량률을 조회합니다.",
                handler=database.get_daily_production,
            ),
            "get_quality_summary": RegisteredTool(
                name="get_quality_summary",
                description="기간과 라인 기준 품질 요약 및 불량률을 집계합니다.",
                handler=database.get_quality_summary,
            ),
            "get_equipment_alarms": RegisteredTool(
                name="get_equipment_alarms",
                description="설비 알람, 조치, 비가동 이력을 조회합니다.",
                handler=database.get_equipment_alarms,
            ),
            "get_inventory_status": RegisteredTool(
                name="get_inventory_status",
                description="ERP성 자재/창고 재고와 할당 가능 수량을 조회합니다.",
                handler=database.get_inventory_status,
            ),
        }

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name].handler(**_drop_none(arguments))

    def descriptions(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
