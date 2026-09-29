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
#   docker build -f .devcontainer/Dockerfile \
#       --build-arg BUILD_WORKSPACE=true \
#       --build-arg USER_UID=$(id -u) \
#       --build-arg USER_GID=$(id -g) \
#       -t airy_ros2:humble .
#   直接用 docker build 时必须显式传 USER_UID/USER_GID，否则容器用户是默认的
#   1000，与宿主 UID 不一致时又会退回"文件属主对不上"的老问题。
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
# 1. 驱动编译与运行所需依赖
#    build-essential / cmake / git  ：rs_driver 需要 C++14 工具链（-std=c++14）
#    libyaml-cpp-dev               ：rslidar_sdk 解析 config.yaml（最小版镜像不含）
#    libpcap-dev                   ：rs_driver 默认 ENABLE_PCAP_PARSE，链接 -lpcap
#    libeigen3-dev                 ：仅 ENABLE_TRANSFORM=ON 时需要，预先装好
#    python3-colcon-common-extensions：colcon build / colcon 命令集
#    iputils-ping / net-tools / tcpdump：排查雷达 UDP（6699/7788）通信
#
#    ros-humble-rmw-cyclonedds-cpp ：rslidar_sdk 自带的 humble_start.py 开头会检测这个包。
#                                    未安装时它会调用 getpass 索要 sudo 密码去装，
#                                    而容器内没有 sudo，launch 会一直停在密码提示上。
#                                    装上后该分支直接跳过。
#    ros-humble-rviz2              ：同一个 launch 文件会启动 rviz2 节点。
#                                    launch_ros 在构造 LaunchDescription 阶段就解析 package，
#                                    包不存在会直接抛异常，连驱动节点都起不来，
#                                    所以这是"能启动 launch 文件"的硬前提，不是可选项。
#                                    容器无图形界面时 rviz2 仍会报连不上 display 后退出，
#                                    属预期现象，不影响驱动节点运行。
#
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
        ros-humble-rmw-cyclonedds-cpp \
        ros-humble-rviz2 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 1.5 建一个与宿主 UID/GID 对齐的普通用户
#
#    【解决什么】宿主 VS Code 报
#      EACCES: permission denied, unlink '.../airy_ws/build/COLCON_IGNORE'
#    根因：ros:humble-ros-base 默认以 root 运行，而 compose 把宿主 airy_ws/
#    整个挂到 /workspace。容器里 root 编译出的 build/ install/ log/ 落到宿主上，
#    属主也是 root；宿主用户既不是文件属主、对目录也没有写权限，
#    VS Code / rm / git 一动它们就被内核拒绝（COLCON_IGNORE 只是恰好第一个被删的）。
#    按宿主 UID/GID 建同名用户后，容器内新建的文件在宿主上就属于当前用户，
#    build/、install/、log/ 想删就删，问题从根上消失。
#
#    【为什么用 ARG】UID/GID 是宿主相关的值，写死在镜像里换台机器就错位，
#    所以由 docker-compose.yml 构建时传入（build.args 的 USER_UID / USER_GID）。
#
#    【为什么不写 USER 指令切成该用户】构建期的 colcon build（第 3 节）仍要以
#    root 跑才能保证 /opt/airy 的写入；运行时换成谁由 compose 的 user: 决定，
#    两件事互不干扰。
#
#    【若构建报 GID/UID already exists】说明所选基础镜像已经带了 1000 号用户，
#    把下面两条命令去掉，compose 里 user: 直接用那个已有用户即可。
# -----------------------------------------------------------------------------
ARG USER_UID=1000
ARG USER_GID=1000

RUN set -eux; \
    groupadd --gid "${USER_GID}" airy; \
    useradd --uid "${USER_UID}" --gid "${USER_GID}" \
            --create-home --shell /bin/bash airy

# -----------------------------------------------------------------------------
# 2. 容器内开箱即用的 ROS2 环境
#    - 交互式 shell 自动 source ROS2 与工作空间 overlay
#    - 文件存在时才 source，避免不存在时报错
#    - 两个用户各写一份，谁进容器都能开箱即用：
#        airy → compose 配了 user:，docker exec 与 VS Code 终端默认就是它，
#               读 /home/airy/.bashrc
#        root → 需要提权时 docker exec -u 0 -it airy_ros2 bash，
#               读 /root/.bashrc（tcpdump 抓包、临时 apt-get install 会用到）
#    - 结尾把家目录属主还给 airy：上面的 .bashrc 是 root 身份写进去的
# -----------------------------------------------------------------------------
RUN for H in /root /home/airy; do \
        echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> "${H}/.bashrc"; \
        echo "[ -f /opt/airy/install/setup.bash ] && source /opt/airy/install/setup.bash" >> "${H}/.bashrc"; \
        echo "[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash" >> "${H}/.bashrc"; \
    done \
 && chown -R airy:airy /home/airy

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
ARG BUILD_WORKSPACE=true

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
            --cmake-args -DCMAKE_BUILD_TYPE=Release -DENABLE_IMU_DATA_PARSE=ON \
        echo "source /opt/airy/install/setup.bash" >> /root/.bashrc; \
    else \
        echo "[info] BUILD_WORKSPACE=false，跳过构建期编译（一阶段：进容器后手动 colcon build）"; \
    fi

# -----------------------------------------------------------------------------
# 4. 放开 /opt/airy 的读与执行权限
#    第 3 节的编译是 root 干的，产物属主也是 root；运行时容器以 airy 身份跑，
#    不放开权限的话 source /opt/airy/install/setup.bash、ros2 launch 会报
#    Permission denied。用 a+rX 而不是 a+rwx：X 只给目录和本来就有执行位的
#    文件加执行权限，普通文件不会被误设成可执行。
#    （放在最后是有意的：它自成一薄层，改动本层不影响上面耗时的 apt 缓存）
# -----------------------------------------------------------------------------
RUN chmod -R a+rX /opt/airy

# 容器默认命令：
#   - compose 中会用 command: sleep infinity 覆盖它，让容器常驻不退出
#   - 直接 docker run 时则得到一个交互式 bash
CMD ["/bin/bash"]
