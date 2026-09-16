"""读取 cleanData.py 写入 MySQL 的清洗明细和质量口径。"""

import pymysql


TABLES = ("dwd_orders", "dwd_stations", "dwd_battery", "ads_quality")


def load_cleaned_tables():
    connection = pymysql.connect(
        host="localhost", port=3306, user="root", password="123456",
        database="car_data", charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            result = {}
            for table in TABLES:
                cursor.execute(f"SELECT * FROM `{table}`")
                result[table] = cursor.fetchall()
            return result
    finally:
        connection.close()
