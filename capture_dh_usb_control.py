#!/usr/bin/env python3
"""
DH USB 摄像头录制服务控制脚本
用于向服务发送命令
"""

import sys
import os

command_pipe_path = "/tmp/dh_usb_camera_service_pipe"
service_pid_file = "/tmp/dh_usb_camera_service.pid"


def send_command(command):
    """
    向服务发送命令
    """
    if not os.path.exists(command_pipe_path):
        print(f"错误: 服务未运行（找不到命令管道: {command_pipe_path}）")
        print("提示: 请先启动服务: python3 capture_dh_usb_service.py")
        return False
    
    try:
        # 打开管道写入命令
        with open(command_pipe_path, 'w') as pipe:
            pipe.write(command + '\n')
            pipe.flush()
        return True
    except Exception as e:
        print(f"错误: 无法发送命令: {e}")
        return False


def check_service_running():
    """
    检查服务是否运行
    """
    if not os.path.exists(service_pid_file):
        return False
    
    try:
        with open(service_pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # 检查进程是否存在
        os.kill(pid, 0)  # 发送信号0，不杀死进程，只检查是否存在
        return True
    except (OSError, ValueError):
        return False


def main():
    """
    主函数
    """
    if len(sys.argv) < 2:
        print("用法: python3 capture_dh_usb_control.py <命令>")
        print("")
        print("命令:")
        print("  start  或  1  - 启动录制")
        print("  stop   或  2  - 停止录制")
        print("  status        - 查看服务状态")
        print("")
        print("示例:")
        print("  python3 capture_dh_usb_control.py start")
        print("  python3 capture_dh_usb_control.py stop")
        print("  python3 capture_dh_usb_control.py 1")
        print("  python3 capture_dh_usb_control.py 2")
        sys.exit(1)
    
    command = sys.argv[1].strip().lower()
    
    # 命令映射
    command_map = {
        "1": "1",
        "start": "1",
        "2": "2",
        "stop": "2",
        "status": "status"
    }
    
    if command not in command_map:
        print(f"错误: 未知命令 '{command}'")
        print("可用命令: start/1, stop/2, status")
        sys.exit(1)
    
    # 检查服务是否运行
    if not check_service_running():
        print("错误: 服务未运行")
        print("提示: 请先启动服务: python3 capture_dh_usb_service.py &")
        sys.exit(1)
    
    # 发送命令
    actual_command = command_map[command]
    if send_command(actual_command):
        if command == "status":
            print("状态查询已发送")
        elif command in ["1", "start"]:
            print("启动录制命令已发送")
        elif command in ["2", "stop"]:
            print("停止录制命令已发送")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

