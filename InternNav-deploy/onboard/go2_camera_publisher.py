#!/usr/bin/env python3
"""
在 onboard/ 目录下新建文件 go2_camera_publisher.py
Go2 原生 RGB 相机 ROS2 发布节点
使用 unitree_sdk2py 采集图像并发布到 /camera/camera/color/image_raw
同时发布虚拟深度图（uint16全零），以疏通 ApproximateTimeSynchronizer
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
import numpy as np
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.video.video_client import VideoClient


class Go2CameraPublisher(Node):
    def __init__(self, network_interface="eth0"):
        super().__init__('go2_camera_publisher')

        # 参数声明
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30)

        self.width = self.get_parameter('width').value
        self.height = self.get_parameter('height').value
        self.fps = self.get_parameter('fps').value

        # 创建 RGB 图像发布器（话题名与原来保持一致）
        self.rgb_publisher = self.create_publisher(
            Image, '/camera/camera/color/image_raw', 10
        )
        # 相机内参信息发布器（话题名与原来保持一致）
        self.rgb_info_publisher = self.create_publisher(
            CameraInfo, '/camera/camera/color/camera_info', 10
        )

        # === 新增：发布虚拟深度图 ===
        # http_internvla_client.py 使用 ApproximateTimeSynchronizer 同步 RGB+深度，
        # 若 /camera/camera/aligned_depth_to_color/image_raw 无数据，同步器永远不会触发回调。
        # Go2 原生相机没有深度传感器，因此发布一张全零 uint16 深度图以疏通流水线。
        self.depth_publisher = self.create_publisher(
            Image, '/camera/camera/aligned_depth_to_color/image_raw', 10
        )
        # === 新增结束 ===

        self.bridge = CvBridge()
        self.network_interface = network_interface

        # 初始化 Unitree SDK 视频客户端
        self._init_camera()

        # 定时器回调（按 FPS 采集）
        timer_period = 1.0 / self.fps
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.get_logger().info(
            f'Go2 camera publisher initialized: {self.width}x{self.height}@{self.fps}fps '
            f'(RGB + synthetic depth)'
        )

    def _init_camera(self):
        """初始化 Go2 相机连接"""
        try:
            # 初始化通道（使用指定的网络接口）
            ChannelFactoryInitialize(0, self.network_interface)
            self.client = VideoClient()
            self.client.SetTimeout(3.0)
            self.client.Init()
            self.get_logger().info('Go2 camera connected successfully')
        except Exception as e:
            self.get_logger().error(f'Go2 camera initialization failed: {e}')
            self.client = None

    def timer_callback(self):
        """主循环：采集图像并发布"""
        if self.client is None:
            # 尝试重连
            self.get_logger().warn('Camera client not available, reconnecting...')
            self._init_camera()
            return

        try:
            code, data = self.client.GetImageSample()
            if code != 0:
                self.get_logger().warn(f'Get image failed with code: {code}')
                return

            # 将数据转换为 OpenCV 图像
            image_data = np.frombuffer(bytes(data), dtype=np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

            if image is None:
                self.get_logger().warn('Failed to decode image')
                return

            # 调整图像尺寸（如果需要）
            if image.shape[1] != self.width or image.shape[0] != self.height:
                image = cv2.resize(image, (self.width, self.height))

            # 发布 RGB 图像
            current_time_msg = self.get_clock().now().to_msg()
            rgb_msg = self.bridge.cv2_to_imgmsg(image, encoding='bgr8')
            rgb_msg.header.stamp = current_time_msg
            rgb_msg.header.frame_id = 'camera_color_optical_frame'
            self.rgb_publisher.publish(rgb_msg)

            # 发布虚拟深度图（固定常数值=2.0m，时间戳与 RGB 一致以触发同步器）
            fake_depth = np.full((self.height, self.width), 2000, dtype=np.uint16)
            depth_msg = self.bridge.cv2_to_imgmsg(fake_depth, encoding='mono16')
            depth_msg.header.stamp = current_time_msg
            depth_msg.header.frame_id = 'camera_depth_optical_frame'
            self.depth_publisher.publish(depth_msg)

            # 发布相机内参
            camera_info = self._create_camera_info()
            camera_info.header.stamp = current_time_msg
            camera_info.header.frame_id = 'camera_color_optical_frame'
            self.rgb_info_publisher.publish(camera_info)

        except Exception as e:
            self.get_logger().error(f'Error during frame capture: {e}')
            # 发生错误时重置客户端，下次重连
            self.client = None

    def _create_camera_info(self):
        """创建 CameraInfo 消息（近似内参，建议实际标定后替换）"""
        info = CameraInfo()
        info.width = self.width
        info.height = self.height
        # 近似内参矩阵（焦距和光心根据实际镜头调整）
        fx = self.width * 0.5
        fy = self.height * 0.5
        cx = self.width * 0.5
        cy = self.height * 0.5
        info.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]  # 假设无畸变
        info.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        return info

    def destroy_node(self):
        """节点销毁时释放资源"""
        if hasattr(self, 'client') and self.client:
            self.client = None
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    # 从命令行参数获取网络接口（与 start_robot.sh 保持一致）
    network_if = "eth0"
    if len(sys.argv) > 1:
        network_if = sys.argv[1]

    node = Go2CameraPublisher(network_interface=network_if)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Critical Error: {e}')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()