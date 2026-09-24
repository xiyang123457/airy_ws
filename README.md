# airy_ws

RoboSense AIRY 激光雷达 ROS2 驱动的容器化开发环境，基于 ROS2 Humble。

三个配置文件各管一层，职责清晰：

| 文件 | 职责 |
|---|---|
| `.devcontainer/Dockerfile` | 环境里有什么（依赖、ROS2、编译工具） |
| `.devcontainer/docker-compose.yml` | 容器怎么运行（构建、挂载、网络、常驻） |
| `.devcontainer/devcontainer.json` | VS Code 怎么接入容器 |

## 目录结构

```
airy_ws/
├── .devcontainer/
│   ├── Dockerfile              # 环境镜像
│   ├── docker-compose.yml      # 容器编排
│   └── devcontainer.json       # VS Code 接入
├── .dockerignore
├── src/
│   ├── rslidar_sdk/            # 驱动主包（内含 src/rs_driver 子模块）
│   └── rslidar_msg/            # 雷达消息定义包
└── README.md
```

## 环境要求

- Docker 与 Docker Compose v2
- 宿主 Ubuntu 22.04（Windows 亦可，注意事项见文末）

## 一、构建与启动

```bash
# 构建镜像（首次较慢，取决于网络与机器性能）
docker compose -f .devcontainer/docker-compose.yml build

# 后台启动容器
docker compose -f .devcontainer/docker-compose.yml up -d

# 进入容器
docker exec -it airy_ros2 bash
```

## 二、VS Code 进入 Dev Container

1. 安装扩展 `Dev Containers`
2. 用 VS Code 打开 `airy_ws` 目录
3. `Ctrl+Shift+P` → `Dev Containers: Reopen in Container`

`devcontainer.json` 直接复用 `docker-compose.yml` 中的 `airy` 服务，不会另建一套容器环境。

## 三、编译

进入容器后：

```bash
cd /workspace
source /opt/ros/humble/setup.bash
colcon build --symlink-install --parallel-workers $(nproc)
source install/setup.bash
```

`rslidar_sdk` 强依赖 `src/rs_driver` 子模块。若该目录为空，编译必然失败。

## 四、运行雷达

ROS2 各版本的 launch 文件格式不同，仓库同时提供 `start.py` 与 `humble_start.py`。
本项目使用 Humble，请指定对应版本：

```bash
ros2 launch rslidar_sdk humble_start.py
```

按实际雷达修改 `src/rslidar_sdk/config/config.yaml`：

| 参数 | 说明 |
|---|---|
| `lidar_type` | 雷达型号，如 `RSAIRY`（本项目 AIRY）、`RSHELIOS`、`RS128`（默认 `RSM1`） |
| `msop_port` | 点云数据端口，默认 `6699` |
| `difop_port` | 设备信息端口，默认 `7788` |
| `host_address` | 本机接收 IP |
| `group_address` | 组播地址（单播时留空） |

## 五、查看点云

```bash
rviz2
```

添加 `PointCloud2`，Topic 选择 `/rslidar_points`，Fixed Frame 设为 `rslidar`。

默认基础镜像 `ros:humble-ros-base` 不含 rviz2，先在容器内装上：

```bash
apt-get update && apt-get install -y ros-humble-rviz2
```

或者直接用自带 rviz2 的镜像重建，见第七节。

## 六、宿主网络调优（重要）

驱动会把 `SO_RCVBUF` 设到 4MB 以上，而 Ubuntu 22.04 默认 `net.core.rmem_max=212992`，
内核会静默截断，表现为丢包、帧率下降。**在宿主机上执行**：

```bash
sudo sysctl -w net.core.rmem_max=8388608
```

永久生效：

```bash
echo "net.core.rmem_max=8388608" | sudo tee -a /etc/sysctl.conf
```

## 七、切换基础镜像

默认 `ros:humble-ros-base`，任务书指定的最小版，只含 ROS2 核心。需要 rviz2 可视化时：

```bash
docker compose -f .devcontainer/docker-compose.yml build \
  --build-arg BASE_IMAGE=osrf/ros:humble-desktop-full
```

注意 `osrf/ros` 仓库只有 `humble-desktop`、`humble-desktop-full`、`humble-simulation` 等 tag，
没有 `humble-ros-base`。最小版必须写官方镜像 `ros:humble-ros-base`，不带 `osrf/` 前缀；
写成 `osrf/ros:humble-ros-base` 会在拉取阶段报 403 Forbidden 导致构建失败。

## 八、二阶段：构建期自动编译

默认关闭。开启后 `docker build` 阶段即完成 `colcon build`，任一包编译失败则构建中断：

```bash
docker compose -f .devcontainer/docker-compose.yml build --build-arg BUILD_WORKSPACE=true
```

产物固化在镜像的 `/opt/airy/install`，开终端自动 source。

## 九、Windows 注意事项

Windows 上 Docker Desktop 的 `network_mode: host` 实际是 WSL2 的虚拟网络，
物理网卡收到的雷达 UDP 广播可能进不了容器。若收不到数据，改为桥接 + 端口映射：

```yaml
    # 注释掉 network_mode: host，改用：
    ports:
      - "6699:6699/udp"
      - "7788:7788/udp"
```

## 十、常见问题

| 现象 | 原因与处理 |
|---|---|
| 找不到 `rs_driver` | `src/rs_driver` 子模块为空，需重新拉取 |
| 找不到 `yaml-cpp` | 缺 `libyaml-cpp-dev`（Dockerfile 已安装） |
| 收不到点云 | 检查防火墙、IP/端口配置、`rmem_max`、host 网络 |
| `ros2: command not found` | 未加载环境：`source /opt/ros/humble/setup.bash` |
| `colcon: command not found` | 缺 `python3-colcon-common-extensions`（Dockerfile 已安装） |

## 十一、获取驱动源码

若 `src/` 下还没有驱动源码，执行：

```bash
cd airy_ws/src
git clone --recursive https://github.com/RoboSense-LiDAR/rslidar_sdk.git
git clone -b master https://github.com/RoboSense-LiDAR/rslidar_msg.git
```

`--recursive` 不可省略：`rslidar_sdk` 通过子模块引入 `src/rs_driver`，
漏掉会导致编译时找不到驱动核心库。
