#!/usr/bin/env python3
"""
DH USB 摄像头图像捕获脚本
自动识别并捕获 DH USB 摄像头的图像，保存为 JPG 文件
"""

import cv2
import sys
import os
import subprocess
import time
import numpy as np
from datetime import datetime
from pathlib import Path


def find_dh_usb_camera():
    """
    查找 DH USB 摄像头设备
    返回设备路径（如 /dev/video2）或索引，如果未找到则返回 None
    """
    print("正在查找 DH USB 摄像头...")
    
    for dev in ['/dev/video0', '/dev/video1', '/dev/video2', '/dev/video3', 
               '/dev/video4', '/dev/video5', '/dev/video6', '/dev/video7']:
        if not os.path.exists(dev):
            continue
        
        try:
            cap = cv2.VideoCapture(dev)
            if not cap.isOpened():
                cap.release()
                continue
            
            ret, _ = cap.read()
            cap.release()
            if not ret:
                continue
            
            try:
                result = subprocess.run(
                    ['udevadm', 'info', '--query=all', '--name', dev],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if 'DH' in result.stdout or 'DH_USB' in result.stdout:
                    print(f"找到 DH USB 摄像头: {dev}")
                    return dev
            except:
                idx = int(dev.replace('/dev/video', ''))
                if idx in [2, 3, 4, 5]:
                    print(f"找到可用摄像头: {dev} (索引 {idx})，假设是 DH USB")
                    return dev
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            continue
    
    return None


def capture_dh_usb_image(output_path=None, warmup_seconds=3, warmup_frames=30, capture_frames=20, width=1920, height=1080, output_dir="captures"):
    """
    从 DH USB 摄像头捕获图像并保存为 JPG 文件
    
    参数:
        output_path: 输出文件路径，如果为 None 则使用时间戳命名
        warmup_seconds: 预热等待时间（秒），默认3秒
        warmup_frames: 预热帧数，默认30帧
        capture_frames: 捕获帧数（选择最亮的），默认20帧
        width: 图像宽度，默认1920（1080p）
        height: 图像高度，默认1080（1080p）
        output_dir: 输出文件夹，默认 "captures"
    """
    camera_device = find_dh_usb_camera()
    
    if camera_device is None:
        print("错误: 未找到 DH USB 摄像头")
        print("提示:")
        print("  1. 请检查 DH USB 摄像头是否已连接")
        print("  2. 检查设备权限: ls -la /dev/video*")
        print("  3. 检查用户是否在 video 组中: groups $USER")
        return False
    
    print(f"正在打开摄像头: {camera_device}")
    cap = cv2.VideoCapture(camera_device)
    
    if not cap.isOpened():
        print(f"错误: 无法打开摄像头 {camera_device}")
        print("提示: 摄像头可能被其他程序占用，或需要权限")
        return False
    
    print(f"设置分辨率: {width}x{height}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # 验证实际设置的分辨率（摄像头可能不支持请求的分辨率，会使用最接近的支持值）
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"实际分辨率: {actual_width}x{actual_height}")
    
    if actual_width != width or actual_height != height:
        print(f"注意: 摄像头不支持 {width}x{height}，已使用 {actual_width}x{actual_height}")
    
    try:
        # 设置自动曝光模式（1 = 自动模式）
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    except:
        pass
    
    # 预热摄像头：丢弃前几帧，让摄像头有时间调整曝光
    print(f"正在预热摄像头（调整曝光）...")
    print(f"  预热帧数: {warmup_frames}, 等待时间: {warmup_seconds}秒")
    for i in range(warmup_frames):
        ret, _ = cap.read()
        if not ret:
            break
        if (i + 1) % 10 == 0:
            print(f"  预热进度: {i + 1}/{warmup_frames} 帧")
    
    # 等待额外时间让曝光稳定（摄像头需要几秒钟来调整）
    print(f"等待曝光稳定 ({warmup_seconds}秒)...")
    time.sleep(warmup_seconds)
    
    # 再读取一些帧，选择亮度合适的帧
    print(f"正在捕获图像（读取 {capture_frames} 帧，选择最佳）...")
    best_frame = None
    best_brightness = 0
    
    for i in range(capture_frames):
        ret, frame = cap.read()
        if ret and frame is not None:
            # 计算图像平均亮度（转换为灰度图后计算均值）
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)
            
            # 选择最亮的帧（曝光调整好的帧通常更亮）
            if brightness > best_brightness:
                best_brightness = brightness
                best_frame = frame.copy()
    
    if best_frame is None:
        print("错误: 无法从摄像头读取图像")
        cap.release()
        return False
    
    frame = best_frame
    print(f"  捕获到最佳图像，平均亮度: {best_brightness:.1f}/255")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dh_usb_image_{timestamp}.jpg"
        output_path = os.path.join(output_dir, filename)
    else:
        if os.path.dirname(output_path) == '' or os.path.dirname(output_path) == '.':
            filename = os.path.basename(output_path)
            output_path = os.path.join(output_dir, filename)
    
    if not output_path.lower().endswith('.jpg') and not output_path.lower().endswith('.jpeg'):
        output_path += '.jpg'
    
    success = cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    if success:
        print(f"✓ 图像已成功保存到: {output_path}")
        print(f"  图像尺寸: {frame.shape[1]}x{frame.shape[0]}")
    else:
        print(f"错误: 无法保存图像到 {output_path}")
    
    cap.release()
    
    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='DH USB 摄像头图像捕获脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 capture_dh_usb.py
  python3 capture_dh_usb.py output.jpg
  python3 capture_dh_usb.py --warmup-seconds 5 output.jpg
  python3 capture_dh_usb.py --resolution 1920x1080 output.jpg
  python3 capture_dh_usb.py --output-dir my_images output.jpg
        """
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        default=None,
        help='输出文件名（可选）'
    )
    
    parser.add_argument(
        '--warmup-seconds',
        type=float,
        default=3,
        help='预热等待时间（秒），默认 3'
    )
    
    parser.add_argument(
        '--warmup-frames',
        type=int,
        default=30,
        help='预热帧数，默认 30'
    )
    
    parser.add_argument(
        '--capture-frames',
        type=int,
        default=20,
        help='捕获帧数，默认 20'
    )
    
    parser.add_argument(
        '--resolution',
        type=str,
        default='1920x1080',
        help='分辨率，默认 1920x1080 (1080p)，例如: 1920x1080, 1280x720, 640x480'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='captures',
        help="输出文件夹，默认 'captures'，所有图像将保存到此文件夹中"
    )
    
    args = parser.parse_args()
    
    if args.output_file and args.output_file.startswith('/dev/video'):
        print("错误: 输出文件名不能是设备路径")
        sys.exit(1)
    
    try:
        if 'x' in args.resolution:
            width, height = map(int, args.resolution.split('x'))
        elif 'X' in args.resolution:
            width, height = map(int, args.resolution.split('X'))
        else:
            raise ValueError("分辨率格式应为 WIDTHxHEIGHT")
    except ValueError:
        print(f"错误: 无效的分辨率格式 '{args.resolution}'，应为 WIDTHxHEIGHT (例如: 1920x1080)")
        sys.exit(1)
    
    success = capture_dh_usb_image(
        args.output_file,
        args.warmup_seconds,
        args.warmup_frames,
        args.capture_frames,
        width,
        height,
        args.output_dir
    )
    sys.exit(0 if success else 1)

