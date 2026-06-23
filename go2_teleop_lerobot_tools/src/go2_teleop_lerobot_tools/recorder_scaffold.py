from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, TypeAlias


RawScalar: TypeAlias = str | int | float


@dataclass(frozen=True)
class RecorderConfig:
    session_root: Path
    session_id: str
    task_name: str
    operator: str
    instruction: str


@dataclass
class TeleopRecorderScaffold:
    config: RecorderConfig
    teleop_rows: list[dict[str, object]] = field(default_factory=list)
    odom_rows: list[dict[str, object]] = field(default_factory=list)
    rgb_rows: list[dict[str, object]] = field(default_factory=list)
    depth_rows: list[dict[str, object]] = field(default_factory=list)

    def record_teleop(self, timestamp_ns: int, vx: float, vy: float, yaw_rate: float) -> None:
        self.teleop_rows.append(
            {"timestamp_ns": timestamp_ns, "vx": vx, "vy": vy, "yaw_rate": yaw_rate}
        )

    def record_odom(self, timestamp_ns: int, pose_x: float, pose_y: float, yaw: float, linear_speed: float) -> None:
        self.odom_rows.append(
            {
                "timestamp_ns": timestamp_ns,
                "pose_x": pose_x,
                "pose_y": pose_y,
                "yaw": yaw,
                "linear_speed": linear_speed,
            }
        )

    def record_rgb_frame(self, timestamp_ns: int, file_path: str, frame_id: int) -> None:
        self.rgb_rows.append({"timestamp_ns": timestamp_ns, "file_path": file_path, "frame_id": frame_id})

    def record_depth_frame(self, timestamp_ns: int, file_path: str, frame_id: int) -> None:
        self.depth_rows.append({"timestamp_ns": timestamp_ns, "file_path": file_path, "frame_id": frame_id})

    def flush(self) -> Path:
        root = self.config.session_root.expanduser().resolve()
        (root / "rgb_front").mkdir(parents=True, exist_ok=True)
        (root / "depth_front").mkdir(parents=True, exist_ok=True)
        (root / "videos").mkdir(parents=True, exist_ok=True)

        self._write_json(
            root / "session_meta.json",
            {
                "session_id": self.config.session_id,
                "robot_name": "Go2",
                "operator": self.config.operator,
                "task_name": self.config.task_name,
                "instruction_file": "instruction.json",
                "rgb_index_file": "rgb_front.csv",
                "depth_index_file": "depth_front.csv",
                "teleop_file": "teleop_cmd.csv",
                "odom_file": "odom.csv",
                "video_files": [],
            },
        )
        self._write_json(root / "instruction.json", {"text": self.config.instruction})
        self._write_csv(root / "teleop_cmd.csv", self.teleop_rows, ["timestamp_ns", "vx", "vy", "yaw_rate"])
        self._write_csv(root / "odom.csv", self.odom_rows, ["timestamp_ns", "pose_x", "pose_y", "yaw", "linear_speed"])
        self._write_csv(root / "rgb_front.csv", self.rgb_rows, ["timestamp_ns", "file_path", "frame_id"])
        self._write_csv(root / "depth_front.csv", self.depth_rows, ["timestamp_ns", "file_path", "frame_id"])
        return root

    @classmethod
    def from_iterable(
        cls, config: RecorderConfig, source_rows: Iterable[dict[str, RawScalar]]
    ) -> "TeleopRecorderScaffold":
        recorder = cls(config=config)
        for item in source_rows:
            stream = str(item["stream"])
            if stream == "teleop":
                recorder.record_teleop(
                    timestamp_ns=int(item["timestamp_ns"]),
                    vx=float(item["vx"]),
                    vy=float(item["vy"]),
                    yaw_rate=float(item["yaw_rate"]),
                )
            elif stream == "odom":
                recorder.record_odom(
                    timestamp_ns=int(item["timestamp_ns"]),
                    pose_x=float(item["pose_x"]),
                    pose_y=float(item["pose_y"]),
                    yaw=float(item["yaw"]),
                    linear_speed=float(item["linear_speed"]),
                )
            elif stream == "rgb":
                recorder.record_rgb_frame(
                    timestamp_ns=int(item["timestamp_ns"]),
                    file_path=str(item["file_path"]),
                    frame_id=int(item["frame_id"]),
                )
            elif stream == "depth":
                recorder.record_depth_frame(
                    timestamp_ns=int(item["timestamp_ns"]),
                    file_path=str(item["file_path"]),
                    frame_id=int(item["frame_id"]),
                )
        return recorder

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
