import rclpy
from rclpy.node import Node
from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import PoseStamped, Point, Vector3
from std_msgs.msg import Empty
from virtuoso_msgs.srv import Channel, Rotate
from .channel_nav_states import State
from ...utils.channel_nav.channel_nav import ChannelNavigation
from ...utils.geometry_conversions import point_to_pose_stamped
import time

class ChannelNavNode(Node):

    def __init__(self):
        super().__init__('autonomy_channel_nav')

        self.declare_parameters(namespace='', parameters=[
            ('num_channels', 0),
            ('extra_forward_nav', 0.0),
            ('gate_buoy_max_dist', 0.0),
            ('rotation_theta', 0.0)
        ])

        self.path_pub = self.create_publisher(Path, '/navigation/set_path', 10)
        self.trans_pub = self.create_publisher(Point, '/navigation/translate', 10)
        self.station_keeping_pub = self.create_publisher(Empty, '/navigation/station_keep', 10)

        self.nav_success_sub = self.create_subscription(PoseStamped, '/navigation/success', 
            self.nav_success_callback, 10)
        self.odom_sub = self.create_subscription(Odometry, '/localization/odometry', 
            self.odom_callback, 10)
        
        self.state = State.START
        self.channels_completed = 0

        self.channel_client = self.create_client(Channel, 'channel')
        self.channel_call = None

        self.rotate_client = self.create_client(Rotate, 'rotate')
        self.rotate_call = None
        
        self.robot_pose:PoseStamped = None

        self.pre_rotation_left = None
        self.pre_rotation_right = None

        self.create_timer(1.0, self.execute)

    def nav_success_callback(self, msg:PoseStamped):
        if (self.channels_completed ==
            self.get_parameter('num_channels').value):
            if self.state != State.COMPLETE:
                self.nav_forward()
            self.state = State.COMPLETE
        elif (self.state == State.EXTRA_FORWARD_NAV
            or self.get_parameter('extra_forward_nav').value == 0.0):
            time.sleep(5.0)
            self.state = State.FINDING_NEXT_GATE
        else:
            time.sleep(2.0)
            self.nav_forward()
        
    def nav_forward(self):
        self.state = State.EXTRA_FORWARD_NAV
        self.trans_pub.publish(Point(x=self.get_parameter('extra_forward_nav').value))
    
    def odom_callback(self, msg:Odometry):
        self.robot_pose = PoseStamped(pose=msg.pose.pose)
    
    def execute(self):
        self.get_logger().info(str(self.state))
        if self.state == State.START:
            self.enable_station_keeping()
            return
        if self.state == State.STATION_KEEPING_ENABLED:
            self.state = State.FINDING_NEXT_GATE
            return
        if self.state == State.FINDING_NEXT_GATE:
            self.nav_to_next_midpoint()
            return
        if self.state == State.ROTATING_TO_FIND_NEXT_GATE:
            return
        if self.state == State.NAVIGATING:
            return
    
    def enable_station_keeping(self):
        self.state = State.STATION_KEEPING_ENABLED
        self.station_keeping_pub.publish(Empty())
    
    def nav_to_next_midpoint(self):

        if self.robot_pose is None:
            return
        if self.channel_call is not None:
            return
        
        req = Channel.Request()
        req.left_color = 'red'
        req.right_color = 'green'
        req.use_lidar = False
        req.use_camera = True
        req.max_dist_from_usv = self.get_parameter('gate_buoy_max_dist').value

        self.channel_call = self.channel_client.call_async(req)
        self.channel_call.add_done_callback(self.channel_response)

    def rotate(self, angle:float):
        self.state = State.ROTATING_TO_FIND_NEXT_GATE
        req = Rotate.Request()
        req.goal = Vector3(z=angle)
        
        self.rotate_call = self.rotate_client.call_async(req)
        self.rotate_call.add_done_callback(self.rotate_response)
    
    def rotate_response(self, future):
        result:Rotate.Response = future.result()
        self.get_logger().info(f'rotate response: {result}')
        self.state = State.FINDING_NEXT_GATE
    
    def channel_response(self, future):
        result:Channel.Response = future.result()
        self.get_logger().info(f'response: {result}')

        null_point = Point(x=0.0,y=0.0,z=0.0)

        self.channel_call = None
        
        if result.left == null_point:
            if result.right == null_point:
                self.get_logger().info('BOTH NULL POINTS')
                return 
            if self.pre_rotation_left is not None:
                result.left = self.pre_rotation_left
                self.nav_to_midpoint(result)
                return
            self.pre_rotation_right = result.right
            self.get_logger().info('ROTATING LEFT')
            self.rotate(self.get_parameter('rotation_theta').value) 
            return
        elif result.right == null_point:
            if self.pre_rotation_right is not None:
                result.right = self.pre_rotation_right
                self.nav_to_midpoint(result)
                return
            self.pre_rotation_left = result.left
            self.get_logger().info('ROTATING RIGHT')
            self.rotate(-self.get_parameter('rotation_theta').value)
            return
        
        self.nav_to_midpoint(result)
    
    def nav_to_midpoint(self, result):

        self.pre_rotation_left = None
        self.pre_rotation_right = None

        channel = (
            point_to_pose_stamped(result.left),
            point_to_pose_stamped(result.right)
        )

        mid = ChannelNavigation.find_midpoint(channel[0], channel[1], self.robot_pose)

        path = Path()
        path.poses.append(mid)
        # path.poses.append(channel[1])

        self.state = State.NAVIGATING
        self.channel_call = None
        self.channels_completed += 1
        self.path_pub.publish(path)


def main(args=None):
    
    rclpy.init(args=args)

    node = ChannelNavNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
