"""东软汽车充电桩数据分析可视化大屏 API。"""

import math

from flask import Flask, request
from flask_cors import CORS

from analytics import build_dashboard, get_store
from utils.response import error, success

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.route('/')
def service_status():
    return success({"service": "EV Charging Analytics API", "status": "running"})

@app.route('/api/health')
def health():
    return success({"api": "ok"})


@app.route('/api/dashboard')
def dashboard():
    try:
        return success(build_dashboard())
    except Exception as exc:
        app.logger.exception("dashboard build failed")
        return error(msg=f"数据分析失败：{exc}", code=500)


@app.route('/api/predict/duration', methods=['GET', 'POST'])
def predict_duration():
    payload = request.get_json(silent=True) or request.args
    try:
        kwh = float(payload.get('kwh', 8))
        start_hour = int(payload.get('startHour', 18))
        facility_type = int(payload.get('facilityType', 3))
        manager_vehicle = int(payload.get('managerVehicle', 0))
        weekday = int(payload.get('weekday', 0))
        if not 0 < kwh <= 60:
            raise ValueError('充电量须在 0-60 kWh 之间')
        if not 0 <= start_hour <= 23 or not 0 <= weekday <= 6:
            raise ValueError('小时或星期参数超出范围')
        if facility_type not in (1, 2, 3, 4) or manager_vehicle not in (0, 1):
            raise ValueError('桩型或车辆类型参数无效')
        # 电池参数可选；空输入保持缺失，避免用零伪造 SOC、温度或电功率。
        battery_limits = {
            'soc': (0, 100), 'packVoltage': (1, 1000),
            'chargeCurrent': (-1000, 1000),
            'maxTemperature': (-50, 150), 'minTemperature': (-50, 150),
            'availableEnergy': (0, 200), 'availableCapacity': (0, 1000),
            'maxCellVoltage': (0, 10), 'minCellVoltage': (0, 10),
        }
        battery = {}
        for name, (lower, upper) in battery_limits.items():
            raw = payload.get(name)
            if raw is None or raw == '':
                continue
            value = float(raw)
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f'{name} 参数超出范围')
            battery[name] = value
        if battery.get('minTemperature', -50) > battery.get('maxTemperature', 150):
            raise ValueError('最低温度不能高于最高温度')
        if battery.get('minCellVoltage', 0) > battery.get('maxCellVoltage', 10):
            raise ValueError('最低单体电压不能高于最高单体电压')
        result = get_store().predict_duration(
            kwh, start_hour, facility_type, manager_vehicle, weekday, battery
        )
        return success(result)
    except (TypeError, ValueError) as exc:
        return error(msg=str(exc), code=400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
