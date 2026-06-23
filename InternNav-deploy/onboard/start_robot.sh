#!/bin/bash

# ================= CONFIGURATION =================
# set the network interface connected to the robot default: eth0
ROBOT_IF="eno1"
# =================================================

# Function to kill all background processes when Ctrl+C is pressed
cleanup() {
    echo ""
    echo "========================================="
    echo "   Stopping all robot modules..."
    echo "========================================="
    kill 0
    exit
}

# Trap SIGINT (Ctrl+C) to run the cleanup function
trap cleanup SIGINT

echo "========================================="
echo "   Launching OpenLegged Robot System"
echo "========================================="
echo "   Target Interface: $ROBOT_IF"
echo "========================================="

# 1. Start the Unitree Driver (Bottom Layer)
# We pass the interface variable ($ROBOT_IF) to the python script
echo "[1/4] Starting Unitree Driver..."
python3 unitree_driver.py "$ROBOT_IF" &
PID_DRIVER=$!
sleep 3  # Wait for the robot to stand up

# 2. Start the ROS Bridge
echo "[2/4] Starting ROS Bridge..."
python3 ros_bridge.py &
PID_BRIDGE=$!
sleep 1

# 3. Start Go2 Camera Publisher (RGB + synthetic depth)
echo "[3/4] Starting Go2 Camera Publisher..."
if [ -f "go2_camera_publisher.py" ]; then
    python3 go2_camera_publisher.py "$ROBOT_IF" &
    PID_CAMERA=$!
else
    echo "[Warning] go2_camera_publisher.py not found, skipping."
fi

sleep 2

# 4. Start Sport State Publisher (DDS odom → ROS2 /odom_bridge)
echo "[4/4] Starting Sport State Publisher..."
if [ -f "sport_state_publisher.py" ]; then
    python3 sport_state_publisher.py "$ROBOT_IF" &
    PID_SPORT_STATE=$!
else
    echo "[Warning] sport_state_publisher.py not found. Odom may not be available."
fi

echo "========================================="
echo "   All Systems GO! Press Ctrl+C to stop."
echo "========================================="

# Keep the script running to maintain the trap
wait
