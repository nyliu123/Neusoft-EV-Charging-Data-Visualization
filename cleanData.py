"""
充电桩的数据清洗：
    1.明确数据源：
        1.dsv13r2.csv
        2.nvv2t.csv
        3.nvv2t_md_end.csv
    2.输出（数据仓库）：
        1.清洗后的单表csv文件
        2.三表联合后的完整的宽表csv文件
        3.核心业务统计结果的csv文件
        4.导入到数据库中（MySQL）
"""
# 导入核心依赖
import os
from ads_analysis import save_analyses, save_table
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType,DoubleType,LongType,StringType,FloatType,IntegerType

# 1.创建Spark对象：SparkSession唯一入口
HERE = os.path.dirname(os.path.abspath(__file__))
CONNECTOR_PATH = os.path.join(HERE, "mysql-connector-java-8.0.27.jar")

spark = SparkSession.builder \
    .appName("cleanData") \
    .master("local[*]") \
    .config("spark.driver.extraClassPath", CONNECTOR_PATH) \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

print("="*80)
print(f"SparkSession对象创建成功,Spark对象为：{spark}")
print("="*80)

# 2.读取数据 & 自定义Schema（匹配实际的数据类型）
# 2.1 充电订单表Schema
sc_orders = (StructType()
             .add("sessionId",LongType())
             .add("kwhTotal",FloatType())
             .add("charging_fees",FloatType())
             .add("created",StringType())
             .add("ended",StringType())
             .add("startTime",IntegerType())
             .add("endTime",IntegerType())
             .add("chargeTimeHrs",FloatType())
             .add("weekday",StringType())
             .add("platform",StringType())
             .add("userId",LongType())
             .add("stationId",LongType())
             .add("locationId",LongType())
             .add("managerVehicle",IntegerType())
             .add("facilityType",IntegerType())
             .add("Mon",IntegerType())
             .add("Tues",IntegerType())
             .add("Wed",IntegerType())
             .add("Thurs",IntegerType())
             .add("Fri",IntegerType())
             .add("Sat",IntegerType())
             .add("Sun",IntegerType())
             )
# 2.2 电池检测表（dsv13r2.csv）
sc_battery = (StructType()
              .add("esd",LongType())
              .add("record_time",StringType())
              .add("soc",FloatType())
              .add("pack_voltage",FloatType())
              .add("charge_current",FloatType())
              .add("max_cell_voltage",FloatType())
              .add("min_cell_voltage",FloatType())
              .add("max_temperature",FloatType())
              .add("min_temperature",FloatType())
              .add("available_energy",FloatType())
              .add("available_capacity",FloatType())
              )

# 2.3 充电桩表（nvv2t.csv）
sc_stations = (StructType()
               .add("stationId",LongType())
               .add("locationId",LongType())
               .add("facilityType",IntegerType())
               .add("station_name",StringType())
               .add("address",StringType())
               .add("device_count",IntegerType())
               .add("open_time",StringType())
               .add("update_time",StringType())
               )
# 3.读取数据
df_orders = spark.read.csv("data/nvv2t.csv",header=True,schema=sc_orders)
df_battery = spark.read.csv("data/dsv13r2.csv",header=True,schema=sc_battery)
df_stations = spark.read.csv("data/nvv2t_md_end.csv",header=True,schema=sc_stations)

# 打印原始数据信息
print("="*80)
print(f"原始数据信息：")
print(f"充电订单表：{df_orders.count()}条数据")
print(f"电池检测表：{df_battery.count()}条数据")
print(f"充电站信息表：{df_stations.count()}条数据")
print("="*80)

# 注册临时视图，SparkSQL使用
df_orders.createTempView("orders")
df_battery.createTempView("battery")
df_stations.createTempView("stations")

# 4.数据清洗 DWD层
df_orders_dwd = spark.sql("""
    SELECT
        *,
        -- 时间字段标准化：字符串转成对应的时间类型
        -- 原始年份 0014/0015 表示 2014/2015，先校正再转时间
        to_timestamp(regexp_replace(created, '^00([0-9]{2})-', '20$1-'),'yyyy-MM-dd HH:mm:ss') AS created_time,
        to_timestamp(regexp_replace(ended, '^00([0-9]{2})-', '20$1-'),'yyyy-MM-dd HH:mm:ss') AS ended_time,
        -- 用电时段划分
        CASE
            WHEN startTime between 0 AND 6 THEN '低谷'
            WHEN startTime between 7 AND 11 THEN '平时'
            WHEN startTime between 12 AND 17 THEN '高峰'
            WHEN startTime between 18 AND 23 THEN '尖峰'
            ELSE '其他'
        END AS stage,
        -- 充电庄的类型
        CASE
            WHEN facilityType = 1 THEN '交流充电桩'
            WHEN facilityType = 2 THEN '直流充电桩'
            WHEN facilityType = 3 THEN '交直流一体充电桩'
            ELSE '其他类型'
        END AS facility_type_name,
        -- 费用为 0 时仅给出运营估算值；原始 charging_fees 字段始终保留
        CASE 
            WHEN charging_fees=0 AND startTime between 0 AND 6 THEN kwhTotal * 1.2
            WHEN charging_fees=0 AND startTime between 7 AND 11 THEN kwhTotal * 1.5
            WHEN charging_fees=0 AND startTime between 12 AND 17 THEN kwhTotal * 1.8
            WHEN charging_fees=0 AND startTime between 18 AND 23 THEN kwhTotal * 2.0
            Else charging_fees
        END AS estimated_charging_fees,
        -- 修正充电时长
        CASE
            WHEN chargeTimeHrs between 0 AND 24 THEN chargeTimeHrs
            ELSE NULL
        END AS chargeTimeHrs_clean
    FROM orders
    WHERE kwhTotal > 0
    AND startTime BETWEEN 0 AND 23
    AND endTime BETWEEN 0 AND 23
""")

