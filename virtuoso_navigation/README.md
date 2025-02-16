# Virtuoso Navigation

## Contents
- [Nav2](#nav2)
- [Virtuoso Navigation Nodes](#virtuoso-navigation-nodes)
  - [waypoints_node.py](#waypoints\_nodepy)
  - [translate_node.py](#translate\_nodepy)
  - [station_keeping_node.py](#station\_keeping\_nodepy)
  - [rotate_node.py](#rotate\_nodepy)
  - [approach_target_node.py](#approach\_target\_nodepy)
  - [waypoint_player_node.py](#waypoint\_player\_nodepy)
  - [multi_tasks_waypoint_player_node.py](#multi\_tasks\_waypoint\_player\_nodepy)
- [External Subscribed Topics](#external-subscribed-topics)
- [External Published Topics](#external-published-topics)
- [External Services](#external-services)
- [External Actions](#external-actions)
- [Parameters](#parameters)
  - [nav2.yaml](#nav2yaml)
  - [waypoints.yaml](#waypointsyaml)
  - [rotate.yaml](#rotateyaml)

## Nav2

Nav2 is an open-source package which is used by our navigation server for global path planning. Nav2 takes in odometry from the localization server and point clouds from the perception server, and it creates a global costmap. When we send it a goal in the map frame, it will generate a sequence of waypoints which the USV will follow. This path is passed to our controller server. Further documentation can be found on the [Nav2 Github](https://github.com/ros-planning/navigation2). 

## Virtuoso Navigation Nodes

### waypoints_node.py
This node takes in a sequence of waypoints in the map frame the USV needs to navigate to. Every time the USV arrives at a waypoint, it will generate a path to the next waypoint through Nav2. When finised with all waypoints, the node will publish a success message.

### translate_node.py
This node takes in a point in the base_link frame the USV needs to translate to. The point is transformed to the map frame and then passed into the `waypoints_node` as a single waypoint. When translation has finished, the node will publish a success message.

### station_keeping_node.py
This node upon request publishes a path with a single waypoint (the current pose) to the controller. The controller will then attempt to hold that pose.

### rotate_node.py
This node upon request rotates the USV by a requested number of radians.

### approach_target_node.py
Using the lidar data from perception, on a request, the node will navigate the USV to the requested distance from the object in front of it. Additionally, width of the lidar scan can be specified in the request along with a timeout.

### waypoint_player_node.py
Check the `virtuoso_localization` documentation on the `waypoint_saver_node.py` to see how waypoints are saved. The player will look inside the `~/mrg/waypoints_raw` directory for the `points_{file_num}.yaml` file containing the the waypoints to follow, where `file_num` is a parameter for the node. If `file_num` is not provided, it will simply find the most recent waypoints file (i.e. the one with the highest number). The pseudo-code below explains how the player navigates through each waypoint:
- while not finished with all gps waypoints:
  - convert current gps waypoint to the map frame, no need to change orientation from the file
  - send a path to the `waypoints_node` containing the map frame waypoint
  - when `waypoints_node` sends a success message, repeat for the next gps waypoint

When finished with all waypoints, the player will publish a success message.

### multi_tasks_waypoint_player_node.py
Check the `virtuoso_localization` documentation on the `multi_tasks_waypoint_saver_node.py` to see how multi-task waypoints are saved. The node takes a request specifying which task's waypoints the USV should navigate through. The waypoints are saved in a `points_{file_num}.yaml` file inside of `~/mrg/semis_waypoints`. If no file_num is specified as a paramter when the node is launched, the node will use the most recent waypoints file (i.e. the one with the highest number). The node will then find the waypoints for the requested task in the file and navigate through them, similar to how the `waypoint_player_node` does. Upon success, the action returns.

## External Subscribed Topics

| Topic | Message Type | Frame | Purpose |
|-------|--------------|-------|---------|
| /localization/odometry | [nav_msgs/Odometry](http://docs.ros.org/en/noetic/api/nav_msgs/html/msg/Odometry.html) | odom | Used by Nav2 for generating costmap and waypoints_node to determine when to navigate to next waypoint. |
| /perception/lidar/points_shore_filtered | [sensor_msgs/PointCloud2](http://docs.ros.org/en/melodic/api/sensor_msgs/html/msg/PointCloud2.html) | lidar_link | Used by Nav2 for generating costmap. |
| /navigation/set_path | [nav_msgs/Path](https://docs.ros2.org/foxy/api/nav_msgs/msg/Path.html) | map | Used by the waypoints_node. |
| /navigation/translate | [geometry_msgs/Point](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/Point.html) | base_link | Used by translate_node. |
| /navigation/station_keep | [std_msgs/Empty](http://docs.ros.org/en/melodic/api/std_msgs/html/msg/Empty.html) | N/A | Activates station keeping. Used by station_keeping_node. |

## External Published Topics

| Topic | Message Type | Frame | Purpose |
|-------|--------------|-------|---------|
| /navigation/plan | [nav_msgs/Path](https://docs.ros2.org/foxy/api/nav_msgs/msg/Path.html) | map | The global plan the USV should follow. Used by the controller server. |
| /navigation/success | [geometry_msgs/PoseStamped](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/PoseStamped.html) | map | Final pose the USV successfully navigates to from waypoint navigation. |
| /navigation/translate_success | [geometry_msgs/Point](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/Point.html) | base_link | Point USV successfully translates to. |
| /navigation/waypoint_player/success | [geometry_msgs/PoseStamped](http://docs.ros.org/en/noetic/api/geometry_msgs/html/msg/PoseStamped.html) | map | Final pose the USV navigates to using the waypoint player. |

## External Services 

| Service | Service Type | Frame | Purpose |
|---------|--------------|-------|---------|
| rotate | [virtuoso_msgs/Rotate](/virtuoso_msgs/srv/Rotate.srv) | base_link | Rotates the USV a certain number of radians. |

## External Actions

| Action | Action Type | Frame | Purpose |
|---------|--------------|-------|---------|
| approach_target | [virtuoso_msgs/ApproachTarget](/virtuoso_msgs/action/ApproachTarget.action) | N/A | USV approaches the object in front of it to a requested number of meters. |
| task_waypoint_nav | [virtuoso_msgs/TaskWaypointNav](/virtuoso_msgs/action/TaskWaypointNav.action) | N/A | USV navigates to the waypoints for the requested task. |

## Parameters

### nav2.yaml
Parameters for tuning Nav2. A full configuration guide can be found [here](https://navigation.ros.org/configuration/index.html). 

### waypoints.yaml

| Node | Parameter | Type | Description |
|------|-----------|------|-------------|
| navigation_waypoints | use_nav2 | bool | If true, Nav2 will work as specified above. If false, the waypoint node will not use Nav2 for path planning but will instead create straight line paths; nav2 will also not be launched. |
| navigation_waypoints | only_translate | bool | If true, they waypoint node will send a command to translate to the controller whenever it sends the controller a path. |
| navigation_waypoints | goal_dist_tolerance | float | The distance from the goal necessary for the waypoint node to decide that it has reached the waypoint. |
| navigation_waypoints | goal_rotation_tolerance | float | The maximum yaw difference in radians that the USV can be from the target orientation for the USV to be at the waypoint. |

### rotate.yaml

| Node | Parameter | Type | Description |
|------|-----------|------|-------------|
| navigation_rotate | goal_tolerance | float | The goal tolerance in radians for the node to send a response. |
