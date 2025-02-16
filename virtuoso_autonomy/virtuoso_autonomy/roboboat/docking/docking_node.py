import rclpy
from rclpy.node import Node
from .docking_states import State
from nav_msgs.msg import Path, Odometry
from std_msgs.msg import Empty
from geometry_msgs.msg import PoseStamped, Point, Pose, Vector3
from virtuoso_msgs.srv import DockCodesCameraPos, CountDockCodes, Rotate, ImageDockStereo
import time
import math

class DockingNode(Node):

    def __init__(self):
        super().__init__('autonomy_docking')

        self.declare_parameters(namespace='', parameters=[
            ('target_color', ''),
            ('camera', ''),
            ('centering_movement_tranches', []),
            ('centering_movement_values', []),
            ('search_movement_value', 0.0),
            ('docking_entry_value', 0.0)
        ])

        self.target_color = self.get_parameter('target_color').value
        cam = self.get_parameter('camera').value

        self.path_pub = self.create_publisher(Path, '/navigation/set_path', 10)
        self.trans_pub = self.create_publisher(Point, '/navigation/translate', 10)
        self.station_keeping_pub = self.create_publisher(Empty, '/navigation/station_keep', 10)

        self.nav_success_sub = self.create_subscription(PoseStamped, '/navigation/success', 
            self.nav_success_callback, 10)
        self.odom_sub = self.create_subscription(Odometry, '/localization/odometry', 
            self.odom_callback, 10)

        self.code_pos_client = self.create_client(DockCodesCameraPos, 
            f'{cam}/find_dock_placard_offsets')
        self.code_pos_req = None

        self.count_code_client = self.create_client(CountDockCodes, 
            f'{cam}/count_dock_codes')
        self.count_code_req = None

        self.stereo_client = self.create_client(ImageDockStereo, 'perception/dock_stereo')
        self.stereo_req = None

        self.rotate_client = self.create_client(Rotate, 'rotate')
        self.rotate_req = None
        
        self.state = State.START

        self.robot_pose:Pose = None

        self.create_timer(1.0, self.execute)
    
    def odom_callback(self, msg:Odometry):
        self.robot_pose = msg.pose.pose
    
    def nav_success_callback(self, msg:PoseStamped):
        if self.state == State.APPROACHING_DOCK: self.state = State.ORIENTING
        elif self.state == State.SEARCH_TRANSLATING: self.state = State.SEARCHING_FOR_DOCK_CODE
        elif self.state == State.CENTER_TRANSLATING: self.state = State.CENTERING
        elif self.state == State.DOCKING: self.state = State.COUNTING_CODE
        time.sleep(1.0)
    
    def execute(self):
        self.get_logger().info(str(self.state))
        if self.state == State.START:
            self.enable_station_keeping()
            return
        if self.state == State.STATION_KEEPING_ENABLED:
            # skip the next 2 states until implemented
            self.state = State.SEARCHING_FOR_DOCK_CODE
            return
        if self.state == State.APPROACHING_DOCK:
            return
        if self.state == State.FINDING_ORIENTATION:
            self.find_orientation()
            return
        if self.state == State.ORIENTING:
            return
        if self.state == State.SEARCHING_FOR_DOCK_CODE:
            self.search_for_dock_code()
            return
        if self.state == State.SEARCH_TRANSLATING:
            return
        if self.state == State.CENTERING:
            self.search_for_dock_code()
            return
        if self.state == State.CENTER_TRANSLATING:
            return
        if self.state == State.DOCKING:
            return
        if self.state == State.COUNTING_CODE:
            self.count_code()
            return
        
    def find_orientation(self):
        if self.stereo_req is not None or self.rotate_req is not None:
            return
        
        self.get_logger().info('sending req')
        # use different request which gets the position of the codes using 
        # stereo instead of their relative placements
        # also make sure the stereo is using bounds that don't border the camera
        msg = ImageDockStereo.Request()
        
        self.stereo_req = self.stereo_client.call_async(msg)
        self.stereo_req.add_done_callback(self.stereo_callback)
    
    def stereo_callback(self, future):
        result = future.result()

        self.stereo_req = None

        self.get_logger().info(f'result: {result}')

        if len(result.end_points) < 2:
            self.get_logger().info('Not enough end_points')
            return
        
        if result.end_points[0].x > result.end_points[1].x:
            p1 = result.end_points[0]
            p2 = result.end_points[1]
        else:
            p1 = result.end_points[1]
            p2 = result.end_points[0]

        msg = Rotate.Request()
        
        x = p1.x - p2.x
        y = -1 * (p1.y - p2.y)

        theta = math.atan(abs(x / y))

        self.get_logger().info(f'RAW THETA: {theta * 180}')

        if y < 0: theta = math.pi - theta

        msg.goal.z = theta

        self.get_logger().info(f'PROCESSED THETA: {msg.goal.z * 180}')

        self.state = State.ORIENTING

        self.rotate_req = self.rotate_client.call_async(msg)
        self.rotate_req.add_done_callback(self.rotate_callback)
    
    def rotate_callback(self, future):
        self.get_logger().info('Finished rotation')

        self.state = State.SEARCHING_FOR_DOCK_CODE        
        
    def enable_station_keeping(self):
        self.state = State.STATION_KEEPING_ENABLED
        self.station_keeping_pub.publish(Empty())
    
    def search_for_dock_code(self):
        if self.code_pos_req is not None:
            return

        msg = DockCodesCameraPos.Request()

        self.code_pos_req = self.code_pos_client.call_async(msg)        
        self.code_pos_req.add_done_callback(self.code_pos_callback)
    
    def code_pos_callback(self, future):
        result = future.result()

        self.code_pos_req = None

        self.get_logger().info(f'result: {result}')

        if len(result.red) == 0:
            self.get_logger().info(f'No dock code positions sent')
            return
        
        targetX = -1
        othersX = 0
        othersCount = 0

        if result.red[0] != -1 and result.red[1] != -1:
            mid = (result.red[0] + result.red[1]) // 2
            if self.target_color == 'red':
                targetX = mid
            else:
                othersX += mid
                othersCount += 1
        
        if result.blue[0] != -1 and result.blue[1] != -1:
            mid = (result.blue[0] + result.blue[1]) // 2
            if self.target_color == 'blue':
                targetX = mid
            else:
                othersX += mid
                othersCount += 1
        
        if result.green[0] != -1 and result.green[1] != -1:
            mid = (result.green[0] + result.green[1]) // 2
            if self.target_color == 'green':
                targetX = mid
            else:
                othersX += mid
                othersCount += 1
        
        if othersCount > 0:
            othersX //= othersCount
        
        if self.state == State.CENTERING and targetX == -1:
            self.get_logger().info('Centering but code not found.')
            return
        
        if targetX > -1:
            self.center_translate(targetX, result.image_width)
            return
        
        if othersCount == 0:
            self.get_logger().info('No code found in search.')
            return
        
        self.search_translate(othersX, result.image_width)
    
    def center_translate(self, targetX, image_width):
        msg = Point()

        self.state = State.CENTER_TRANSLATING

        movement_vals = self.get_parameter('centering_movement_values').value

        loc = targetX / image_width

        for i, tranch in enumerate(self.get_parameter('centering_movement_tranches').value):
            if not loc < tranch: continue

            if movement_vals[i] == 0.0:
                self.dock()
                return
            
            self.get_logger().info(f'translating: {movement_vals[i]}')
            msg.y = movement_vals[i]
            break
        else:
            self.get_logger().info(f'translating: {movement_vals[-1]}')
            msg.y = movement_vals[-1]

        self.trans_pub.publish(msg)
    
    def search_translate(self, othersX, image_width):
        msg = Point()

        self.state = State.SEARCH_TRANSLATING

        if othersX < image_width * .5:
            msg.y = self.get_parameter('search_movement_value').value
        else:
            msg.y = -self.get_parameter('search_movement_value').value

        self.trans_pub.publish(msg)
    
    def dock(self):
        self.get_logger().info('Within bounds, good to dock')
        self.state = State.DOCKING
        msg = Point()
        msg.x = self.get_parameter('docking_entry_value').value

        self.trans_pub.publish(msg)
    
    def count_code(self):
        if self.count_code_req is not None:
            return
        
        msg = CountDockCodes.Request(color=self.target_color)

        self.count_code_req = self.count_code_client.call_async(msg)
        self.count_code_req.add_done_callback(self.count_code_callback)
    
    def count_code_callback(self, future):
        result = future.result()

        self.count_code_req = None

        self.get_logger().info(f'COUNTED {result.count}')

        self.state = State.COMPLETE


def main(args=None):
    rclpy.init(args=args)

    node = DockingNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()