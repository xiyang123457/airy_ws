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

镜像已在构建阶段自动编译（见第八节，`/opt/airy/install` 已有产物），通常无需手动编译，直接 launch 即可。若改动了 `src/` 下源码需要重新编译，进入容器后：

```bash
cd /workspace
source /opt/ros/humble/setup.bash
colcon build --symlink-install --parallel-workers $(nproc)
source install/setup.bash
```

`rslidar_sdk` 强依赖 `src/rs_driver` 子模块。若该目录为空，编译必然失败。

## 四、运行雷达

### 4.1 网络准备（接雷达前必做）

AIRY 出厂默认网络参数（RoboSense 官方产品手册）：

| 项目 | 默认值 |
|---|---|
| 雷达 IP | `192.168.1.200` |
| MSOP 点云端口 | `6699` |
| DIFOP 设备信息端口 | `7788` |
| 电脑 IP（官方约定） | `192.168.1.102` |

AIRY 是**雷达主动往电脑发包**：雷达上电后靠 ARP 报文发现同网段的电脑，再把数据推过去。所以电脑 IP 必须与雷达同网段，用官方约定值 `.102` 最省事：

```bash
# 本机有线网卡是拓展坞提供的 USB 网卡，名为 enx00e602015dae
sudo nmcli con mod "有线连接 1" con-name airy ifname enx00e602015dae \
  ipv4.method manual ipv4.addresses 192.168.1.102/24 ipv4.never-default yes
sudo nmcli con up airy
ip -br addr show enx00e602015dae      # 回读确认 192.168.1.102/24
```

三个要点：

- **不要设网关**：`ipv4.never-default yes`，否则有线口会抢默认路由，把 WiFi 上网断掉
- 雷达 IP 若被改过（不再是 `.200`），用 4.2 的 ARP 抓包找出真实地址
- 需要改雷达自身的 IP 或端口：电脑设好同网段后，浏览器打开 `http://192.168.1.200` 进雷达 Web 端修改

### 4.2 链路验证（先抓包，再启动驱动）

```bash
ping 192.168.1.200                                     # 雷达在线？
sudo tcpdump -i enx00e602015dae -n udp port 6699       # 有包 = 数据正在进来
sudo tcpdump -i enx00e602015dae -n arp                 # IP 不确定时，看雷达的 ARP 请求里带的是哪个地址
```

`tcpdump` 抓到包是唯一可信的判据。驱动不报错不等于链路正常——没有数据时驱动照样持续运行、点云为空。

### 4.3 启动

ROS2 各版本的 launch 文件格式不同，仓库同时提供 `start.py` 与 `humble_start.py`。
本项目使用 Humble，请指定对应版本：

```bash
source /opt/ros/humble/setup.bash && source /opt/airy/install/setup.bash
ros2 launch rslidar_sdk humble_start.py
```

该 launch 会**同时拉起 rviz2**，窗口直接弹在宿主桌面上（X11 转发配置见 `.devcontainer/docker-compose.yml` 注释；宿主每次重新登录后需执行一次 `xhost +SI:localuser:xiyang`）。另开一个终端确认点云频率：

```bash
ros2 topic hz /rslidar_points        # 正常约 10 Hz
```

按实际雷达修改 `src/rslidar_sdk/config/config.yaml`：

| 参数 | 说明 |
|---|---|
| `lidar_type` | 雷达型号，如 `RSAIRY`（本项目 AIRY）、`RSHELIOS`、`RS128`（默认 `RSM1`） |
| `msop_port` | 点云数据端口，默认 `6699` |
| `difop_port` | 设备信息端口，默认 `7788` |
| `host_address` | 本机接收 IP |
| `group_address` | 组播地址（单播时留空） |

本项目已把 `config.yaml` 的 `lidar_type` 改为 `RSAIRY`（上游默认值是 `RSM1`）；换用其他型号时按上表相应修改。`host_address` / `group_address` 保持 `0.0.0.0` 即可——AIRY 驱动直接绑定任意地址收包，不需要在这里写本机 IP。

