from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .utils import read_csv_rows, read_json


@dataclass(frozen=True)
class RawSessionSchema:
    session_root: Path
    session_meta_path: Path
    instruction_path: Path
    rgb_index_path: Path
    depth_index_path: Path
    teleop_path: Path
    odom_path: Path
    video_paths: tuple[Path, ...]

    @classmethod
    def from_root(cls, session_root: Path) -> "RawSessionSchema":
        root = session_root.expanduser().resolve()
        meta_path = root / "session_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing session meta file: {meta_path}")

        meta = read_json(meta_path)
        instruction_path = root / meta["instruction_file"]
        rgb_index_path = root / meta["rgb_index_file"]
        depth_index_path = root / meta["depth_index_file"]
        teleop_path = root / meta["teleop_file"]
        odom_path = root / meta["odom_file"]
        video_paths = tuple(root / relative for relative in meta.get("video_files", []))

        schema = cls(
            session_root=root,
            session_meta_path=meta_path,
            instruction_path=instruction_path,
            rgb_index_path=rgb_index_path,
            depth_index_path=depth_index_path,
            teleop_path=teleop_path,
            odom_path=odom_path,
            video_paths=video_paths,
        )
        schema.validate()
        return schema

    def validate(self) -> None:
        required_paths = [
            self.session_meta_path,
            self.instruction_path,
            self.rgb_index_path,
            self.depth_index_path,
            self.teleop_path,
            self.odom_path,
        ]
        for path in required_paths:
            if not path.exists():
                raise FileNotFoundError(f"Missing required log artifact: {path}")

        self._validate_csv_columns(self.rgb_index_path, ["timestamp_ns", "file_path", "frame_id"])
        self._validate_csv_columns(self.depth_index_path, ["timestamp_ns", "file_path", "frame_id"])
        self._validate_csv_columns(self.teleop_path, ["timestamp_ns", "vx", "vy", "yaw_rate"])
        self._validate_csv_columns(self.odom_path, ["timestamp_ns", "pose_x", "pose_y", "yaw", "linear_speed"])

    def load_instruction_text(self) -> str:
        payload = read_json(self.instruction_path)
        text = payload.get("text", "")
        if not text:
            raise ValueError(f"Instruction file has no text: {self.instruction_path}")
        return str(text)

    @staticmethod
    def _validate_csv_columns(path: Path, required_columns: list[str]) -> None:
        rows = read_csv_rows(path)
        if not rows:
            raise ValueError(f"CSV is empty: {path}")
        row_keys = set(rows[0].keys())
        missing = [column for column in required_columns if column not in row_keys]
        if missing:
            raise ValueError(f"CSV {path} missing required columns: {missing}")
