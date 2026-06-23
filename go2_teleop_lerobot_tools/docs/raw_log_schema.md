# Raw Log Schema

## 目标

定义一套与具体运行时弱耦合的原始日志目录约定，保证第一版离线工具可以独立工作。

## 目录结构

```text
session_root/
  session_meta.json
  instruction.json
  teleop_cmd.csv
  odom.csv
  rgb_front.csv
  depth_front.csv
  rgb_front/
    frame_000001.jpg
  depth_front/
    frame_000001.png
  videos/
    front.mp4
```

## 文件说明

### `session_meta.json`

```json
{
  "session_id": "go2_demo_0001",
  "robot_name": "Go2",
  "operator": "student_a",
  "task_name": "follow corridor",
  "instruction_file": "instruction.json",
  "rgb_index_file": "rgb_front.csv",
  "depth_index_file": "depth_front.csv",
  "teleop_file": "teleop_cmd.csv",
  "odom_file": "odom.csv",
  "video_files": ["videos/front.mp4"]
}
```

### `instruction.json`

```json
{
  "text": "Walk forward and turn left at the end of the corridor."
}
```

### `rgb_front.csv`

必需列：

- `timestamp_ns`
- `file_path`
- `frame_id`

### `depth_front.csv`

必需列：

- `timestamp_ns`
- `file_path`
- `frame_id`

### `teleop_cmd.csv`

必需列：

- `timestamp_ns`
- `vx`
- `vy`
- `yaw_rate`

### `odom.csv`

必需列：

- `timestamp_ns`
- `pose_x`
- `pose_y`
- `yaw`
- `linear_speed`

可选列：

- `pose_z`
- `quat_x`
- `quat_y`
- `quat_z`
- `quat_w`

## 对齐策略

- 以 RGB 帧时间轴作为主序列。
- 其它流通过最近邻时间戳对齐到 RGB 帧。
- 超过阈值的样本视为缺失并报错，默认阈值 `100 ms`。

## 标签策略

- 第一版默认生成 `future_waypoints_local[K,2]`
- 同时保留遥操动作 `action.teleop_cmd = [vx, vy, yaw_rate]`
- waypoint 由未来 odom 轨迹在当前机器人坐标系下转换得到

## 导出约定

- 对齐后的中间产物使用 CSV，便于肉眼检查
- 最终导出到 LeRobot 风格目录时，episode 文件写为 `parquet`
- 第一版固定导出单 chunk：`data/chunk-000/episode_000000.parquet`
