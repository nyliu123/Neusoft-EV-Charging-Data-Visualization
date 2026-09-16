"""基于 cleanData.py 注册的原始/DWD 视图生成并保存 ADS 分析表。"""

# 统一使用同一 JDBC 连接配置，避免不同分析表写入不同数据库。
JDBC_URL = "jdbc:mysql://localhost:3306/car_data?useUnicode=true&characterEncoding=utf8&useSSL=false"
JDBC_OPTIONS = {
    "url": JDBC_URL,
    "user": "root",
    "password": "123456",
    "driver": "com.mysql.cj.jdbc.Driver",
}


def save_table(frame, table, csv_path=None):
    """同一分析结果可同时保存为 CSV 与 MySQL 表；重跑时覆盖旧结果。"""
    if csv_path:
        frame.write.mode("overwrite").csv(csv_path, header=True)
    frame.write.format("jdbc").options(**JDBC_OPTIONS).option("dbtable", table).save(mode="overwrite")


ANALYSES = (
    # 分析1（桩型运营）：有效订单、电量、原始费用及有效充电时长。
    ("ads_facility", "data/ads/ads_facility.csv", """
        SELECT facility_type_name,
               COUNT(*) AS total_count,
               ROUND(SUM(kwhTotal), 2) AS total_kwh,
               ROUND(AVG(kwhTotal), 2) AS avg_kwh,
               ROUND(SUM(charging_fees), 2) AS total_charging_fees,
               ROUND(AVG(charging_fees), 2) AS avg_charging_fees,
               ROUND(AVG(chargeTimeHrs_clean), 2) AS avg_chargeTimeHrs
        FROM orders_dwd
        GROUP BY facility_type_name
        ORDER BY total_charging_fees DESC
    """),
    # 分析2（月度趋势）：订单、电量、原始费用及零费用订单的规则估算费用。
    ("ads_monthly", "data/ads/ads_monthly.csv", """
        SELECT date_format(created_time, 'yyyy-MM') AS month,
               COUNT(*) AS orders, ROUND(SUM(kwhTotal), 2) AS total_kwh,
               ROUND(SUM(charging_fees), 2) AS recorded_fees,
               ROUND(SUM(CASE WHEN charging_fees = 0 THEN estimated_charging_fees ELSE 0 END), 2) AS estimated_fees
        FROM orders_dwd WHERE created_time IS NOT NULL GROUP BY date_format(created_time, 'yyyy-MM')
    """),
    # 分析3（小时分布）：订单、电量及有效充电时长，供需求峰谷分析。
    ("ads_hourly", "data/ads/ads_hourly.csv", """
        SELECT startTime AS hour, COUNT(*) AS orders,
               ROUND(SUM(kwhTotal), 2) AS total_kwh,
               ROUND(AVG(chargeTimeHrs_clean), 2) AS avg_duration
        FROM orders_dwd GROUP BY startTime
    """),
    # 分析4（站点负荷）：站点订单、电量，以及清洗后的地址和设备数量。
    ("ads_station", "data/ads/ads_station.csv", """
        SELECT o.stationId, s.station_name, s.address_clean AS address,
               MAX(s.device_count_clean) AS devices, COUNT(*) AS orders,
               ROUND(SUM(o.kwhTotal), 2) AS total_kwh
        FROM orders_dwd o LEFT JOIN stations_dwd s ON o.stationId = s.stationId
        GROUP BY o.stationId, s.station_name, s.address_clean
    """),
    # 分析5（用户行为）：订单频次、电量和访问站点数，供复充分析。
    ("ads_user", "data/ads/ads_user.csv", """
        SELECT userId, COUNT(*) AS orders, ROUND(SUM(kwhTotal), 2) AS total_kwh,
               COUNT(DISTINCT stationId) AS visited_stations,
               ROUND(AVG(kwhTotal), 2) AS avg_kwh
        FROM orders_dwd GROUP BY userId
    """),
    # 分析6（费用构成）：按桩型拆分原始费用与估算费用，避免混为实际收入。
    ("ads_revenue", "data/ads/ads_revenue.csv", """
        SELECT facility_type_name, COUNT(*) AS orders,
               SUM(CASE WHEN charging_fees > 0 THEN 1 ELSE 0 END) AS recorded_orders,
               SUM(CASE WHEN charging_fees = 0 THEN 1 ELSE 0 END) AS estimated_orders,
               ROUND(SUM(charging_fees), 2) AS recorded_fees,
               ROUND(SUM(CASE WHEN charging_fees = 0 THEN estimated_charging_fees ELSE 0 END), 2) AS estimated_fees
        FROM orders_dwd GROUP BY facility_type_name
    """),
    # 分析7（电池状态）：按 20% SOC 分档，SOC=100 归入最后一档。
    ("ads_battery", "data/ads/ads_battery.csv", """
        SELECT CASE WHEN soc = 100 THEN 4 ELSE CAST(FLOOR(soc / 20) AS INT) END AS soc_band,
               COUNT(*) AS records, ROUND(AVG(max_temperature_clean), 2) AS avg_max_temperature,
               ROUND(AVG(charge_current_clean), 2) AS avg_current
        FROM battery_dwd GROUP BY CASE WHEN soc = 100 THEN 4 ELSE CAST(FLOOR(soc / 20) AS INT) END
    """),
)


