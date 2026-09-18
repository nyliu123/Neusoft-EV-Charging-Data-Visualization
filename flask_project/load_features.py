"""充电负荷预测的特征工程：按自然日聚合、站点规模窗口与特征行构造。

与时长模型的 duration_features.py 对应：这里只负责把订单变成特征，
拟合与评估在 load_model.py。
"""

from collections import defaultdict
from datetime import timedelta


WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

STATION_WINDOW = 7          # 站点规模的回看天数
LAG_STEPS = (7, 14)         # 周滞后：上周、上上周同一天

# 特征顺序与 feature_row 的拼装顺序一致，供说明与核对使用。
FEATURE_NAMES = [
    "截距", "趋势", "lag7", "lag14", "近7天活跃站点数",
    "周一", "周二", "周三", "周四", "周五", "周六",
    "趋势×周一", "趋势×周二", "趋势×周三", "趋势×周四", "趋势×周五", "趋势×周六",
]


def daily_series(orders):
    """按自然日聚合：当日充电量，以及当日出现过的站点集合。"""
    daily = defaultdict(float)
    stations_by_day = defaultdict(set)
    for order in orders:
        day = order["created"].date()
        daily[day] += order["kwh"]
        stations_by_day[day].add(order["stationId"])
    return daily, stations_by_day


def calendar_days(daily):
    """补齐首末日之间没有订单的日期，返回连续日期与对应充电量（无订单按 0）。"""
    first_day, last_day = min(daily), max(daily)
    dates = []
    current = first_day
    while current <= last_day:
        dates.append(current)
        current += timedelta(days=1)
    return dates, [daily.get(day, 0.0) for day in dates]


def station_window(dates, stations_by_day, index):
    """目标日之前 7 天内出现过的站点数，只用已知数据。

    预测期的 index 会越过数据末尾，这里夹到最后一个已知日，7 天预测共用同一个值。
    """
    end = min(index, len(dates))
    start = max(0, end - STATION_WINDOW)
    seen = set()
    for day in dates[start:end]:
        seen |= stations_by_day[day]
    return float(len(seen))


def station_series(dates, stations_by_day, extra_days=0):
    """整段日期的站点规模序列；末尾多算 extra_days 天供预测期复用最后一个已知值。"""
    return [station_window(dates, stations_by_day, index) for index in range(len(dates) + extra_days)]


def feature_row(values, stations, index, trend, weekday):
    """一行特征：趋势、周滞后、近 7 天活跃站点数，以及星期哑变量和趋势×星期的交互。

    lag7 / lag14 是以周为单位变化的量：只有趋势时工作日上行了、周末没动，
    公共趋势会把周末顶高、把工作日压低，周内振幅被压平（回测只有 140，实际约 180）。
    站点数解释的是量级：活跃站点从 38 涨到 92，日负荷同步从 14 涨到 151。
    """
    lags = [values[index - step] if index >= step else 0.0 for step in LAG_STEPS]
    return (
        [1.0, trend, *lags, stations[index]]
        + [1.0 if weekday == wd else 0.0 for wd in range(6)]
        + [trend if weekday == wd else 0.0 for wd in range(6)]
    )
