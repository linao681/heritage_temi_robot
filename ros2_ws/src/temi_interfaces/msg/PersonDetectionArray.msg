std_msgs/Header header
string source
float32 sample_age_sec
bool valid
string error
string observation_state
uint32 people_count
temi_interfaces/PersonDetection[] detections
bool person_distance_valid
float32 nearest_person_m
# Optional 0..1 occupancy score; valid only after camera-zone calibration.
bool crowd_density_valid
float32 crowd_density