def save_analyses(spark):
    """执行全部 ADS 分析；桩型运营结果仍在终端打印供人工核对。"""
    for table, csv_path, query in ANALYSES:
        frame = spark.sql(query)
        if table == "ads_facility":
            frame.show()
        save_table(frame, table, csv_path)

    # 分析8（数据质量）：设备 esd 与会话 sessionId 只审计数值重合，不能当作已验证的关联。
    quality = spark.sql("""
        WITH order_checks AS (
            SELECT COUNT(*) AS raw_orders,
                   SUM(CASE WHEN kwhTotal <= 0 OR kwhTotal IS NULL THEN 1 ELSE 0 END) AS invalid_kwh,
                   SUM(CASE WHEN startTime NOT BETWEEN 0 AND 23 OR endTime NOT BETWEEN 0 AND 23
                                 OR startTime IS NULL OR endTime IS NULL THEN 1 ELSE 0 END) AS invalid_hours,
                   SUM(CASE WHEN created IS NULL OR TRIM(created) = '' THEN 1 ELSE 0 END) AS missing_created,
                   SUM(CASE WHEN ended IS NULL OR TRIM(ended) = '' THEN 1 ELSE 0 END) AS missing_ended,
                   SUM(CASE WHEN created RLIKE '^00(14|15)-' THEN 1 ELSE 0 END) AS year_corrected,
                   SUM(CASE WHEN chargeTimeHrs <= 0 OR chargeTimeHrs > 24 OR chargeTimeHrs IS NULL
                                 THEN 1 ELSE 0 END) AS invalid_duration,
                   COUNT(sessionId) - COUNT(DISTINCT sessionId) AS duplicate_session_ids,
                   SUM(CASE WHEN sessionId IS NULL THEN 1 ELSE 0 END) AS missing_session_ids,
                   SUM(CASE WHEN userId IS NULL THEN 1 ELSE 0 END) AS missing_user_ids,
                   SUM(CASE WHEN charging_fees < 0 THEN 1 ELSE 0 END) AS negative_fee_orders,
                   SUM(CASE WHEN charging_fees = 0 THEN 1 ELSE 0 END) AS raw_zero_fee_orders,
                   SUM(CASE WHEN charging_fees > 0 THEN 1 ELSE 0 END) AS raw_positive_fee_orders,
                   ROUND(SUM(charging_fees), 2) AS raw_recorded_amount
            FROM orders
        ),
        cleaned_orders AS (
            SELECT COUNT(*) AS valid_orders,
                   SUM(CASE WHEN charging_fees = 0 THEN 1 ELSE 0 END) AS estimated_fee_orders,
                   SUM(CASE WHEN created_time IS NULL OR ended_time IS NULL OR ended_time <= created_time
                                 THEN 1 ELSE 0 END) AS invalid_elapsed_sessions
            FROM orders_dwd
        ),
        station_checks AS (
            SELECT COUNT(*) AS raw_stations,
                   SUM(CASE WHEN station_name IS NULL OR TRIM(station_name) = '' THEN 1 ELSE 0 END) AS missing_station_names,
                   SUM(CASE WHEN address IS NULL OR TRIM(address) = '' THEN 1 ELSE 0 END) AS missing_station_addresses,
                   SUM(CASE WHEN device_count <= 0 OR device_count IS NULL THEN 1 ELSE 0 END) AS invalid_device_counts
            FROM stations
        ),
        cleaned_stations AS (SELECT COUNT(*) AS valid_stations FROM stations_dwd),
        battery_checks AS (
            SELECT COUNT(*) AS raw_battery,
                   SUM(CASE WHEN soc NOT BETWEEN 0 AND 100 OR soc IS NULL THEN 1 ELSE 0 END) AS invalid_soc,
                   SUM(CASE WHEN pack_voltage <= 0 OR pack_voltage IS NULL THEN 1 ELSE 0 END) AS invalid_pack_voltage,
                   SUM(CASE WHEN charge_current NOT BETWEEN -200 AND 0 OR charge_current IS NULL
                                 THEN 1 ELSE 0 END) AS invalid_charge_current,
                   SUM(CASE WHEN max_temperature NOT BETWEEN -40 AND 85 OR min_temperature NOT BETWEEN -40 AND 85
                                 OR max_temperature IS NULL OR min_temperature IS NULL THEN 1 ELSE 0 END) AS invalid_temperature,
                   SUM(CASE WHEN available_energy < 0 OR available_energy IS NULL THEN 1 ELSE 0 END) AS invalid_available_energy,
                   SUM(CASE WHEN available_capacity < 0 OR available_capacity IS NULL THEN 1 ELSE 0 END) AS invalid_available_capacity,
                   SUM(CASE WHEN max_cell_voltage < min_cell_voltage THEN 1 ELSE 0 END) AS inverted_cell_voltage
            FROM battery
        ),
        cleaned_battery AS (SELECT COUNT(*) AS valid_battery FROM battery_dwd),
        matches AS (
            SELECT SUM(CASE WHEN s.stationId IS NULL THEN 1 ELSE 0 END) AS unmatched_station_orders,
                   COUNT(DISTINCT CASE WHEN b.esd IS NOT NULL THEN o.sessionId END) AS matched_battery_sessions
            FROM orders_dwd o
            LEFT JOIN stations_dwd s ON o.stationId = s.stationId
            LEFT JOIN battery_dwd b ON o.sessionId = b.esd
        )
        SELECT * FROM order_checks CROSS JOIN cleaned_orders CROSS JOIN station_checks
             CROSS JOIN cleaned_stations CROSS JOIN battery_checks CROSS JOIN cleaned_battery
             CROSS JOIN matches
    """)
    save_table(quality, "ads_quality", "data/ads/ads_quality.csv")
