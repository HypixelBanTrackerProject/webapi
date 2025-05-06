import time


def time_since(timestamp, include_ms=True):
    """
    计算时间戳距离现在的时间差，返回中文易读字符串

    参数:
        timestamp (int/float): 时间戳（秒或毫秒）
        include_ms (bool): 是否包含毫秒精度

    返回:
        str: 时间差描述字符串，如 "3天前" 或 "5分钟后"
    """
    now = time.time()

    # 判断时间戳是秒级（10位）还是毫秒级（13位）
    if timestamp > 1e12:  # 毫秒级（如 1700000000000）
        timestamp_seconds = timestamp / 1000
    else:
        timestamp_seconds = timestamp

    delta = now - timestamp_seconds
    is_past = delta >= 0
    delta = abs(delta)

    # 定义时间单位及其对应的秒数（中文）
    time_units = (
        [
            ("年", 365 * 24 * 60 * 60),
            ("个月", 30 * 24 * 60 * 60),
            ("周", 7 * 24 * 60 * 60),
            ("天", 24 * 60 * 60),
            ("小时", 60 * 60),
            ("分钟", 60),
            ("秒", 1),
            ("毫秒", 0.001),
        ]
        if include_ms
        else [
            ("年", 365 * 24 * 60 * 60),
            ("个月", 30 * 24 * 60 * 60),
            ("周", 7 * 24 * 60 * 60),
            ("天", 24 * 60 * 60),
            ("小时", 60 * 60),
            ("分钟", 60),
            ("秒", 1),
        ]
    )

    for unit, unit_seconds in time_units:
        if delta >= unit_seconds:
            value = int(delta / unit_seconds) if unit != "毫秒" else int(delta * 1000)
            return f"{value}{unit}{'前' if is_past else '后'}"

    return "刚刚"


# # 示例用法
# if __name__ == "__main__":
#     # 测试过去的时间（秒级时间戳）
#     past_timestamp = time.time() - 3600  # 1小时前
#     print(time_since(past_timestamp))  # 输出: "1小时前"

#     # 测试未来的时间（毫秒级时间戳）
#     future_timestamp = (time.time() + 120) * 1000  # 2分钟后（毫秒级）
#     print(time_since(future_timestamp))  # 输出: "2分钟后"

#     # 测试很近的时间（毫秒级）
#     recent_timestamp = time.time() - 0.1
#     print(time_since(recent_timestamp))  # 输出: "100毫秒前"

#     # 测试极小时间差
#     print(time_since(time.time()))  # 输出: "刚刚"