# 存储当前dwd数据
df_orders_dwd.write.mode("overwrite").csv("data/dwd/dwd_orders.csv",header=True)
df_orders_dwd.createTempView("orders_dwd")
print(f"DWD层充电订单表：{df_orders_dwd.count()}条数据")


df_battery_dwd = spark.sql("""
    SELECT
        *,
        -- 电池采样时间精确到分钟，用于核验充电开始前是否可获得该状态。
        to_timestamp(record_time, 'yyyy/M/d H:mm') AS record_time_clean,
        -- 充电电流清洗
        CASE
            -- 原始数据为充电负电流，保留合理的车辆充电工作区间
            WHEN charge_current BETWEEN -200 AND 0 THEN charge_current
            ELSE NULL
        END AS charge_current_clean,
        -- 电池最高和最低温度清洗
        CASE
            WHEN max_temperature BETWEEN -40 AND 85 THEN max_temperature
            ELSE NULL
        END AS max_temperature_clean,
        CASE
            WHEN min_temperature BETWEEN -40 AND 85 THEN min_temperature
            ELSE NULL
        END AS min_temperature_clean,
        -- 可用能量清洗
        CASE
            WHEN available_energy >=0 THEN available_energy
            ELSE NULL
        END AS available_energy_clean,
        -- 可用容量清洗
        CASE
            WHEN available_capacity >=0 THEN available_capacity
            ELSE NULL
        END AS available_capacity_clean
    FROM
        battery
    WHERE soc BETWEEN 0 AND 100
    AND pack_voltage > 0
""")

# 存储数据
df_battery_dwd.write.mode("overwrite").csv("data/dwd/dwd_battery.csv",header=True)
df_battery_dwd.createTempView("battery_dwd")
print(f"DWD层电池检测表：{df_battery_dwd.count()}条数据")

df_stations_dwd = spark.sql("""
    SELECT
        *,
        -- 充电桩类型
        CASE
            WHEN facilityType = 1 THEN '交流充电桩'
            WHEN facilityType = 2 THEN '直流充电桩'
            WHEN facilityType = 3 THEN '交直流一体充电桩'
            ELSE '其他类型'
        END AS facility_type_name,
        -- 地址清洗
        CASE
            WHEN address IS NOT NULL AND address != '' THEN address
            ELSE "地址未知"
        END AS address_clean,
        -- 充电桩数量清洗
        CASE
            WHEN device_count > 0 THEN device_count
            ELSE NULL
        END AS device_count_clean
    FROM stations
    WHERE station_name IS NOT NULL AND station_name != ''
""")

# 存储数据
df_stations_dwd.write.mode("overwrite").csv("data/dwd/dwd_stations.csv",header=True)
df_stations_dwd.createTempView("stations_dwd")
print(f"DWD层充电站信息表：{df_stations_dwd.count()}条数据")

# DWS层，合并三个表的数据
df_full_data_dws = spark.sql("""
    SELECT
    n.*,
    b.*,
    s.station_name,
    s.address_clean AS address,
    s.device_count_clean AS device_count
    FROM orders_dwd n
    LEFT JOIN battery_dwd b ON n.sessionId = b.esd
    LEFT JOIN stations_dwd s ON n.stationId = s.stationId
""")

# 存储数据
df_full_data_dws.write.mode("overwrite").csv("data/dws/dws_full_data.csv",header=True)
df_full_data_dws.createTempView("full_data_dws")

# 大屏从 MySQL 读取 DWD 明细；所有 ADS 汇总统一由分析模块生成。
save_table(df_orders_dwd, "dwd_orders")
save_table(df_stations_dwd, "dwd_stations")
save_table(df_battery_dwd, "dwd_battery")
save_analyses(spark)

# 关闭
spark.stop()
