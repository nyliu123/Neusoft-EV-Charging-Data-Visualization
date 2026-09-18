"""充电负荷预测模型：趋势 × 星期 + 周滞后 + 站点规模的岭回归。

和时长模型分开成独立模块：本模型是线性岭回归配滚动回测，
时长模型是 XGBoost 配时间留出验证，两者数据窗口、特征和评估口径都不同。

为什么用岭回归而不是树模型：试过同特征的 XGBoost 与「岭回归 + 残差」混合，
滚动回测 MAE 分别 27.9 / 25.2，都差于本模型 —— 未来 7 天的趋势和站点数落在训练区间之外，
树只能钳在最后一个叶子的取值上，无法外推。
"""

import math
from datetime import timedelta

from load_features import (
    FEATURE_NAMES, WEEKDAY_NAMES, calendar_days, daily_series, feature_row, station_series,
)


PENALTY = 0.15              # 岭回归正则系数，截距不惩罚
HORIZON = 7                 # 输出未来 7 个完整自然日
HISTORY_DAYS = 30           # 返回给前端做拟合对照的历史天数
BACKTEST_SPAN = 120         # 滚动回测覆盖的最近天数
BACKTEST_MIN_TRAIN = 28     # 回测最少训练天数


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


def _ridge_fit(features, targets, penalty=PENALTY):
    """岭回归闭式解：对除截距外的对角线加惩罚项。"""
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


def _backtest_rmse(dates, values, stations, horizon=HORIZON, span=BACKTEST_SPAN):
    """滚动回测的样本外 RMSE：每次只用截止日前的数据拟合，再预测之后 horizon 天。

    误差带要用这个值。样本内 RMSE 是拿同一批数据既拟合又打分，偏乐观，
    会把误差范围画得比实际窄、把置信度说得比实际好。
    """
    errors = []
    for cut in range(max(BACKTEST_MIN_TRAIN, len(dates) - span), len(dates) - horizon + 1):
        train = values[:cut]
        scale = max(cut - 1, 1)
        features = [feature_row(train, stations, index, index / scale, day.weekday())
                    for index, day in enumerate(dates[:cut])]
        coefficients = _ridge_fit(features, train)
        for step, day in enumerate(dates[cut:cut + horizon], start=1):
            index = cut + step - 1
            predicted = max(_dot(feature_row(values, stations, index, index / scale, day.weekday()), coefficients), 0.0)
            errors.append(predicted - values[index])
    if not errors:
        return 0.0
    return math.sqrt(sum(error * error for error in errors) / len(errors))


def build_load_forecast(orders):
    """拟合负荷模型并输出历史拟合、未来 7 日预测与误差带宽。

    dates/values 是按自然日补齐的连续序列（无订单的日子记 0），
    站点规模取「目标日之前 7 天内出现过的站点数」，预测期沿用最后一个已知值，
    因此未来 7 天的特征全部来自已知数据，不需要递归预测。
    """
    daily, stations_by_day = daily_series(orders)
    dates, values = calendar_days(daily)
    scale = max(len(dates) - 1, 1)
    stations = station_series(dates, stations_by_day, extra_days=HORIZON)

    features = [feature_row(values, stations, index, index / scale, day.weekday())
                for index, day in enumerate(dates)]
    coefficients = _ridge_fit(features, values)
    fitted = [_dot(row, coefficients) for row in features]
    in_sample_rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(values, fitted)) / len(values))

    # 误差带用滚动回测的样本外误差，而不是上面这个偏乐观的样本内数字。
    rmse = _backtest_rmse(dates, values, stations)

    forecast = []
    for step in range(1, HORIZON + 1):
        target = dates[-1] + timedelta(days=step)
        index = len(dates) - 1 + step
        predicted = max(_dot(feature_row(values, stations, index, index / scale, target.weekday()), coefficients), 0.0)
        forecast.append({
            "date": target.isoformat(),
            "weekday": WEEKDAY_NAMES[target.weekday()],
            "value": round(predicted, 2),
            "lower": round(max(predicted - rmse, 0.0), 2),
            "upper": round(predicted + rmse, 2),
        })

    # fitted 一并返回，前端把模型在历史日期上的预测和实际值画在一起，直观看出模型贴合程度。
    history = [
        {"date": day.isoformat(), "value": round(value, 2), "fitted": round(fit, 2)}
        for day, value, fit in zip(dates[-HISTORY_DAYS:], values[-HISTORY_DAYS:], fitted[-HISTORY_DAYS:])
    ]

    return {
        "history": history,
        "forecast": forecast,
        "rmse": round(rmse, 2),
        "inSampleRmse": round(in_sample_rmse, 2),
        "method": "趋势 × 星期 + 周滞后 + 站点规模岭回归",
        "featureCount": len(FEATURE_NAMES),
        "trainingDays": len(dates),
        "penalty": PENALTY,
        "backtestSpan": BACKTEST_SPAN,
    }
