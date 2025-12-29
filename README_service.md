# DH USB 摄像头录制服务使用说明

## 文件说明

- `capture_dh_usb_service.py` - 录制服务（后台运行）
- `capture_dh_usb_control.py` - 控制脚本（发送命令）

## 使用方法

### 1. 启动服务

```bash
# 前台运行（可以看到日志），使用默认频率 1秒
python3 capture_dh_usb_service.py

# 后台运行，使用默认频率 1秒
python3 capture_dh_usb_service.py &

# 指定录制频率（每 x 秒捕获一次）
python3 capture_dh_usb_service.py --interval 2    # 每2秒捕获一次
python3 capture_dh_usb_service.py -i 0.5          # 每0.5秒捕获一次
python3 capture_dh_usb_service.py -i 5            # 每5秒捕获一次

# 查看帮助
python3 capture_dh_usb_service.py --help
```

### 2. 发送命令

在另一个终端中使用控制脚本发送命令：

```bash
# 启动录制（命令1）
python3 capture_dh_usb_control.py start
# 或
python3 capture_dh_usb_control.py 1

# 停止录制（命令2）
python3 capture_dh_usb_control.py stop
# 或
python3 capture_dh_usb_control.py 2

# 查看服务状态
python3 capture_dh_usb_control.py status
```

### 3. 停止服务

```bash
# 方法1: 发送退出命令（如果服务在前台运行）
# 在服务终端输入: quit 或 exit

# 方法2: 通过PID文件停止
kill $(cat /tmp/dh_usb_camera_service.pid)

# 方法3: 查找进程并停止
pkill -f capture_dh_usb_service.py
```

## 录制说明

- **启动录制时**：服务会初始化摄像头、预热并等待曝光稳定（约3秒）
- **录制过程**：按照启动时设置的频率自动保存图像（默认每1秒一次）
- **录制频率**：在服务启动时通过 `--interval` 或 `-i` 参数设置，运行期间不可修改
- **保存位置**：图像保存在 `recordings/` 目录下
- **文件命名**：`dh_usb_YYYYMMDD_HHMMSS_mmm.jpg`（包含毫秒时间戳）

## 示例效果

以下是一张捕获的示例图像：

![捕获示例](images/dh_usb_image_20251229_082857.jpg)

## 注意事项

1. 确保摄像头未被其他程序占用
2. 服务使用命名管道 `/tmp/dh_usb_camera_service_pipe` 进行通信
3. PID文件保存在 `/tmp/dh_usb_camera_service.pid`
4. 录制前会自动预热摄像头，确保曝光正常