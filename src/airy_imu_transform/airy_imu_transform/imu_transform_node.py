"""AIRY IMU 坐标轴变换节点。"""                              # 模块文档字符串：说明本文件用途

# 原始 AIRY IMU：Z 轴朝下，水平静止时 z ≈ -0.98g；目标 X前Y左Z上，静止时 z ≈ +9.8
# 变换矩阵 R = [[0,-1,0],[-1,0,0],[0,0,-1]]，即 (x,y,z) -> (-y,-x,-z)

import rclpy                                                 # 导入 ROS2 的 Python 主库
from rclpy.node import Node                                  # 导入节点基类 Node
from sensor_msgs.msg import Imu                              # 导入标准 IMU 消息类型

class ImuTransformNode(Node):                                # 定义节点类，继承 Node
    """订阅原始 IMU,变换坐标系后重新发布。"""                # 类的文档说明
    def __init__(self):                                      # 构造函数：节点创建时执行一次
        super().__init__('imu_transform_node')               # 调父类构造，节点命名为 imu_transform_node
        
        self.declare_parameter('input_topic', '/rslidar_imu_data')   # 声明参数：输入话题名
        self.declare_parameter('output_topic', '/livox/imu')        # 声明参数：输出话题名
        self.declare_parameter('frame_id', 'livox_imu')           #声明参数：输出坐标系名
        self.declare_parameter('accel_scale',9.80665)       # 声明参数：g->m/s² 换算系数
        
        in_topic = self.get_parameter('input_topic').get_parameter_value().string_value     #读取参数值
        out_topic = self.get_parameter('output_topic').get_parameter_value().string_value    # 读取输出话题参数值
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value    # 读取坐标系名，存实例变量     
        self.accel_scale= float(self.get_parameter('accel_scale').value)                     # 读取换算系数并转 float
        
        self.sub = self.create_subscription(Imu,in_topic,self.cb,10)    # 订阅输入话题，收到消息回调 cb，队列长度 10
        self.pub = self.create_publisher(Imu,out_topic,10)             # 创建输出话题发布者，队列长度 10

        self.get_logger().info(                              # 启动时打印一行回显，确认参数生效
            f'IMU transform: {in_topic} -> {out_topic}, '           # 回显输入输出话题
            f'frame_id={self.frame_id}, accel_scale={self.accel_scale}')  # 回显坐标系与换算系数
        
    def cb(self,msg:Imu):                                    # 回调：每收到一条原始 IMU 消息时触发
        """订阅回调函数。"""                                 # 回调的文档说明
        out =Imu()                                           # 新建一条空的 Imu 消息用于装结果
        out.header = msg.header                              # 时间戳 header 原样复制
        out.header.frame_id = self.frame_id                  # 把坐标系名改成目标名
        out.orientation = msg.orientation                    # 朝向四元数原样透传

        out.angular_velocity.x =-msg.angular_velocity.y      # 角速度 x' = -y
        out.angular_velocity.y =-msg.angular_velocity.x      # 角速度 y' = -x
        out.angular_velocity.z =-msg.angular_velocity.z      # 角速度 z' = -z
        
        s = self.accel_scale                                 # 取换算系数，少写几次 self.
        out.linear_acceleration.x =-msg.linear_acceleration.y*s   # 加速度 x' = -y * s
        out.linear_acceleration.y =-msg.linear_acceleration.x*s   # 加速度 y' = -x * s
        out.linear_acceleration.z =-msg.linear_acceleration.z*s   # 加速度 z' = -z * s

        self.pub.publish(out)                                # 把变换后的消息发布到输出话题
        
        
def main(args =None):                                        # 模块级入口函数，供 entry_points 调用
    rclpy.init(args=args)                                    # 初始化 ROS2 客户端
    node = ImuTransformNode()                                # 创建节点实例
    try:                                                     # 进入 try，以便退出时做清理
        rclpy.spin(node)                                     # 事件循环，开始收发消息，直到 Ctrl+C
    finally:                                                 # 无论正常退出还是异常都会执行清理
        node.destroy_node()                                  # 销毁节点
        rclpy.shutdown()                                     # 关闭 ROS2
        
if __name__ == '__main__':                                   # 直接运行本文件时（非被 import）
    main()                                                   # 调用 main() 启动节点
