from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from .schema import RawSessionSchema
from .utils import parse_float, parse_int, read_csv_rows, read_json, write_json, write_jsonl


@dataclass(frozen=True)
class LeRobotExporter:
    fps: int = 10
    chunk_name: str = "chunk-000"

    def export_from_csv(
        self,
        labeled_csv: Path,
        session_root: Path,
        dataset_root: Path,
        task_name: str,
    ) -> dict[str, object]:
        schema = RawSessionSchema.from_root(session_root)
        session_meta = read_json(schema.session_meta_path)
        labeled_rows = read_csv_rows(labeled_csv)
        if not labeled_rows:
            raise ValueError(f"No labeled rows found in: {labeled_csv}")

        dataset_root = dataset_root.expanduser().resolve()
        data_dir = dataset_root / "data" / self.chunk_name
        videos_dir = dataset_root / "videos" / self.chunk_name
        meta_dir = dataset_root / "meta"
        data_dir.mkdir(parents=True, exist_ok=True)
        videos_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)

        episode_file = data_dir / "episode_000000.parquet"
        episode_rows = [self._episode_row(index, row, schema) for index, row in enumerate(labeled_rows)]
        pd.DataFrame(episode_rows).to_parquet(episode_file, index=False)

        copied_videos = self._copy_videos(schema.video_paths, session_root, videos_dir)
        episodes_payload: list[dict[str, object]] = [
            {
                "episode_index": 0,
                "session_id": session_meta["session_id"],
                "length": len(episode_rows),
                "tasks": [task_name],
                "data_file": f"data/{self.chunk_name}/episode_000000.parquet",
                "video_files": copied_videos,
            }
        ]
        tasks_payload: list[dict[str, object]] = [{"task_index": 0, "task": task_name}]
        info_payload: dict[str, object] = {
            "dataset_name": dataset_root.name,
            "robot_type": session_meta.get("robot_name", "Go2"),
            "fps": self.fps,
            "total_episodes": 1,
            "total_frames": len(episode_rows),
            "data_path": f"data/{self.chunk_name}/episode_{{episode_index:06d}}.parquet",
            "video_path": f"videos/{self.chunk_name}/{{video_key}}/episode_{{episode_index:06d}}.mp4",
            "features": {
                "observation.images.rgb_front": {"dtype": "image_path", "shape": [1]},
                "observation.images.depth_front": {"dtype": "image_path", "shape": [1]},
                "observation.state.pose_xy_yaw": {"dtype": "float32", "shape": [3]},
                "observation.state.linear_speed": {"dtype": "float32", "shape": [1]},
                "action.teleop_cmd": {"dtype": "float32", "shape": [3]},
                "action.future_waypoints_local": {
                    "dtype": "float32",
                    "shape": self._infer_waypoint_shape(labeled_rows[0]["label.future_waypoints_local"]),
                },
                "language_instruction": {"dtype": "string", "shape": [1]},
            },
        }
        stats_payload: list[dict[str, object]] = [
            {
                "episode_index": 0,
                "num_frames": len(episode_rows),
                "teleop_vx_mean": round(
                    sum(parse_float(row["teleop_vx"], "teleop_vx") for row in labeled_rows) / len(labeled_rows), 6
                ),
                "linear_speed_mean": round(
                    sum(parse_float(row["linear_speed"], "linear_speed") for row in labeled_rows) / len(labeled_rows), 6
                ),
            }
        ]

        write_jsonl(meta_dir / "episodes.jsonl", episodes_payload)
        write_jsonl(meta_dir / "tasks.jsonl", tasks_payload)
        write_json(meta_dir / "info.json", info_payload)
        write_jsonl(meta_dir / "episodes_stats.jsonl", stats_payload)

        return {
            "dataset_root": str(dataset_root),
            "episode_file": str(episode_file),
            "num_frames": len(episode_rows),
            "copied_videos": copied_videos,
        }

    def _episode_row(self, index: int, row: dict[str, str], schema: RawSessionSchema) -> dict[str, object]:
        return {
            "episode_index": parse_int(row["episode_index"], "episode_index"),
            "frame_index": index,
            "timestamp_ns": parse_int(row["timestamp_ns"], "timestamp_ns"),
            "observation.images.rgb_front": str((schema.session_root / row["rgb_path"]).resolve()),
            "observation.images.depth_front": str((schema.session_root / row["depth_path"]).resolve()),
            "observation.state.pose_xy_yaw": [
                parse_float(row["pose_x"], "pose_x"),
                parse_float(row["pose_y"], "pose_y"),
                parse_float(row["yaw"], "yaw"),
            ],
            "observation.state.linear_speed": parse_float(row["linear_speed"], "linear_speed"),
            "action.teleop_cmd": json.loads(row["action.teleop_cmd"]),
            "action.future_waypoints_local": json.loads(row["label.future_waypoints_local"]),
            "language_instruction": row["instruction"],
            "task_name": row["task_name"],
        }

    @staticmethod
    def _copy_videos(video_paths: tuple[Path, ...], session_root: Path, videos_dir: Path) -> list[str]:
        copied: list[str] = []
        for video_path in video_paths:
            if not video_path.exists():
                continue
            stream_dir = videos_dir / video_path.stem
            stream_dir.mkdir(parents=True, exist_ok=True)
            target_path = stream_dir / "episode_000000.mp4"
            if video_path.resolve() != target_path.resolve():
                shutil.copy2(video_path, target_path)
            copied.append(f"videos/chunk-000/{video_path.stem}/episode_000000.mp4")
        return copied

    @staticmethod
    def _infer_waypoint_shape(serialized_waypoints: str) -> list[int]:
        payload = json.loads(serialized_waypoints)
        if not isinstance(payload, list) or not payload:
            return [0, 0]
        first = payload[0]
        if not isinstance(first, list):
            return [len(payload)]
        return [len(payload), len(first)]
