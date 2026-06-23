from __future__ import annotations

import argparse
from pathlib import Path

from .aligner import SessionAligner
from .labels import FutureWaypointLabelBuilder
from .lerobot_export import LeRobotExporter
from .recorder_scaffold import RecorderConfig, TeleopRecorderScaffold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Go2 teleop log processing tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    align_parser = subparsers.add_parser("align", help="Align raw session logs")
    align_parser.add_argument("--session-root", type=Path, required=True)
    align_parser.add_argument("--output-csv", type=Path, required=True)
    align_parser.add_argument("--max-delta-ms", type=int, default=100)

    labels_parser = subparsers.add_parser("build-labels", help="Build future waypoint labels")
    labels_parser.add_argument("--aligned-csv", type=Path, required=True)
    labels_parser.add_argument("--output-csv", type=Path, required=True)
    labels_parser.add_argument("--num-waypoints", type=int, default=5)
    labels_parser.add_argument("--step", type=int, default=3)

    export_parser = subparsers.add_parser("export", help="Export LeRobot-style dataset")
    export_parser.add_argument("--labeled-csv", type=Path, required=True)
    export_parser.add_argument("--session-root", type=Path, required=True)
    export_parser.add_argument("--dataset-root", type=Path, required=True)
    export_parser.add_argument("--task-name", type=str, required=True)

    scaffold_parser = subparsers.add_parser("record-scaffold", help="Generate a scaffolded raw session")
    scaffold_parser.add_argument("--output-root", type=Path, required=True)
    scaffold_parser.add_argument("--session-id", type=str, default="go2_scaffold_0001")
    scaffold_parser.add_argument("--task-name", type=str, default="teleop collection")
    scaffold_parser.add_argument("--operator", type=str, default="operator")
    scaffold_parser.add_argument("--instruction", type=str, default="Describe the teleop task here.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "align":
        aligner = SessionAligner(max_delta_ns=args.max_delta_ms * 1_000_000)
        rows = aligner.align_session(args.session_root, args.output_csv)
        print(f"Aligned {len(rows)} rows -> {args.output_csv}")
        return

    if args.command == "build-labels":
        builder = FutureWaypointLabelBuilder(
            num_waypoints=args.num_waypoints,
            step=args.step,
        )
        rows = builder.build_from_csv(args.aligned_csv, args.output_csv)
        print(f"Labeled {len(rows)} rows -> {args.output_csv}")
        return

    if args.command == "export":
        exporter = LeRobotExporter()
        summary = exporter.export_from_csv(
            labeled_csv=args.labeled_csv,
            session_root=args.session_root,
            dataset_root=args.dataset_root,
            task_name=args.task_name,
        )
        print(f"Exported {summary['num_frames']} frames -> {summary['dataset_root']}")
        return

    if args.command == "record-scaffold":
        config = RecorderConfig(
            session_root=args.output_root,
            session_id=args.session_id,
            task_name=args.task_name,
            operator=args.operator,
            instruction=args.instruction,
        )
        recorder = TeleopRecorderScaffold(config=config)
        recorder.record_rgb_frame(1_000_000_000, "rgb_front/frame_000001.jpg", 1)
        recorder.record_depth_frame(1_005_000_000, "depth_front/frame_000001.png", 1)
        recorder.record_teleop(995_000_000, 0.3, 0.0, 0.02)
        recorder.record_odom(990_000_000, 0.0, 0.0, 0.0, 0.3)
        output_root = recorder.flush()
        print(f"Recorder scaffold written to {output_root}")
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
