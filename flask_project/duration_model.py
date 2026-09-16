"""充电时长模型：订单及可关联电池状态的物理特征工程与时间验证。"""

import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

from duration_features import BATTERY_FIELDS, FEATURE_NAMES, build_features


def _new_model():
    # 数千样本采用浅树、较大的叶节点约束和 L2 正则，防止电池字段稀疏时过拟合。
    return XGBRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.03,
        min_child_weight=20, reg_lambda=20, subsample=0.85,
        colsample_bytree=0.9, objective="reg:squarederror",
        tree_method="hist", n_jobs=4, random_state=42,
    )


def train_duration_model(orders):
    usable = sorted(
        (order for order in orders if order["duration"] is not None),
        key=lambda order: order["created"],
    )
    split = max(1, int(len(usable) * 0.8))
    training, testing = usable[:split], usable[split:]
    # 前 60% 训练、接续 20% 校准绝对误差；最后 20% 只用于独立测试。
    calibration_split = max(1, int(len(usable) * 0.6))
    calibration_model = _new_model()
    calibration_model.fit(
        np.asarray([build_features(order) for order in usable[:calibration_split]]),
        [order["duration"] for order in usable[:calibration_split]],
    )
    calibration = usable[calibration_split:split]
    calibration_predicted = calibration_model.predict(np.asarray([build_features(order) for order in calibration]))
    calibration_errors = [
        abs(order["duration"] - estimate)
        for order, estimate in zip(calibration, calibration_predicted)
    ]
    half_width = float(np.quantile(calibration_errors, 0.8, method="higher"))

    # 点预测仍使用前 80% 全部样本训练，保持独立测试口径与页面原有指标一致。
    model = _new_model()
    model.fit(np.asarray([build_features(order) for order in training]), [order["duration"] for order in training])
    actual = [order["duration"] for order in testing]
    predicted = model.predict(np.asarray([build_features(order) for order in testing]))
    battery_testing = [index for index, order in enumerate(testing) if any(order.get(name) is not None for name in BATTERY_FIELDS)]
    metrics = {
        "mae": round(float(mean_absolute_error(actual, predicted)), 2),
        "r2": round(float(r2_score(actual, predicted)), 3),
        "sampleCount": len(usable),
        "testCount": len(testing),
        "method": "数值拼接电池字段的探索性 XGBoost；设备与会话映射尚待确认，按时间留出 20% 测试集",
        "featureCount": len(FEATURE_NAMES),
        "batterySampleCount": sum(any(order.get(name) is not None for name in BATTERY_FIELDS) for order in usable),
        "batteryTestCount": len(battery_testing),
        "batteryTestR2": round(float(r2_score(np.asarray(actual)[battery_testing], predicted[battery_testing])), 3) if len(battery_testing) >= 2 else None,
        "p80HalfWidth": round(half_width, 2),
        "intervalCoverage": round(float(np.mean(np.abs(np.asarray(actual) - predicted) <= half_width) * 100), 1),
        "calibrationCount": len(calibration),
    }
    return model, metrics


def predict_duration(model, kwh, start_hour, facility_type, manager_vehicle, weekday, battery=None):
    # 同一特征构造函数同时服务历史样本和实时预测，避免训练与推断口径漂移。
    order = dict(kwh=kwh, startHour=start_hour, facilityType=facility_type,
                 managerVehicle=manager_vehicle, weekday=weekday)
    order.update(battery or {})
    features = np.asarray([build_features(order)])
    predicted = float(model.predict(features)[0])
    return min(max(predicted, 0.08), 24.0)
