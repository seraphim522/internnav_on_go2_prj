from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .schema import RawSessionSchema
from .utils import parse_float, parse_int, read_csv_rows, read_json, write_csv_rows


@dataclass(frozen=True)
class SessionAligner:
    max_delta_ns: int = 100_000_000

    def align_session(self, session_root: Path, output_csv: Path) -> list[dict[str, object]]:
        schema = RawSessionSchema.from_root(session_root)
        session_meta = read_json(schema.session_meta_path)
        instruction_text = schema.load_instruction_text()

        rgb_rows = self._normalize_rows(read_csv_rows(schema.rgb_index_path), ["timestamp_ns", "file_path", "frame_id"])
        depth_rows = self._normalize_rows(read_csv_rows(schema.depth_index_path), ["timestamp_ns", "file_path", "frame_id"])
        teleop_rows = self._normalize_rows(read_csv_rows(schema.teleop_path), ["timestamp_ns", "vx", "vy", "yaw_rate"])
        odom_rows = self._normalize_rows(read_csv_rows(schema.odom_path), ["timestamp_ns", "pose_x", "pose_y", "yaw", "linear_speed"])

        aligned_rows: list[dict[str, object]] = []
        for rgb_row in rgb_rows:
            anchor_ts = parse_int(rgb_row["timestamp_ns"], "rgb.timestamp_ns")
            depth_row = self._nearest_row(depth_rows, anchor_ts, "depth")
            teleop_row = self._nearest_row(teleop_rows, anchor_ts, "teleop")
            odom_row = self._nearest_row(odom_rows, anchor_ts, "odom")

            aligned_rows.append(
                {
                    "session_id": str(session_meta["session_id"]),
                    "task_name": str(session_meta.get("task_name", "")),
                    "instruction": instruction_text,
                    "timestamp_ns": anchor_ts,
                    "rgb_frame_id": parse_int(rgb_row["frame_id"], "rgb.frame_id"),
                    "rgb_path": str(rgb_row["file_path"]),
                    "depth_frame_id": parse_int(depth_row["frame_id"], "depth.frame_id"),
                    "depth_path": str(depth_row["file_path"]),
                    "teleop_vx": parse_float(teleop_row["vx"], "teleop.vx"),
                    "teleop_vy": parse_float(teleop_row["vy"], "teleop.vy"),
                    "teleop_yaw_rate": parse_float(teleop_row["yaw_rate"], "teleop.yaw_rate"),
                    "pose_x": parse_float(odom_row["pose_x"], "odom.pose_x"),
                    "pose_y": parse_float(odom_row["pose_y"], "odom.pose_y"),
                    "yaw": parse_float(odom_row["yaw"], "odom.yaw"),
                    "linear_speed": parse_float(odom_row["linear_speed"], "odom.linear_speed"),
                }
            )

        fieldnames = list(aligned_rows[0].keys()) if aligned_rows else []
        if fieldnames:
            write_csv_rows(output_csv, aligned_rows, fieldnames)
        return aligned_rows

    def _nearest_row(self, rows: list[dict[str, str]], anchor_ts: int, stream_name: str) -> dict[str, str]:
        best_row: dict[str, str] | None = None
        best_delta: int | None = None
        for row in rows:
            row_ts = parse_int(row["timestamp_ns"], f"{stream_name}.timestamp_ns")
            delta = abs(anchor_ts - row_ts)
            if best_delta is None or delta < best_delta:
                best_row = row
                best_delta = delta

        if best_row is None or best_delta is None:
            raise ValueError(f"No rows available for stream: {stream_name}")
        if best_delta > self.max_delta_ns:
            raise ValueError(
                f"Nearest {stream_name} row is too far from anchor timestamp {anchor_ts}: {best_delta} ns"
            )
        return best_row

    @staticmethod
    def _normalize_rows(rows: list[dict[str, str]], required_columns: list[str]) -> list[dict[str, str]]:
        if not rows:
            raise ValueError("Expected non-empty stream rows")
        first_keys = set(rows[0].keys())
        missing = [column for column in required_columns if column not in first_keys]
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        return rows
