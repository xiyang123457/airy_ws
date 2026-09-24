# PROJECT.md

RoboSense AIRY 激光雷达 ROS2 驱动的容器化部署。战队任务。

## 目标

在 Ubuntu 22.04 上用 Docker 把 rslidar_sdk 驱动跑起来。链路是：

    Dockerfile → Docker Compose → Dev Container → ROS2 驱动编译

三个文件的职责：Dockerfile 管"环境里有什么"，Compose 管"容器怎么运行"，Dev Container 管"VS Code 怎么用这个容器"。

分两阶段。一阶段镜像只装环境，进容器后手动 `colcon build`；二阶段改成构建期自动编译，编译失败则镜像构建失败。

## 验收标准

9/28 前由战队师兄检查，四条：

1. Docker 镜像构建成功
2. Docker Compose 容器正常运行
3. VS Code 成功进入 Dev Container
4. `colcon build` 编译成功

进容器后还要确认：ROS2 命令可用、`rslidar_sdk` 与 `rslidar_msg` 编译成功、能尝试启动 `rslidar_sdk` 的 launch 文件。没有实体 AIRY 雷达时，不要求产生真实点云。

## 不做

多雷达接入、外参标定、SLAM/建图、点云算法、与战队其他模块联调。

## 任务书要求

Docker Compose，文件 `docker-compose.yml`：用自己的 Dockerfile 构建镜像；挂载本地工作空间到容器；容器启动后保持运行；考虑雷达 UDP/网口通信的网络配置。

Dev Container，文件 `.devcontainer/devcontainer.json`：复用已有的 `docker-compose.yml`，不得另建一套与 Compose 无关的容器环境；指定要进入的 service；VS Code 能通过 `Dev Containers: Reopen in Container` 进入。

二阶段，改 Dockerfile：构建期执行 `colcon build`；两个包任一编译失败，镜像构建也失败；最终 `docker build` 或 `docker compose build` 一步完成环境配置与驱动编译，不需进容器再手动构建。

## 环境与源码

Ubuntu 22.04 + ROS2 Humble + Docker + Docker Compose + VS Code Dev Container。基础镜像 `ros:humble-ros-base`。

工作空间相对结构：

    airy_ws/
    └── src/
        ├── rslidar_sdk/   # RoboSense-LiDAR/rslidar_sdk，main 分支，含 rs_driver 子模块
        └── rslidar_msg/   # RoboSense-LiDAR/rslidar_msg，master 分支

## 交付物与现状

| 文件 | 状态 |
|---|---|
| `docker/Dockerfile` | 已完成（76 行）；工作空间路径待从 `/ros2_ws` 改为 `airy_ws` |
| `docker/docker-compose.yml` | 待做 |
| `.devcontainer/devcontainer.json` | 待做 |

## 已验证的技术前提

- 容器不需要 `NET_RAW`，也不需要 root。驱动在线收包走普通 UDP socket，端口 6699/7788 都大于 1024；libpcap 只在回放 `.pcap` 时用到。
- 丢包与帧率下降的根因是 `net.core.rmem_max`。驱动把 `SO_RCVBUF` 设到至少 4MB，Ubuntu 22.04 默认只有 212992，内核会静默截断。宿主执行 `sysctl -w net.core.rmem_max=8388608`。
- `colcon` 不会深入已识别包的子目录，所以 `rslidar_msg` 整仓库克隆进 `src/` 是安全的。

## 待定

二阶段要让构建期能编译，源码必须进镜像。构建时 `git clone`、`COPY` 本地 `src/`、用 `ARG` 切换，三者未定。

## 下一步

- [ ] 克隆 `rslidar_sdk`（main）与 `rslidar_msg`（master）到 `airy_ws/src/`
- [ ] 在 `rslidar_sdk/` 内执行 `git submodule update --init --recursive`
- [ ] Dockerfile 里 `/ros2_ws` 改为 `airy_ws`
- [ ] 写 `docker/docker-compose.yml`
- [ ] 写 `.devcontainer/devcontainer.json`
- [ ] 装完 Ubuntu 后 `docker compose build`，确认镜像构建成功
- [ ] VS Code `Reopen in Container` 进入容器
- [ ] 容器内 `colcon build`，确认两个包编译成功
- [ ] 宿主执行 `sysctl -w net.core.rmem_max=8388608`
- [ ] 二阶段：改 Dockerfile，构建期跑 `colcon build`
