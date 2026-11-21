# 机器人状态快照。连接断开时，不应使用位置控制实体机器人。
std_msgs/Header header
bool connected
# 百分比为 0~100；默认 -1 表示电量未知。
float32 battery_percentage -1.0
# 位置单位为米，偏航角单位为弧度；坐标系由 header.frame_id 给出。
float64 x
float64 y
float64 yaw
string navigation_status
string current_location
bool is_moving
string error_message
