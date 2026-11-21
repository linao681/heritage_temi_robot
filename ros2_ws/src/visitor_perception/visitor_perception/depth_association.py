"""Associate normalized person boxes with calibrated depth-image measurements."""
import math

import numpy as np


def associate_person_depth(bbox, depth_m, *, fx, fy, cx, cy, min_depth_m=0.2,
                           max_depth_m=8.0, minimum_valid_pixels=3):
    """Return radial camera distance from the median center-box depth, or None."""
    if (len(bbox) != 4 or not isinstance(depth_m, np.ndarray) or depth_m.ndim != 2 or
            depth_m.size == 0):
        raise ValueError('bbox 与 depth_m 格式无效')
    x0, y0, x1, y1 = bbox
    numeric = lambda value: isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_))
    if (not all(numeric(v) and math.isfinite(v) for v in bbox) or
            not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1)):
        raise ValueError('bbox 必须是 [0,1] 内有效的归一化坐标')
    if (not all(numeric(v) and math.isfinite(v) for v in (fx, fy, cx, cy)) or
            fx <= 0 or fy <= 0):
        raise ValueError('相机内参无效')
    if (not math.isfinite(min_depth_m) or not math.isfinite(max_depth_m) or
            min_depth_m <= 0 or max_depth_m <= min_depth_m or
            type(minimum_valid_pixels) is not int or minimum_valid_pixels < 1):
        raise ValueError('深度范围或有效像素数配置无效')

    height, width = depth_m.shape
    box_x0, box_y0 = int(x0 * width), int(y0 * height)
    box_x1, box_y1 = min(width, math.ceil(x1 * width)), min(height, math.ceil(y1 * height))
    roi_x0 = box_x0 + (box_x1 - box_x0) // 4
    roi_x1 = box_x1 - (box_x1 - box_x0) // 4
    roi_y0 = box_y0 + (box_y1 - box_y0) // 4
    roi_y1 = box_y1 - (box_y1 - box_y0) // 4
    roi = depth_m[roi_y0:roi_y1, roi_x0:roi_x1]
    valid = roi[np.isfinite(roi) & (roi >= min_depth_m) & (roi <= max_depth_m)]
    if valid.size < minimum_valid_pixels:
        return None

    z = float(np.median(valid))
    u = (box_x0 + box_x1 - 1) / 2.0
    v = (box_y0 + box_y1 - 1) / 2.0
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    distance = math.sqrt(x * x + y * y + z * z)
    return distance if math.isfinite(distance) else None
