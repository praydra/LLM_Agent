DROP TABLE IF EXISTS daily_production;
DROP TABLE IF EXISTS lot_history;
DROP TABLE IF EXISTS equipment_alarm;
DROP TABLE IF EXISTS inventory_status;

CREATE TABLE daily_production (
  date TEXT NOT NULL,
  line TEXT NOT NULL,
  item_code TEXT NOT NULL,
  produced_qty INTEGER NOT NULL,
  defect_qty INTEGER NOT NULL
);

CREATE TABLE lot_history (
  lot_id TEXT NOT NULL,
  process TEXT NOT NULL,
  equipment_id TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  result TEXT NOT NULL,
  defect_code TEXT,
  operator TEXT NOT NULL
);

CREATE TABLE equipment_alarm (
  alarm_id TEXT NOT NULL,
  equipment_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  alarm_code TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  action TEXT NOT NULL,
  downtime_min INTEGER NOT NULL
);

CREATE TABLE inventory_status (
  material_code TEXT NOT NULL,
  warehouse TEXT NOT NULL,
  available_qty INTEGER NOT NULL,
  reserved_qty INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
