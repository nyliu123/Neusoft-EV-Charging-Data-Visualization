"""把 ADS 质量统计整理成大屏摘要与可核对的详情分组。"""


def build_quality_report(row):
    def metric(key, label, source, denominator=None, unit="单", note=""):
        # 异常比例始终明确分母；金额和覆盖率不强行套用“订单占比”。
        value = row[source]
        base = row[denominator] if denominator else None
        return {
            "key": key, "label": label, "value": value or 0, "unit": unit,
            "rate": round(value / base * 100, 1) if base and value is not None else None,
            "note": note,
        }

    # 各组覆盖清洗过滤、费用估算、站点关联和电池字段有效性。
    groups = [
        {"title": "订单与时间", "metrics": [
            metric("rawOrders", "原始订单", "raw_orders", unit="单", note="清洗前全部订单"),
            metric("validOrders", "有效充电订单", "valid_orders", "raw_orders", note="正电量且起止小时在 0–23 时"),
            metric("invalidKwh", "非正或缺失电量", "invalid_kwh", "raw_orders"),
            metric("invalidHours", "起止小时异常", "invalid_hours", "raw_orders"),
            metric("missingCreated", "缺失创建时间", "missing_created", "raw_orders"),
            metric("missingEnded", "缺失结束时间", "missing_ended", "raw_orders"),
            metric("yearCorrected", "年份校正记录", "year_corrected", "raw_orders", note="0014/0015 年按语义校正"),
            metric("invalidDuration", "异常充电时长", "invalid_duration", "raw_orders", note="不在 (0,24] 小时"),
            metric("duplicateSessions", "重复会话标识", "duplicate_session_ids", "raw_orders"),
            metric("missingSessions", "缺失会话标识", "missing_session_ids", "raw_orders"),
            metric("invalidElapsed", "清洗后起止时间异常", "invalid_elapsed_sessions", "valid_orders", note="结束时间不晚于开始时间或无法解析"),
            metric("missingUsers", "缺失用户标识", "missing_user_ids", "raw_orders"),
        ]},
        {"title": "费用口径", "metrics": [
            metric("zeroFees", "原始零费用订单", "raw_zero_fee_orders", "raw_orders"),
            metric("positiveFees", "原始正费用订单", "raw_positive_fee_orders", "raw_orders"),
            metric("negativeFees", "原始负费用订单", "negative_fee_orders", "raw_orders"),
            metric("estimatedFees", "有效订单中按规则估算", "estimated_fee_orders", "valid_orders", note="原始费用为 0，原值保留"),
            metric("rawRecordedAmount", "原始费用合计", "raw_recorded_amount", unit="元", note="包括被排除的异常订单费用"),
        ]},
        {"title": "站点与设备", "metrics": [
            metric("rawStations", "原始站点", "raw_stations", unit="站"),
            metric("validStations", "有效站点", "valid_stations", "raw_stations", unit="站", note="名称不为空"),
            metric("missingStationNames", "站点名称缺失", "missing_station_names", "raw_stations", unit="站"),
            metric("missingStationAddresses", "站点地址缺失", "missing_station_addresses", "raw_stations", unit="站"),
            metric("invalidDeviceCounts", "设备数异常", "invalid_device_counts", "raw_stations", unit="站", note="设备数非正或缺失"),
            metric("unmatchedStations", "订单未匹配站点", "unmatched_station_orders", "valid_orders"),
        ]},
        {"title": "电池与关联", "metrics": [
            metric("rawBattery", "原始电池记录", "raw_battery", unit="条"),
            metric("validBattery", "有效电池记录", "valid_battery", "raw_battery", unit="条", note="SOC 合理且电压为正"),
            metric("matchedBattery", "设备与会话标识数值重合", "matched_battery_sessions", "valid_orders", note="esd 为设备标识、sessionId 为会话标识；缺少映射，数值重合不代表实际关联"),
            metric("invalidSoc", "SOC 异常", "invalid_soc", "raw_battery", unit="条"),
            metric("invalidPackVoltage", "电池包电压异常", "invalid_pack_voltage", "raw_battery", unit="条"),
            metric("invalidCurrent", "充电电流异常", "invalid_charge_current", "raw_battery", unit="条", note="不在 -200–0 A"),
            metric("invalidTemperature", "电池温度异常", "invalid_temperature", "raw_battery", unit="条", note="最高或最低温不在 -40–85℃"),
            metric("invalidEnergy", "可用能量异常", "invalid_available_energy", "raw_battery", unit="条"),
            metric("invalidCapacity", "可用容量异常", "invalid_available_capacity", "raw_battery", unit="条"),
            metric("invertedCellVoltage", "单体电压次序异常", "inverted_cell_voltage", "raw_battery", unit="条", note="最高单体电压低于最低单体电压"),
        ]},
    ]
    by_key = {item["key"]: item for group in groups for item in group["metrics"]}
    valid_rate = round(row["valid_orders"] / row["raw_orders"] * 100, 1)
    by_key["validOrderRate"] = {
        "key": "validOrderRate", "label": "有效订单率", "value": valid_rate,
        "unit": "%", "rate": None, "note": "有效订单占原始订单",
    }
    # 大屏选跨域的十二项，四列三行填充质量区域；完整口径留在详情页。
    summary_keys = (
        "validOrderRate", "validOrders", "invalidKwh", "invalidHours",
        "invalidDuration", "yearCorrected", "duplicateSessions", "estimatedFees",
        "unmatchedStations", "invalidDeviceCounts", "matchedBattery", "invalidSoc",
    )
    return {
        "validOrders": row["valid_orders"],
        "invalidKwh": row["invalid_kwh"],
        "invalidDuration": row["invalid_duration"],
        "yearCorrected": row["year_corrected"],
        "batteryRecords": row["valid_battery"],
        "validOrderRate": valid_rate,
        "summaryCards": [by_key[key] for key in summary_keys],
        "groups": groups,
        "notes": [
            "订单年份 0014/0015 按数据语义校正为 2014/2015。",
            "有效订单要求正电量且起止小时在 0–23 时；时长异常单独统计，不一定剔除订单。",
            "电池仅对 SOC 与包电压做整行过滤；电流、温度和可用能量异常置为空值。",
            "esd 与 sessionId 分属设备和会话标识；当前只统计数值重合，不能作为跨表关联覆盖率。",
            "站点名称为空的记录被过滤；地址及设备数异常保留站点但对应清洗字段为空或补默认值。",
            "零费用订单按分时规则估算，原始费用与估算费用分别列示。",
            "异常维度可能在同一记录上重叠，不能把异常数量直接相加。",
        ],
    }
