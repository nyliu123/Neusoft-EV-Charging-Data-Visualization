"""充电时长预测所需的订单、电池状态与物理派生特征。"""

import math

import numpy as np


# 电池字段与清洗后的 MySQL DWD 表一一对应；缺失关联保留 NaN 供树模型处理。
BATTERY_FIELDS = (
    "soc", "packVoltage", "chargeCurrent", "maxTemperature", "minTemperature",
    "availableEnergy", "availableCapacity", "maxCellVoltage", "minCellVoltage",
)
FEATURE_NAMES = (
    "kwh", "startHour", "facilityType", "managerVehicle", "weekday",
    *BATTERY_FIELDS,
    "powerKw", "idealHours", "availableCapacityKwh", "energyToAvailableRatio",
    "socHeadroom", "temperatureSpread", "cellVoltageSpread",
)
BATTERY_COLUMNS = {
    "soc": "soc", "packVoltage": "pack_voltage",
    "chargeCurrent": "charge_current_clean",
    "maxTemperature": "max_temperature_clean",
    "minTemperature": "min_temperature_clean",
    "availableEnergy": "available_energy_clean",
    "availableCapacity": "available_capacity_clean",
    "maxCellVoltage": "max_cell_voltage",
    "minCellVoltage": "min_cell_voltage",
}


def _number(value):
    """空值或非有限数值统一为 NaN，避免把缺测误当作零。"""
    try:
        number = float(value)
        return number if math.isfinite(number) else np.nan
    except (TypeError, ValueError):
        return np.nan


def battery_from_row(row):
    """将 DWD 电池列转成与预测接口相同的字段名。"""
    return {name: _number(row.get(column)) for name, column in BATTERY_COLUMNS.items()}


def build_features(order):
    """用历史实际电量与电池状态构造功率、理论时长和状态余量。"""
    kwh = _number(order.get("kwh"))
    values = [_number(order.get(name)) for name in FEATURE_NAMES[:5]]
    battery = [_number(order.get(name)) for name in BATTERY_FIELDS]
    state = dict(zip(BATTERY_FIELDS, battery))
    voltage, current = state["packVoltage"], state["chargeCurrent"]
    # 电池采样电流可能为负；仅取绝对值来计算瞬时电功率 kW。
    power = voltage * abs(current) / 1000 if voltage > 0 and abs(current) > 0 else np.nan
    # 理论时长是假设该采样功率恒定的下限代理量，并非实际充电时长。
    ideal_hours = kwh / power if power > 0 else np.nan
    capacity_kwh = voltage * state["availableCapacity"] / 1000 if voltage > 0 and state["availableCapacity"] > 0 else np.nan
    energy_ratio = kwh / state["availableEnergy"] if state["availableEnergy"] > 0 else np.nan
    soc_headroom = 100 - state["soc"] if 0 <= state["soc"] <= 100 else np.nan
    temperature_spread = state["maxTemperature"] - state["minTemperature"]
    cell_voltage_spread = state["maxCellVoltage"] - state["minCellVoltage"]
    return values + battery + [
        power, ideal_hours, capacity_kwh, energy_ratio, soc_headroom,
        temperature_spread, cell_voltage_spread,
    ]
