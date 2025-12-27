#!/usr/bin/env python3
"""
DH USB 摄像头录制服务
后台运行，接收命令进行录制控制
命令1: 启动录制
命令2: 停止录制
"""

import cv2
import sys
import os
import subprocess
import time
import numpy as np
import signal
import threading
from datetime import datetime
from pathlib import Path


# 全局变量
recording = False
recording_thread = None
camera_device = None
cap = None
command_pipe_path = "/tmp/dh_usb_camera_service_pipe"
service_pid_file = "/tmp/dh_usb_camera_service.pid"
# 录制频率（秒），启动时设置，运行期间不修改
recording_interval = 1.0


def find_dh_usb_camera():
    """
    查找 DH USB 摄像头设备
    返回设备路径（如 /dev/video2），如果未找到则返回 None
    """
    print("正在查找 DH USB 摄像头...")
    
    # 方法1: 通过 udevadm 查找
    try:
        for dev in ['/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3', 
                   '/dev/video4', '/dev/video5', '/dev/video6', '/dev/video7']:
            if not os.path.exists(dev):
                continue
                
            try:
                result = subprocess.run(
                    ['udevadm', 'info', '--query=all', '--name', dev],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                # 检查是否包含 DH USB 相关信息
                if 'DH' in result.stdout or 'DH_USB' in result.stdout:
                    # 验证这个设备是否可以打开
                    test_cap = cv2.VideoCapture(dev)
                    if test_cap.isOpened():
                        ret, _ = test_cap.read()
                        test_cap.release()
                        if ret:
                            print(f"找到 DH USB 摄像头: {dev}")
                            return dev
                    test_cap.release()
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                continue
    except Exception as e:
        print(f"使用 udevadm 查找时出错: {e}")
    
    # 方法2: 尝试常见的 DH USB 设备索引（通常是 video2 或 video3）
    print("尝试通过设备索引查找...")
    for idx in [2, 3, 4, 5]:
        dev = f'/dev/video{idx}'
        if os.path.exists(dev):
            test_cap = cv2.VideoCapture(idx)
            if test_cap.isOpened():
                ret, _ = test_cap.read()
                test_cap.release()
                if ret:
                    # 再次验证是否是 DH USB
                    try:
                        result = subprocess.run(
                            ['udevadm', 'info', '--query=all', '--name', dev],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if 'DH' in result.stdout or 'DH_USB' in result.stdout:
                            print(f"找到 DH USB 摄像头: {dev} (索引 {idx})")
                            return idx
                    except:
                        print(f"找到可用摄像头: {dev} (索引 {idx})，假设是 DH USB")
                        return idx
            test_cap.release()
    
    return None


def initialize_camera(width=1920, height=1080, warmup_seconds=3, warmup_frames=30):
    """
    初始化摄像头并预热
    """
    global camera_device, cap
    
    if camera_device is None:
        camera_device = find_dh_usb_camera()
        if camera_device is None:
            print("错误: 未找到 DH USB 摄像头")
            return False
    
    print(f"正在打开摄像头: {camera_device}")
    cap = cv2.VideoCapture(camera_device)
    
    if not cap.isOpened():
        print(f"错误: 无法打开摄像头 {camera_device}")
        return False
    
    print(f"设置分辨率: {width}x{height}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"实际分辨率: {actual_width}x{actual_height}")
    
    # 尝试启用自动曝光
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    except:
        pass
    
    print(f"正在预热摄像头（调整曝光）...")
    print(f"  预热帧数: {warmup_frames}, 等待时间: {warmup_seconds}秒")
    for i in range(warmup_frames):
        ret, _ = cap.read()
        if not ret:
            break
        if (i + 1) % 10 == 0:
            print(f"  预热进度: {i + 1}/{warmup_frames} 帧")
    
    print(f"等待曝光稳定 ({warmup_seconds}秒)...")
    time.sleep(warmup_seconds)
    
    print("摄像头初始化完成，准备录制")
    return True


def close_camera():
    """
    关闭摄像头
    """
    global cap
    if cap is not None:
        cap.release()
        cap = None
        print("摄像头已关闭")


def save_image(frame, output_dir="recordings"):
    """
    保存图像到文件
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"dh_usb_{timestamp}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    success = cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    if success:
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] 保存: {filename}")
    else:
        print(f"  错误: 无法保存图像到 {filepath}")
    
    return success


def recording_loop(output_dir="recordings", interval=1.0):
    """
    录制循环：每隔指定时间保存一帧图像
    """
    global recording, cap
    
    print(f"开始录制，保存目录: {output_dir}")
    print(f"录制间隔: {interval}秒")
    
    frame_count = 0
    last_save_time = time.time()
    
    while recording:
        if cap is None or not cap.isOpened():
            print("错误: 摄像头未打开")
            break
        
        ret, frame = cap.read()
        
        if ret and frame is not None:
            current_time = time.time()
            
            # 每隔指定时间保存一次
            if current_time - last_save_time >= interval:
                save_image(frame, output_dir)
                last_save_time = current_time
                frame_count += 1
        else:
            print("警告: 无法读取摄像头帧")
            time.sleep(0.1)
    
    print(f"录制已停止，共保存 {frame_count} 帧图像")
    close_camera()


def start_recording(output_dir="recordings", interval=1.0, width=1920, height=1080, 
                   warmup_seconds=3, warmup_frames=30):
    """
    启动录制
    """
    global recording, recording_thread
    
    if recording:
        print("录制已在运行中")
        return False
    
    print("准备启动录制...")
    
    if not initialize_camera(width, height, warmup_seconds, warmup_frames):
        return False
    
    # 启动录制线程
    recording = True
    recording_thread = threading.Thread(
        target=recording_loop,
        args=(output_dir, interval),
        daemon=True
    )
    recording_thread.start()
    print("录制已启动")
    return True


def stop_recording():
    """
    停止录制
    """
    global recording
    
    if not recording:
        print("录制未在运行")
        return False
    
    print("正在停止录制...")
    recording = False
    
    # 等待录制线程结束
    if recording_thread is not None:
        recording_thread.join(timeout=5)
    
    print("录制已停止")
    return True


def signal_handler(signum, frame):
    """
    信号处理：优雅退出
    """
    print(f"\n收到信号 {signum}，正在退出...")
    stop_recording()
    close_camera()
    # 清理管道和PID文件
    if os.path.exists(command_pipe_path):
        os.remove(command_pipe_path)
    if os.path.exists(service_pid_file):
        os.remove(service_pid_file)
    sys.exit(0)


def command_listener(interval=1.0):
    """
    命令监听循环
    
    参数:
        interval: 录制频率（秒），默认1.0秒
    """
    global recording_interval
    recording_interval = interval
    
    # 创建命名管道
    if os.path.exists(command_pipe_path):
        os.remove(command_pipe_path)
    
    os.mkfifo(command_pipe_path)
    print(f"服务已启动，监听命令管道: {command_pipe_path}")
    print(f"录制频率: {interval}秒/帧")
    print("等待命令...")
    
    while True:
        try:
            # 打开管道读取命令（阻塞等待）
            with open(command_pipe_path, 'r') as pipe:
                command = pipe.read().strip()
                
            if not command:
                continue
            
            print(f"\n收到命令: {command}")
            
            if command == "1" or command.lower() == "start":
                start_recording(interval=recording_interval)
            elif command == "2" or command.lower() == "stop":
                stop_recording()
            elif command.lower() == "status":
                if recording:
                    print("状态: 正在录制")
                else:
                    print("状态: 未录制")
            elif command.lower() == "quit" or command.lower() == "exit":
                print("收到退出命令")
                stop_recording()
                break
            else:
                print(f"未知命令: {command}")
                print("可用命令: 1/start (启动录制), 2/stop (停止录制), status (状态), quit/exit (退出)")
        
        except Exception as e:
            print(f"处理命令时出错: {e}")
            time.sleep(0.1)


def main():
    """
    主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='DH USB 摄像头录制服务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 capture_dh_usb_service.py                    # 使用默认频率 1秒
  python3 capture_dh_usb_service.py --interval 2       # 每2秒捕获一次
  python3 capture_dh_usb_service.py -i 0.5              # 每0.5秒捕获一次
        """
    )
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=1.0,
        help='录制频率（秒），即每隔多少秒捕获一次图像，默认 1.0 秒'
    )
    
    args = parser.parse_args()
    
    if args.interval <= 0:
        print("错误: 录制频率必须大于 0")
        sys.exit(1)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 保存PID
    with open(service_pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    print("=" * 50)
    print("DH USB 摄像头录制服务")
    print("=" * 50)
    print(f"录制频率: {args.interval}秒/帧")
    print("命令:")
    print("  1 或 start  - 启动录制")
    print("  2 或 stop   - 停止录制")
    print("  status      - 查看状态")
    print("  quit/exit   - 退出服务")
    print("=" * 50)
    
    try:
        command_listener(interval=args.interval)
    finally:
        # 清理
        stop_recording()
        close_camera()
        if os.path.exists(command_pipe_path):
            os.remove(command_pipe_path)
        if os.path.exists(service_pid_file):
            os.remove(service_pid_file)
        print("服务已退出")


if __name__ == "__main__":
    main()

