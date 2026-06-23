# Go2 Teleop LeRobot Tools

面向 Go2 真机遥操日志的最小离线工具包，目标是把松散原始日志整理成可复用的训练数据资产。

## 包含内容

- `schema.py`: 原始日志目录约定与校验
- `aligner.py`: 以 RGB 帧为主时轴，对齐 depth / teleop / odom / instruction
- `labels.py`: 生成未来局部 waypoint 标签
- `lerobot_export.py`: 导出 LeRobotDataset 风格目录与 `parquet` episode
- `recorder_scaffold.py`: 未来接 ROS2 / Unitree topic 的 recorder 骨架
- `cli.py`: 命令行入口

## 目录

```text
go2_teleop_lerobot_tools/
  docs/raw_log_schema.md
  examples/sample_session/
  src/go2_teleop_lerobot_tools/
```

## 快速开始

```bash
cd go2_teleop_lerobot_tools
python -m go2_teleop_lerobot_tools.cli align ^
  --session-root examples/sample_session ^
  --output-csv outputs/aligned.csv

python -m go2_teleop_lerobot_tools.cli build-labels ^
  --aligned-csv outputs/aligned.csv ^
  --output-csv outputs/aligned_labeled.csv ^
  --num-waypoints 4 ^
  --step 1

python -m go2_teleop_lerobot_tools.cli export ^
  --labeled-csv outputs/aligned_labeled.csv ^
  --session-root examples/sample_session ^
  --dataset-root outputs/lerobot_dataset ^
  --task-name "go2 hallway teleop"
```

## 迁移到目标目录

当前实现先落在工作区根目录的 `go2_teleop_lerobot_tools/`。后续可整体复制到：

`D:\desktop\routing\SII learning\prj_afterclass2`

## 后续接真机建议

1. 用 `recorder_scaffold.py` 替换 `iter_source()`，把数据源接到 ROS2 topic 或 Unitree SDK 回调。
2. 先保持输出字段名不变，避免后处理脚本改两遍。
3. 真机接入时优先保证 `timestamp_ns` 统一，离线对齐会更稳定。

## 当前导出格式说明

- 每个 episode 当前导出到 `data/chunk-000/episode_000000.parquet`
- `meta/` 下会生成 `episodes.jsonl`、`tasks.jsonl`、`info.json`、`episodes_stats.jsonl`
- `videos/` 下按 `chunk-000/<video_stem>/episode_000000.mp4` 组织
- 这一版已经比最初的 JSONL exporter 更贴近官方 `LeRobotDataset` 结构
