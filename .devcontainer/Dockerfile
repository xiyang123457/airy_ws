# =============================================================================
# airy_ws —— RoboSense AIRY 激光雷达 ROS2 驱动开发环境
#
# 基础镜像：ROS 官方 Humble —— 默认最小版 ros:humble-ros-base（任务书指定）
#   可用 --build-arg BASE_IMAGE=... 切换：
#     ros:humble-ros-base            默认，最小版，仅核心 ROS2
#     osrf/ros:humble-desktop        桌面版，含 rviz2，体积约 +1GB
#     osrf/ros:humble-desktop-full   功能最全，含 rviz2 / PCL / 仿真工具，体积最大
#
#   【命名坑】osrf/ros 仓库只有 desktop 与 simulation 系列，没有 ros-base / ros-core。
#   把最小版写成 osrf/ros:humble-ros-base 会在拉取阶段报 403 Forbidden
#   （上游实际返回 MANIFEST_UNKNOWN，被部分镜像加速器包装成 403），
#   正确写法是不带 osrf/ 前缀的官方镜像 ros:humble-ros-base。
#
# 构建：
#   docker compose -f .devcontainer/docker-compose.yml build
#   或直接：
#   docker build -f .devcontainer/Dockerfile --build-arg BUILD_WORKSPACE=true -t airy_ros2:humble .
# =============================================================================

ARG BASE_IMAGE=ros:humble-ros-base
FROM ${BASE_IMAGE}

# ROS2 发行版（与基础镜像保持一致，可用 --build-arg 覆盖）
ARG ROS_DISTRO=humble

ENV ROS_DISTRO=${ROS_DISTRO} \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-c"]

# -----------------------------------------------------------------------------
# 1. 驱动编译所需依赖
#    build-essential / cmake / git  ：rs_driver 需要 C++14 工具链（-std=c++14）
#    libyaml-cpp-dev               ：rslidar_sdk 解析 config.yaml（最小版镜像不含）
#    libpcap-dev                   ：rs_driver 默认 ENABLE_PCAP_PARSE，链接 -lpcap
#    libeigen3-dev                 ：仅 ENABLE_TRANSFORM=ON 时需要，预先装好
#    python3-colcon-common-extensions：colcon build / colcon 命令集
#    iputils-ping / net-tools / tcpdump：排查雷达 UDP（6699/7788）通信
#    依赖安装与 apt 缓存清理合并在同一层，减小镜像体积
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        libyaml-cpp-dev \
        libpcap-dev \
        libeigen3-dev \
        python3-colcon-common-extensions \
        python3-pip \
        iputils-ping \
        net-tools \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 2. 容器内开箱即用的 ROS2 环境
#    - 交互式 shell 自动 source ROS2 与工作空间 overlay
#    - 文件存在时才 source，避免不存在时报错
# -----------------------------------------------------------------------------
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /root/.bashrc \
 && echo "[ -f /opt/airy/install/setup.bash ] && source /opt/airy/install/setup.bash" >> /root/.bashrc \
 && echo "[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash" >> /root/.bashrc

WORKDIR /workspace

# -----------------------------------------------------------------------------
# 3. 二阶段（可选）：构建期自动编译工作空间
#
#    【为什么要有这个开关】本项目采用两阶段构建策略：
#      一阶段（默认）：镜像只装环境，源码通过挂载进入容器，进容器后手动 colcon build。
#                     改代码无需重建镜像，日常开发最快
#      二阶段（可选）：docker build 时即自动编译，任一包编译失败 ⇒ 镜像构建失败。
#                     适合交付、CI 与"一条命令完成环境配置 + 驱动编译"的场景
#    默认 false；需要出交付镜像时再显式开启。
#
#    【开启方式】
#      docker compose -f .devcontainer/docker-compose.yml build \
#          --build-arg BUILD_WORKSPACE=true
#
#    【产物为什么装到 /opt/airy 而不是 /workspace】
#      docker-compose.yml 会把宿主机 airy_ws/ 整个挂载到容器的 /workspace，
#      挂载会"遮蔽"镜像里 /workspace 下原有的内容。若产物放 /workspace/install，
#      构建期虽然编译成功，运行时却被宿主机目录盖住，看到的仍是空的。
#      因此产物固定装在 /opt/airy/install（挂载范围之外）；
#      bashrc 中优先 source 它，其次才是 /workspace/install（一阶段手动编译的产物）。
#
#    注意：下面的 RUN 用 \ 续行拼成一条 shell 命令，续行体内不能再插 # 注释
#          （否则会把后面整段都注释掉），所以说明统一写在指令上方。
# -----------------------------------------------------------------------------

