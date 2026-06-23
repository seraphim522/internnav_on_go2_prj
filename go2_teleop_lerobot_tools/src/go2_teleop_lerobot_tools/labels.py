from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .utils import parse_float, parse_int, read_csv_rows, rotate_global_to_local, write_csv_rows


@dataclass(frozen=True)
class FutureWaypointLabelBuilder:
    num_waypoints: int = 5
    step: int = 3

    def build_from_csv(self, aligned_csv: Path, output_csv: Path) -> list[dict[str, object]]:
        source_rows = read_csv_rows(aligned_csv)
        labeled_rows = self.build_rows(source_rows)
        if labeled_rows:
            write_csv_rows(output_csv, labeled_rows, list(labeled_rows[0].keys()))
        return labeled_rows

    def build_rows(self, rows: list[dict[str, str]]) -> list[dict[str, object]]:
        labeled_rows: list[dict[str, object]] = []
        for index, row in enumerate(rows):
            future_indices = [index + (offset + 1) * self.step for offset in range(self.num_waypoints)]
            if future_indices[-1] >= len(rows):
                break

            pose_x = parse_float(row["pose_x"], "pose_x")
            pose_y = parse_float(row["pose_y"], "pose_y")
            yaw = parse_float(row["yaw"], "yaw")

            waypoints_local: list[list[float]] = []
            for future_index in future_indices:
                future_row = rows[future_index]
                future_x = parse_float(future_row["pose_x"], "future.pose_x")
                future_y = parse_float(future_row["pose_y"], "future.pose_y")
                local_x, local_y = rotate_global_to_local(future_x - pose_x, future_y - pose_y, yaw)
                waypoints_local.append([round(local_x, 6), round(local_y, 6)])

            labeled_rows.append(
                {
                    **row,
                    "episode_index": 0,
                    "frame_index": parse_int(row["rgb_frame_id"], "rgb_frame_id") - 1,
                    "action.teleop_cmd": json.dumps(
                        [
                            parse_float(row["teleop_vx"], "teleop_vx"),
                            parse_float(row["teleop_vy"], "teleop_vy"),
                            parse_float(row["teleop_yaw_rate"], "teleop_yaw_rate"),
                        ]
                    ),
                    "label.future_waypoints_local": json.dumps(waypoints_local),
                }
            )
        return labeled_rows