## 五、查看点云

镜像已装 rviz2。`humble_start.py` 会自动启动它并加载本包自带的配置（`share/rslidar_sdk/rviz/rviz2.rviz`）；手动启动则是：

```bash
rviz2
```

添加 `PointCloud2`，Topic 选择 `/rslidar_points`，Fixed Frame 设为 `rslidar`。

X11 转发已在 `.devcontainer/docker-compose.yml` 里配好（挂载 `/tmp/.X11-unix` 并传入 `DISPLAY`），宿主执行一次 `xhost +SI:localuser:xiyang` 即可。未授权时 rviz2 会因加载不了 Qt 的 `xcb` 平台插件而退出（`Could not load the Qt platform plugin "xcb"` 或 `cannot connect to X server`），驱动节点不受影响。

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

调之前先看当前值：

```bash
sysctl net.core.rmem_max
```

Ubuntu 22.04 默认 `212992`，需要调。Docker Desktop on Windows 的 WSL2 内核默认已是 `4194304`，够用，不必再调。

驱动启动时会打印两行作为佐证：

```
Original receive buffer size: 212992 bytes
After setting: receive buffer size: 8388608 bytes
```

这两个数是 `getsockopt(SO_RCVBUF)` 的返回值，Linux 内核会把它翻倍显示。驱动在 `input_sock_select.hpp` 里把请求值下限写死为 `4194304`，所以第二行 8388608 对应实际生效的 4MB，等于驱动要求的下限，属正常。若第二行只有 425984（即 2 × 212992），说明内核把请求截断到了默认值，此时才需要调 `rmem_max`。

## 七、切换基础镜像

默认 `ros:humble-ros-base`，任务书指定的最小版，只含 ROS2 核心；rviz2 与 CycloneDDS 由 Dockerfile 单独补装。需要 PCL、Gazebo 等完整工具链时再切换：

```bash
docker compose -f .devcontainer/docker-compose.yml build \
  --build-arg BASE_IMAGE=osrf/ros:humble-desktop-full
```

注意 `osrf/ros` 仓库只有 `humble-desktop`、`humble-desktop-full`、`humble-simulation` 等 tag，
没有 `humble-ros-base`。最小版必须写官方镜像 `ros:humble-ros-base`，不带 `osrf/` 前缀；
写成 `osrf/ros:humble-ros-base` 会在拉取阶段报 403 Forbidden 导致构建失败。

## 八、二阶段：构建期自动编译

`docker-compose.yml` 中 `BUILD_WORKSPACE` 已设为 `"true"`，即**默认开启**。直接 `docker compose build`（无需额外参数）即会在构建阶段完成 `colcon build`，任一包编译失败则构建中断：

```bash
# 以下两种写法等价（compose 里默认已是 true）
docker compose -f .devcontainer/docker-compose.yml build
docker compose -f .devcontainer/docker-compose.yml build --build-arg BUILD_WORKSPACE=true
```

如需改回手动编译（进容器后再 `colcon build`，见第三节），把 `docker-compose.yml` 里的 `BUILD_WORKSPACE` 改成 `"false"`，或显式传参：