# 构建参数：false = 一阶段（只装环境）；true = 二阶段（构建期编译）
ARG BUILD_WORKSPACE=false

# 把宿主机 src/（rslidar_sdk、rslidar_msg）拷进镜像。
# Dockerfile 语法不支持"条件 COPY"，所以无论开关取值这行都会执行；
# 正因如此它被放在整个文件最后 —— 源码一改只有这一层及之后失效，
# 前面耗时的 apt 安装层仍能命中缓存，重建很快。
COPY src/ /opt/airy/src/

# RUN 内部各步的含义（按顺序）：
#   set -eo pipefail
#       -e  任何命令返回非 0 立即退出 —— "编译失败 ⇒ 镜像构建失败"的关键。
#           没有它，colcon 报错后 shell 仍会继续往下走，镜像照样构建成功
#       -o pipefail  管道中任意一环失败都算整体失败
#       这里刻意先不开 -u，原因见下面 "set -u" 那一条。
#   . /opt/ros/${ROS_DISTRO}/setup.sh
#       编译前必须先加载 ROS2 环境，否则找不到 rclcpp / ament_cmake 等包。
#       用 setup.sh 而非 setup.bash：RUN 的底层 shell 不保证支持 bash 语法
#   set -u
#       source 完 ROS 环境之后再开 nounset，顺序不能颠倒。
#       坑：ROS 自带的 setup.sh 会引用未定义的 $AMENT_TRACE_SETUP_FILES，
#       若在 source 之前就开了 -u，会在 setup.sh 第 124 行直接
#       报 "AMENT_TRACE_SETUP_FILES: unbound variable" 退出，
#       表现为二阶段构建必然失败。所以必须先 source、后 set -u。
#   cd /opt/airy
#       colcon 以"当前目录"为工作空间根并扫描其下的 src/，所以必须切到这一层
#   --symlink-install
#       install 目录用符号链接指向源文件：改 launch/脚本后无需重新 colcon build
#   --parallel-workers "$(nproc)"
#       nproc 返回 CPU 核数，多包并行；本工作空间 2 个包收益有限，但写法通用
#   --cmake-args -DCMAKE_BUILD_TYPE=Release
#       开 -O3 优化；rslidar_sdk 的 CMakeLists 默认即 Release，显式声明保持一致
#   echo "source ..." >> /root/.bashrc
#       编译成功后把 overlay 写进 bashrc：进容器开终端即可直接 ros2 launch，
#       无需每次手动 source
#   else 分支
#       未开启时给出明确提示，避免误以为已经编译过
RUN if [ "${BUILD_WORKSPACE}" = "true" ]; then \
        set -eo pipefail; \
        . /opt/ros/${ROS_DISTRO}/setup.sh; \
        set -u; \
        cd /opt/airy; \
        colcon build \
            --symlink-install \
            --parallel-workers "$(nproc)" \
            --cmake-args -DCMAKE_BUILD_TYPE=Release; \
        echo "source /opt/airy/install/setup.bash" >> /root/.bashrc; \
    else \
        echo "[info] BUILD_WORKSPACE=false，跳过构建期编译（一阶段：进容器后手动 colcon build）"; \
    fi

# 容器默认命令：
#   - compose 中会用 command: sleep infinity 覆盖它，让容器常驻不退出
#   - 直接 docker run 时则得到一个交互式 bash
CMD ["/bin/bash"]
