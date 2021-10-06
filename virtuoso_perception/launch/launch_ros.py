import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    config_yolo = os.path.join(
        get_package_share_directory('virtuoso_perception'),
        'virtuoso_perception',
         'camera',
          'config',
           'detector_node_params.yaml'
    )

    return LaunchDescription([
        Node(
            package='openrobotics_darknet_ros',
            executable='detector_node',
            name='darknet',
            parameters=[config_yolo],
            remappings=[
	    ('/darknet/images', '/zed/zed_node/stereo/image_rect_color'),
	    ],
        )
        ]
      )
