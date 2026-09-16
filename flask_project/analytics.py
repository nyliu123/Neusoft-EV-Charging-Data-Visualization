"""基于 MySQL 清洗明细的统计与轻量预测服务。"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache

from duration_model import predict_duration as model_predict_duration, train_duration_model
from duration_features import battery_from_row
from mysql_store import load_cleaned_tables
from quality_report import build_quality_report
from user_business import analyze_user_business


FACILITY_NAMES = {
    1: "交流充电桩",
    2: "直流充电桩",
    3: "交直流一体桩",
    4: "其他类型",
}
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _float(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _district(address):
    if "郑东新区" in address:
        return "郑东新区"
    if "高新区" in address:
        return "高新区"
    if "经开区" in address:
        return "经开区"
    if "航空港区" in address:
        return "航空港区"
    tail = address.split("市", 1)[-1]
    if "区" in tail:
        return tail.split("区", 1)[0] + "区"
    return "其他区域"


def _round(value, digits=2):
    return round(float(value), digits)


def _solve(matrix, vector):
    """高斯消元求解小型线性方程组。"""
    size = len(vector)
    augmented = [list(matrix[i]) + [vector[i]] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            continue
        augmented[column] = [item / divisor for item in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[index][-1] for index in range(size)]


def _ridge_fit(features, targets, penalty=0.15):
    width = len(features[0])
    gram = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for row, target in zip(features, targets):
        for left in range(width):
            rhs[left] += row[left] * target
            for right in range(width):
                gram[left][right] += row[left] * row[right]
    for index in range(1, width):
        gram[index][index] += penalty
    return _solve(gram, rhs)


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


@dataclass
class AnalyticsStore:
    orders: list
    stations: list
    battery: list
    station_by_id: dict
    duration_model: object
    duration_metrics: dict

    def predict_duration(self, kwh, start_hour, facility_type, manager_vehicle, weekday, battery=None):
        predicted = model_predict_duration(
            self.duration_model, float(kwh), int(start_hour), int(facility_type),
            int(manager_vehicle), int(weekday), battery,
        )
        half_width = self.duration_metrics["p80HalfWidth"]
        return {
            "hours": _round(predicted),
            "minutes": round(predicted * 60),
            "lower": _round(max(predicted - half_width, 0.08)),
            "upper": _round(min(predicted + half_width, 24.0)),
            "intervalCoverage": self.duration_metrics["intervalCoverage"],
            "mae": self.duration_metrics["mae"],
            "r2": self.duration_metrics["r2"],
            "sampleCount": self.duration_metrics["sampleCount"],
            "method": self.duration_metrics["method"],
            "note": "历史训练使用充电后的实际电量；输入的预计电量仅作代理。模型未经充电前场景验证。",
        }


@lru_cache(maxsize=1)
def get_store():
    tables = load_cleaned_tables()
    station_rows = tables["dwd_stations"]
    stations = []
    station_by_id = {}
    for row in station_rows:
        address = (row.get("address_clean") or "地址未知").strip()
        station = {
            "stationId": _int(row.get("stationId")),
            "stationName": (row.get("station_name") or "未命名站点").strip(),
            "address": address,
            "district": _district(address),
            "facilityType": _int(row.get("facilityType")),
            "deviceCount": max(_int(row.get("device_count_clean")), 0),
        }
        stations.append(station)
        station_by_id[station["stationId"]] = station

    battery = tables["dwd_battery"]
    battery_by_session = {_int(row.get("esd")): row for row in battery}
    orders = []
    for row in tables["dwd_orders"]:
        created = row.get("created_time")
        if created is None:
            continue
        station_id = _int(row.get("stationId"))
        station = station_by_id.get(station_id, {})
        fee = _float(row.get("charging_fees"))
        duration = _float(row.get("chargeTimeHrs_clean"), -1)
        battery_row = battery_by_session.get(_int(row.get("sessionId")))
        record_time = battery_row.get("record_time_clean") if battery_row else None
        # 原始时间只精确到分钟；超出该窗口或晚于开始的快照不能用于充电前预测。
        battery_features = battery_from_row(battery_row) if record_time and created - timedelta(minutes=1) < record_time <= created else {}
        orders.append({
            "sessionId": _int(row.get("sessionId")),
            "kwh": _float(row.get("kwhTotal")),
            "fee": fee,
            "estimatedFee": _float(row.get("estimated_charging_fees")) if fee == 0 else 0.0,
            "created": created,
            "startHour": _int(row.get("startTime")),
            "endHour": _int(row.get("endTime")),
            "duration": duration if 0 < duration <= 24 else None,
            "weekday": created.weekday(),
            "platform": (row.get("platform") or "未知").lower(),
            "userId": _int(row.get("userId")),
            "stationId": station_id,
            "locationId": _int(row.get("locationId")),
            "managerVehicle": _int(row.get("managerVehicle")),
            "facilityType": _int(row.get("facilityType")),
            "stationName": station.get("stationName", f"站点 {station_id}"),
            "district": station.get("district", "其他区域"),
            **battery_features,
        })
    model, metrics = train_duration_model(orders)
    store = AnalyticsStore(orders, stations, battery, station_by_id, model, metrics)
    quality = tables["ads_quality"][0]
    store.quality_data = quality
    store.raw_order_count = _int(quality.get("raw_orders"))
    store.raw_positive_fee_count = _int(quality.get("raw_positive_fee_orders"))
    store.raw_recorded_amount = _float(quality.get("raw_recorded_amount"))
    store.invalid_kwh_count = _int(quality.get("invalid_kwh"))
    store.invalid_duration_count = _int(quality.get("invalid_duration"))
    return store


def _station_window(dates, stations_by_day, index):
    """目标日之前 7 天内出现过的站点数，只用已知数据。

    预测期的 index 会越过数据末尾，这里夹到最后一个已知日，7 天预测共用同一个值。
    """
    end = min(index, len(dates))
    start = max(0, end - 7)
    seen = set()
    for day in dates[start:end]:
        seen |= stations_by_day[day]
    return float(len(seen))


def _load_feature_row(values, stations, index, trend, weekday):
    """一行特征：趋势、周滞后、近 7 天活跃站点数，以及星期哑变量和趋势×星期的交互。

    lag7 / lag14 是以周为单位变化的量：只有趋势时工作日上行了、周末没动，
    公共趋势会把周末顶高、把工作日压低，周内振幅被压平（回测只有 140，实际约 180）。
    站点数解释的是量级：活跃站点从 38 涨到 92，日负荷同步从 14 涨到 151。
    """
    lag7 = values[index - 7] if index >= 7 else 0.0
    lag14 = values[index - 14] if index >= 14 else 0.0
    return (
        [1.0, trend, lag7, lag14, stations[index]]
        + [1.0 if weekday == wd else 0.0 for wd in range(6)]
        + [trend if weekday == wd else 0.0 for wd in range(6)]
    )


def _backtest_rmse(dates, values, stations, horizon=7, span=120):
    """滚动回测的样本外 RMSE：每次只用截止日前的数据拟合，再预测之后 horizon 天。

    误差带要用这个值。样本内 RMSE 是拿同一批数据既拟合又打分，偏乐观，
    会把误差范围画得比实际窄、把置信度说得比实际好。
    """
    penalty = 0.15
    errors = []
    for cut in range(max(28, len(dates) - span), len(dates) - horizon + 1):
        train = values[:cut]
        scale = max(cut - 1, 1)
        features = [_load_feature_row(train, stations, index, index / scale, day.weekday())
                    for index, day in enumerate(dates[:cut])]
        coefficients = _ridge_fit(features, train, penalty=penalty)
        for step, day in enumerate(dates[cut:cut + horizon], start=1):
            index = cut + step - 1
            trend = index / scale
            predicted = max(_dot(_load_feature_row(values, stations, index, trend, day.weekday()), coefficients), 0.0)
            errors.append(predicted - values[index])
    if not errors:
        return 0.0
    return math.sqrt(sum(error * error for error in errors) / len(errors))


def _load_forecast(orders):
    daily = defaultdict(float)
    stations_by_day = defaultdict(set)
    for order in orders:
        day = order["created"].date()
        daily[day] += order["kwh"]
        stations_by_day[day].add(order["stationId"])
    first_day, last_day = min(daily), max(daily)
    dates = []
    current = first_day
    while current <= last_day:
        dates.append(current)
        current += timedelta(days=1)
    values = [daily.get(day, 0.0) for day in dates]
    scale = max(len(dates) - 1, 1)
    stations = [_station_window(dates, stations_by_day, index) for index in range(len(dates) + 7)]
    features = [_load_feature_row(values, stations, index, index / scale, day.weekday())
                for index, day in enumerate(dates)]
    coefficients = _ridge_fit(features, values, penalty=0.15)
    fitted = [_dot(row, coefficients) for row in features]
    in_sample_rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(values, fitted)) / len(values))
    # 误差带用滚动回测的样本外误差，而不是上面这个偏乐观的样本内数字。
    rmse = _backtest_rmse(dates, values, stations)
    forecast = []
    for step in range(1, 8):
        target = last_day + timedelta(days=step)
        index = len(dates) - 1 + step
        row = _load_feature_row(values, stations, index, index / scale, target.weekday())
        predicted = max(_dot(row, coefficients), 0.0)
        forecast.append({
            "date": target.isoformat(),
            "weekday": WEEKDAY_NAMES[target.weekday()],
            "value": _round(predicted),
            "lower": _round(max(predicted - rmse, 0.0)),
            "upper": _round(predicted + rmse),
        })
    # fitted 一并返回，前端把模型在历史日期上的预测和实际值画在一起，直观看出模型贴合程度。
    history = [
        {"date": day.isoformat(), "value": _round(value), "fitted": _round(fit)}
        for day, value, fit in zip(dates[-30:], values[-30:], fitted[-30:])
    ]
    return {
        "history": history,
        "forecast": forecast,
        "rmse": _round(rmse),
        "inSampleRmse": _round(in_sample_rmse),
        "method": "趋势 × 星期 + 周滞后 + 站点规模岭回归",
        "trainingDays": len(dates),
    }


def build_dashboard():
    store = get_store()
    orders = store.orders
    durations = [order["duration"] for order in orders if order["duration"] is not None]

    hourly = {hour: {"orders": 0, "kwh": 0.0, "duration": []} for hour in range(24)}
    weekday = {index: {"orders": 0, "kwh": 0.0} for index in range(7)}
    facility = defaultdict(lambda: {"orders": 0, "kwh": 0.0, "duration": []})
    platform = Counter()
    monthly = defaultdict(lambda: {"orders": 0, "kwh": 0.0})
    station_stats = defaultdict(lambda: {"orders": 0, "kwh": 0.0})
    heatmap = Counter()
    users = set()
    for order in orders:
        hour_item = hourly[order["startHour"]]
        hour_item["orders"] += 1
        hour_item["kwh"] += order["kwh"]
        if order["duration"] is not None:
            hour_item["duration"].append(order["duration"])
        weekday[order["weekday"]]["orders"] += 1
        weekday[order["weekday"]]["kwh"] += order["kwh"]
        facility_item = facility[order["facilityType"]]
        facility_item["orders"] += 1
        facility_item["kwh"] += order["kwh"]
        if order["duration"] is not None:
            facility_item["duration"].append(order["duration"])
        platform[order["platform"]] += 1
        month_key = order["created"].strftime("%Y-%m")
        monthly[month_key]["orders"] += 1
        monthly[month_key]["kwh"] += order["kwh"]
        station_stats[order["stationId"]]["orders"] += 1
        station_stats[order["stationId"]]["kwh"] += order["kwh"]
        heatmap[(order["weekday"], order["startHour"])] += 1
        users.add(order["userId"])

    district_stats = defaultdict(lambda: {"stations": 0, "devices": 0, "orders": 0, "kwh": 0.0})
    for station in store.stations:
        district_stats[station["district"]]["stations"] += 1
        district_stats[station["district"]]["devices"] += station["deviceCount"]
    for order in orders:
        district_stats[order["district"]]["orders"] += 1
        district_stats[order["district"]]["kwh"] += order["kwh"]

    soc_bins = [0] * 5
    energy_scatter = []
    max_temperatures = []
    currents = []
    for index, row in enumerate(store.battery):
        soc = _float(row.get("soc"))
        energy = _float(row.get("available_energy_clean"))
        temperature = _float(row.get("max_temperature_clean"))
        current = _float(row.get("charge_current_clean"))
        soc_bins[min(int(soc // 20), 4)] += 1
        max_temperatures.append(temperature)
        currents.append(current)
        if index % 8 == 0:
            energy_scatter.append([_round(soc, 1), _round(energy, 2), _round(temperature, 1)])

    station_ranking = sorted(
        station_stats.items(), key=lambda item: item[1]["kwh"], reverse=True
    )[:10]
    min_date = min(order["created"] for order in orders).date()
    max_date = max(order["created"] for order in orders).date()
    total_kwh = sum(order["kwh"] for order in orders)
    paid_orders = sum(order["fee"] > 0 for order in orders)
    user_business = analyze_user_business(
        orders, FACILITY_NAMES,
        raw_positive_fee_count=store.raw_positive_fee_count,
        raw_recorded_amount=store.raw_recorded_amount,
    )

    return {
        "meta": {
            "source": "MySQL 清洗明细（cleanData.py）",
            "dateRange": f"{min_date.isoformat()} 至 {max_date.isoformat()}",
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
        },
        "kpis": {
            "orders": len(orders),
            "rawOrders": store.raw_order_count,
            "totalKwh": _round(total_kwh),
            "avgKwh": _round(total_kwh / len(orders)),
            "avgDuration": _round(sum(durations) / len(durations)),
            "users": len(users),
            "stations": len(store.stations),
            "devices": sum(station["deviceCount"] for station in store.stations),
            "paidOrderRate": _round(paid_orders / len(orders) * 100, 1),
            "recordedAmount": user_business["revenue"]["recordedAmount"],
            "estimatedAmount": user_business["revenue"]["estimatedAmount"],
            "combinedAmount": user_business["revenue"]["combinedAmount"],
        },
        # ADS 质量表同时驱动大屏摘要和详情，避免两处采用不同统计口径。
        "quality": build_quality_report(store.quality_data),
        "hourly": [
            {
                "hour": f"{hour:02d}:00",
                "orders": item["orders"],
                "kwh": _round(item["kwh"]),
                "avgDuration": _round(sum(item["duration"]) / len(item["duration"])) if item["duration"] else 0,
            }
            for hour, item in hourly.items()
        ],
        "weekday": [
            {"name": WEEKDAY_NAMES[index], "orders": item["orders"], "kwh": _round(item["kwh"])}
            for index, item in weekday.items()
        ],
        "facility": [
            {
                "name": FACILITY_NAMES.get(kind, "其他类型"),
                "orders": item["orders"],
                "kwh": _round(item["kwh"]),
                "avgDuration": _round(sum(item["duration"]) / len(item["duration"])) if item["duration"] else 0,
            }
            for kind, item in sorted(facility.items())
        ],
        "platform": [
            {"name": name.upper() if name == "ios" else name.title(), "value": count}
            for name, count in platform.most_common()
        ],
        "monthly": [
            {"month": month, "orders": item["orders"], "kwh": _round(item["kwh"])}
            for month, item in sorted(monthly.items())
        ],
        "districts": [
            {"name": name, **item, "kwh": _round(item["kwh"])}
            for name, item in sorted(district_stats.items(), key=lambda pair: pair[1]["kwh"], reverse=True)
        ],
        "topStations": [
            {
                "name": store.station_by_id[station_id]["stationName"],
                "district": store.station_by_id[station_id]["district"],
                "orders": stats["orders"],
                "kwh": _round(stats["kwh"]),
            }
            for station_id, stats in station_ranking
        ],
        "heatmap": [[weekday_index, hour, heatmap[(weekday_index, hour)]] for weekday_index in range(7) for hour in range(24)],
        "battery": {
            "socDistribution": [
                {"name": label, "value": value}
                for label, value in zip(["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"], soc_bins)
            ],
            "scatter": energy_scatter,
            "avgMaxTemperature": _round(sum(max_temperatures) / len(max_temperatures), 1),
            "avgCurrent": _round(sum(currents) / len(currents), 1),
        },
        "loadPrediction": _load_forecast(orders),
        "durationModel": store.duration_metrics,
        "userBehavior": user_business["users"],
        "revenue": user_business["revenue"],
    }
