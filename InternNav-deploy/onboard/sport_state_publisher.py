#!/usr/bin/env python3
"""
sport_state_publisher.py — DDS SportModeState_ → ROS2 /odom_bridge
===================================================================
Go2 机器人没有激光雷达 SLAM 时，/utlidar/robot_odom 话题不存在，
原 ros_bridge.py 依赖该话题来产生 /odom_bridge，导致 http_internvla_client.py
收不到里程计。

本节点直接从 DDS 订阅 rt/lf/sportmodestate 获取机器人位姿和速度，
转换为 nav_msgs/Odometry 后发布到 /odom_bridge，替代缺失的 LiDAR odom。
"""

import sys
import math

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Pose, Quaternion, Twist, Vector3
from std_msgs.msg import Header

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_

# DDS 运动状态话题
TOPIC_SPORTMODE_STATE = "rt/lf/sportmodestate"


class SportStatePublisher(Node):
    def __init__(self, network_interface: str = "eth0"):
        super().__init__("sport_state_publisher")

        # 发布 /odom_bridge
        self.odom_pub = self.create_publisher(Odometry, "/odom_bridge", 10)

        # 初始化 DDS 通道
        ChannelFactoryInitialize(0, network_interface)

        # 订阅 DDS sport mode state
        self.subscriber = ChannelSubscriber(TOPIC_SPORTMODE_STATE, SportModeState_)
        self.subscriber.Init(self._state_handler, 10)

        self.get_logger().info(
            f"Sport State Publisher started on iface={network_interface}. "
            f"Publishing DDS SportModeState_ -> /odom_bridge"
        )

    def _state_handler(self, msg: SportModeState_):
        """
        DDS 回调：将 SportModeState_ 转为 Odometry 并发布。
        """
        odom = Odometry()
        odom.header = Header()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"

        # position: [x, y, z] in world frame
        px, py, pz = msg.position[0], msg.position[1], msg.position[2]

        # orientation: 从 yaw_speed 和 IMU rpy 推算
        # SportModeState_ 包含 imu_state.rpy = [roll, pitch, yaw]
        roll = msg.imu_state.rpy[0]
        pitch = msg.imu_state.rpy[1]
        yaw = msg.imu_state.rpy[2]

        half_yaw = yaw * 0.5
        qz = math.sin(half_yaw)
        qw = math.cos(half_yaw)

        odom.pose.pose = Pose(
            position=Point(x=px, y=py, z=pz),
            orientation=Quaternion(x=0.0, y=0.0, z=qz, w=qw),
        )

        # velocity: [vx, vy, vz] in body frame
        vx = msg.velocity[0]
        vy = msg.velocity[1]
        yaw_speed = msg.yaw_speed

        odom.twist.twist = Twist(
            linear=Vector3(x=vx, y=vy, z=0.0),
            angular=Vector3(x=0.0, y=0.0, z=yaw_speed),
        )

        self.odom_pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)

    network_if = "eth0"
    if len(sys.argv) > 1:
        network_if = sys.argv[1]

    node = SportStatePublisher(network_interface=network_if)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()