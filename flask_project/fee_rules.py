"""按分时估算规则估算零费用充电订单，不改写原始费用。"""


TIME_RATES = (
    (0, 6, 1.2),
    (7, 11, 1.5),
    (12, 17, 1.8),
    (18, 23, 2.0),
)


def estimate_zero_fee(kwh, start_hour, recorded_fee):
    if recorded_fee != 0:
        return 0.0
    for first, last, rate in TIME_RATES:
        if first <= start_hour <= last:
            return kwh * rate
    raise ValueError(f"开始时段超出费率范围：{start_hour}")
