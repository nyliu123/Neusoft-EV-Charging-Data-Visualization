"""用户行为，以及原始费用与分时估算费用的分项分析。"""

from collections import Counter, defaultdict


FREQUENCY_GROUPS = (
    ("仅 1 单", lambda count: count == 1),
    ("2–5 单", lambda count: 2 <= count <= 5),
    ("6–20 单", lambda count: 6 <= count <= 20),
    ("21 单以上", lambda count: count >= 21),
)
TIME_GROUPS = (
    ("夜间 0–7 时", lambda hour: hour < 8),
    ("上午 8–11 时", lambda hour: 8 <= hour < 12),
    ("下午 12–15 时", lambda hour: 12 <= hour < 16),
    ("晚高峰 16–19 时", lambda hour: 16 <= hour < 20),
    ("夜晚 20–23 时", lambda hour: hour >= 20),
)


def _favorite(counts):
    # 平票按名称固定顺序处理，避免结果依赖 CSV 行顺序。
    return sorted(counts.items(), key=lambda pair: (-pair[1], str(pair[0])))[0][0]


def analyze_user_business(orders, facility_names, raw_positive_fee_count=0, raw_recorded_amount=0.0):
    by_user = defaultdict(list)
    for order in orders:
        by_user[order["userId"]].append(order)

    platform_users = Counter()
    time_users = Counter()
    facility_users = Counter()
    frequency_groups = Counter()
    loyalty_users = 0
    user_points = []
    for user_id, rows in by_user.items():
        count = len(rows)
        total_kwh = sum(row["kwh"] for row in rows)
        platform = _favorite(Counter(row["platform"] for row in rows))
        platform_users[platform] += 1
        time_group = _favorite(Counter(
            next(name for name, matches in TIME_GROUPS if matches(row["startHour"]))
            for row in rows
        ))
        time_users[time_group] += 1
        facility = _favorite(Counter(row["facilityType"] for row in rows))
        facility_users[facility_names.get(facility, "其他类型")] += 1
        group = next(name for name, matches in FREQUENCY_GROUPS if matches(count))
        frequency_groups[group] += 1
        if max(Counter(row["stationId"] for row in rows).values()) / count >= 0.5:
            loyalty_users += 1
        user_points.append({
            "userId": user_id,
            "orders": count,
            "avgKwh": round(total_kwh / count, 2),
            "totalKwh": round(total_kwh, 2),
            "segment": group,
        })

    fee_total = sum(order["fee"] for order in orders)
    estimated_total = sum(order["estimatedFee"] for order in orders)
    paid = [order for order in orders if order["fee"] > 0]
    estimated_orders = sum(order["estimatedFee"] > 0 for order in orders)
    monthly = defaultdict(lambda: {"amount": 0.0, "estimatedAmount": 0.0, "paidOrders": 0, "estimatedOrders": 0, "orders": 0})
    facility_fee = defaultdict(lambda: {"amount": 0.0, "estimatedAmount": 0.0, "paidOrders": 0, "estimatedOrders": 0, "orders": 0})
    for order in orders:
        month = order["created"].strftime("%Y-%m")
        month_item = monthly[month]
        month_item["orders"] += 1
        month_item["amount"] += order["fee"]
        month_item["estimatedAmount"] += order["estimatedFee"]
        facility_item = facility_fee[facility_names.get(order["facilityType"], "其他类型")]
        facility_item["orders"] += 1
        facility_item["amount"] += order["fee"]
        facility_item["estimatedAmount"] += order["estimatedFee"]
        if order["fee"] > 0:
            month_item["paidOrders"] += 1
            facility_item["paidOrders"] += 1
        if order["estimatedFee"] > 0:
            month_item["estimatedOrders"] += 1
            facility_item["estimatedOrders"] += 1

    return {
        "users": {
            "platformPreference": [
                {"name": name.upper() if name == "ios" else name.title(), "value": value}
                for name, value in sorted(platform_users.items(), key=lambda pair: -pair[1])
            ],
            "frequencySegments": [
                {"name": name, "value": frequency_groups[name]}
                for name, _ in FREQUENCY_GROUPS
            ],
            "timePreference": [
                {"name": name, "value": time_users[name]}
                for name, _ in TIME_GROUPS
            ],
            "facilityPreference": [
                {"name": name, "value": value}
                for name, value in sorted(facility_users.items(), key=lambda pair: -pair[1])
            ],
            "points": sorted(user_points, key=lambda item: item["orders"]),
            "repeatUsers": sum(len(rows) > 1 for rows in by_user.values()),
            "stationLoyaltyUsers": loyalty_users,
            "note": "平台偏好为每位用户在样本中最常使用的平台；不代表用户对未用平台的主观评价",
        },
        "revenue": {
            "recordedAmount": round(fee_total, 2),
            "estimatedAmount": round(estimated_total, 2),
            "combinedAmount": round(fee_total + estimated_total, 2),
            "paidOrders": len(paid),
            "estimatedOrders": estimated_orders,
            "paidOrderRate": round(len(paid) / len(orders) * 100, 1),
            "avgPaidFee": round(fee_total / len(paid), 2) if paid else 0.0,
            "rawRecordedAmount": round(raw_recorded_amount, 2),
            "rawPositiveFeeOrders": raw_positive_fee_count,
            "excludedRecordedAmount": round(raw_recorded_amount - fee_total, 2),
            "excludedRecordedOrders": raw_positive_fee_count - len(paid),
            "monthly": [
                {"month": month, "amount": round(item["amount"], 2),
                 "estimatedAmount": round(item["estimatedAmount"], 2),
                 "combinedAmount": round(item["amount"] + item["estimatedAmount"], 2),
                 "paidOrders": item["paidOrders"], "estimatedOrders": item["estimatedOrders"], "orders": item["orders"]}
                for month, item in sorted(monthly.items())
            ],
            "facility": [
                {"name": name, "amount": round(item["amount"], 2),
                 "estimatedAmount": round(item["estimatedAmount"], 2),
                 "combinedAmount": round(item["amount"] + item["estimatedAmount"], 2),
                 "paidOrders": item["paidOrders"], "estimatedOrders": item["estimatedOrders"], "orders": item["orders"]}
                for name, item in sorted(facility_fee.items(), key=lambda pair: -(pair[1]["amount"] + pair[1]["estimatedAmount"]))
            ],
            "note": "零费用订单按分时估算规则估算；原始费用与估算费用分开列示。零电量收费记录未纳入有效充电订单。缺少成本，无法计算利润。",
        },
    }
