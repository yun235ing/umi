# umi

原版 Universal Manipulation Interface（UMI）的云端学习和复现项目。第一阶段从读代码、核对数据流和小规模 CPU 测试开始。

## 在云端运行

在 Codex 云端打开本仓库，在仓库根目录运行：

```bash
bash scripts/bootstrap.sh
.venv/bin/python scripts/smoke_test.py
```

初始化脚本会按提交哈希下载原版 UMI 和 ExifTool，在 `.venv/` 中安装锁定版本的 Python 依赖。重复运行会复用已有的源码和虚拟环境。测试用的是脚本现场生成的 1 秒 ArUco 视频，结果在 `runs/smoke-*/`。每次测试会新建一个目录。

本环境使用 Linux x86_64、Python 3.12、Git、Perl 和带 `libx264` 的 FFmpeg。当前默认云端已经有这些系统命令。如果换了镜像，先用镜像的工具管理器补缺。在 Debian 或 Ubuntu 上，有管理员权限时可用 `apt-get install git perl ffmpeg`。当 `python3` 指向其他版本时，可以运行 `UMI_PYTHON=python3.12 bash scripts/bootstrap.sh`。标准库的 `venv` 也须可用。

系统提供的 FFmpeg 和 FFprobe 用于生成或检查视频，原版 UMI 代码使用 PyAV 读视频。Python 环境包含 OpenCV Contrib Headless、NumPy、SciPy、pandas、PyExifTool、Zarr 2 和用于 JPEG XL 的 imagecodecs。官方 README 记录的完整环境基于 Ubuntu 22.04 / Python 3.9，并包含 Docker、CUDA 版 PyTorch 和仿真依赖。当前方案用于学习和离线处理的第一阶段。完整 SLAM 复现需要另行准备 OpenICC、ORB-SLAM3 容器和对应的真实采集数据。

[原版 README](https://github.com/real-stanford/universal_manipulation_interface/blob/d095ba9590df789df5189eea5ee7e431689038a6/README.md) · [官方 Conda 配置](https://github.com/real-stanford/universal_manipulation_interface/blob/d095ba9590df789df5189eea5ee7e431689038a6/conda_environment.yaml)

## 按文件追踪数据流

原版代码在 `upstream/universal_manipulation_interface/`。先看总入口 `run_slam_pipeline.py`，再对照下面的脚本和产物。总入口调用到 06，导出训练数据需要单独运行 07。

| 阶段 | 输入 | 主要产物 |
| --- | --- | --- |
| `00_process_videos.py` | GoPro 原始视频、时间码、相机序列号 | 整理好的 `demos/*/raw_video.mp4` |
| `01_extract_gopro_imu.py` | 整理后的 GoPro 视频 | `imu_data.json` |
| `02_create_map.py` | 建图片和该片 IMU | `map_atlas.osa`、建图片轨迹 |
| `03_batch_slam.py` | 地图、视频、IMU | 各片段的 `camera_trajectory.csv` |
| `04_detect_aruco.py` | 视频、相机内参、标签尺寸配置 | 每帧的 `tag_detection.pkl` |
| `05_run_calibrations.py` | 标签检测、建图片轨迹、夹爪标定片 | `tx_slam_tag.json`、`gripper_range.json` |
| `06_generate_dataset_plan.py` | 视频时间码、轨迹、标签检测和标定结果 | `dataset_plan.pkl`，包含对齐后的片段、TCP 位姿和夹爪宽度 |
| `07_generate_replay_buffer.py` | 视频、标签检测和数据集计划 | `dataset.zarr.zip` |

测试使用原版 04 检测标签，按 06 的输出结构生成一份合成计划，再使用原版 07 导出压缩数据。运行后可以在生成目录里对应查看 `tag_detection.pkl`、`dataset_plan.pkl` 和 `dataset.zarr.zip`。其中位姿和夹爪宽度由测试脚本生成。原版 00 会移动视频并留下符号链接，用实验视频尝试时请在原片副本上运行。

## 跨电脑继续

用同一 ChatGPT 账号打开原云端会话，可以继续这次工作。要开新任务并复用依赖，在网页版 **Settings → Codex Cloud → Environments → Create environment**，或在新任务的 **Work in → Cloud → Create environment** 中选择 `yun235ing/umi`，名称填 `umi`。配置启用 **Package manager domains**，安装脚本使用 `bash scripts/bootstrap.sh`。设置过程中可让 Codex 执行 `.venv/bin/python scripts/smoke_test.py` 进行检查，通过后保存并发布环境。以后在另一台电脑选择这个已发布的环境即可。

提交 [PROGRESS.md](PROGRESS.md) 和实验脚本的小改动后，新任务也能从相同记录接着做。该仓库公开，适合记录可公开的学习内容。`data/`、`runs/`、`upstream/`、`.tools/` 和 `.venv/` 不跟踪。

[Codex Cloud 环境设置说明](https://learn.chatgpt.com/docs/environments/cloud-environments)