```bash
docker compose -f .devcontainer/docker-compose.yml build --build-arg BUILD_WORKSPACE=false
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
| 收不到点云 / `/rslidar_points` 没有频率 | 按 4.2 先抓包：`sudo tcpdump -i enx00e602015dae -n udp port 6699`。**有包**说明链路通，问题在 `lidar_type`（须 `RSAIRY`）或 `rmem_max`；**没包**则查电脑 IP 是否与雷达同网段（官方约定 `192.168.1.102`）、雷达 IP 是否被改过（用 ARP 抓包确认）、`network_mode: host` 是否还在 |
| rviz2 报 `Could not load the Qt platform plugin "xcb"` / `cannot connect to X server` | 宿主未授权 X11。执行 `xhost +SI:localuser:xiyang`；若仍失败，确认 `docker-compose.yml` 里 `/tmp/.X11-unix` 挂载与 `DISPLAY` 已生效（改过 compose 需 `up -d --force-recreate`）。驱动节点不受影响，点云照常发布 |
| `ros2: command not found` | 环境未加载。交互式进容器会自动 source；用 `bash -c` 一次性执行不会，需手动 `source /opt/ros/humble/setup.bash` |
| `colcon: command not found` | 缺 `python3-colcon-common-extensions`（Dockerfile 已安装） |
| `ros2 topic echo` 报 `xmlrpc.client.Fault ... !rclpy.ok()` | ros2 daemon 上下文失效，见下文同名小节 |
| `ros2 launch` 停在索要 sudo 密码的提示 | 镜像未装 `ros-humble-rmw-cyclonedds-cpp`，见下文《`humble_start.py` 起不来》 |
| `ros2 launch` 报找不到 `rviz2` | 镜像未装 rviz2，见下文《`humble_start.py` 起不来》 |

### `ros2 topic echo` 报 `!rclpy.ok()`

`ros2 topic echo` 与 `ros2 topic list` 使用 `NodeStrategy`，默认把请求经 xmlrpc 转发给长驻的 ros2 daemon。daemon 是跨 `docker exec` 会话共享的独立进程，其 rclpy 上下文失效后，所有走 daemon 的子命令都会收到：

```
xmlrpc.client.Fault: <Fault 1: "<class 'RuntimeError'>:!rclpy.ok()">
```

`ros2 topic pub` 不受影响，它使用 `DirectNode`，在自身进程内建节点，因此出现「pub 正常、echo 报错」属于预期，不是环境损坏。

两种处理方式：

```bash
# 重启 daemon，下一条 ros2 命令会自动把它拉起
ros2 daemon stop

# 完全绕开 daemon
ros2 topic echo --no-daemon /chatter std_msgs/msg/String
```

推荐后者。daemon 在容器内的收益有限，它本是为多条 ros2 命令共享节点、加快 CLI 响应而设计，代价是跨会话的共享状态。`list`、`info`、`echo` 均支持 `--no-daemon`，`hz` 不支持。

### `humble_start.py` 起不来

该 launch 文件有两个前置依赖，`ros:humble-ros-base` 自身都不满足，Dockerfile 已显式安装。

其一是 `ros-humble-rmw-cyclonedds-cpp`。文件开头的 `install_cyclone_dds()` 用 `dpkg -s` 检测该包，未安装时会调用 `getpass` 索要 sudo 密码，而容器内没有 sudo，进程会停在交互提示上。装上后该分支直接跳过，输出 `DDS is already installed.`。

其二是 rviz2。第 36 行硬编码启动 rviz2 节点，`launch_ros` 在构造 `LaunchDescription` 阶段就解析 package，包不存在会直接抛异常，连驱动节点都起不来。这是「能启动 launch 文件」的硬前提，不是可选项。

用旧镜像或自建基础镜像遇到这两种报错时，在容器内补装：

```bash
apt-get update && apt-get install -y ros-humble-rmw-cyclonedds-cpp ros-humble-rviz2
```

## 十一、获取驱动源码

`rslidar_msg` 已随本仓库（airy_ws）一起提供，位于 `src/rslidar_msg`，无需单独拉取。
若 `src/rslidar_sdk` 缺失或为空，执行（注意 `rslidar_sdk` 目录若已存在但为空，先 `rm -rf rslidar_sdk` 再 clone）：

```bash
cd airy_ws/src
git clone --recursive https://github.com/RoboSense-LiDAR/rslidar_sdk.git
```

`--recursive` 不可省略：`rslidar_sdk` 通过子模块引入 `src/rs_driver`，
漏掉会导致编译时找不到驱动核心库。
