# 东软汽车充电桩数据分析可视化大屏

项目用 `cleanData.py` 读取 `data/` 内三份原始 CSV，经 Spark 清洗后写入 MySQL。大屏 API 从 MySQL 的 DWD 清洗明细与 ADS 质量表读取数据，完成订单、用户、站点、区域、桩型、时段、电池等多维分析，并提供未来 7 日负荷预测与交互式充电时长预测。

首页的“查看详情”按钮通过 Vue Router 跳转到 `/details/operations`、`/details/stations`、`/details/users`、`/details/revenue`、`/details/prediction`、`/details/quality`，各页可返回大屏或切换详情类别。

## 数据口径

- 原始订单 3,395 条；剔除 `kwhTotal <= 0` 后有效订单 3,340 条。
- 原始日期中的 `0014/0015` 按数据语义校正为 `2014/2015`。
- 平均时长和时长预测仅使用 `(0, 24]` 小时范围内的数据。
- 用户平台、时段、桩型偏好以用户标识去重，按样本内最多记录归类；频次分层、复充率和站点忠诚度也只反映观察到的行为。
- 区域 TOP 3 图只比较累计充电量（kWh）；设备数在站点详情单独查看。订单数与充电量叠加时分别使用“单”和“kWh”双轴。
- 费用按元展示；对 3,340 单有效充电订单，378 单保留原始正费用记录 398.85 元，2,962 单原始费用为零，按分时估算规则估算 29,711.50 元；综合费用 30,110.35 元。原始订单另有 1 单电量为零但费用为 2.67 元，单独列为异常，原始费用列合计 401.52 元。估算费用有效用于运营分析，但须与原始记录分开；缺少成本，不能计算利润。
- 分时估算规则：0–6 时 1.2 元/kWh、7–11 时 1.5 元/kWh、12–17 时 1.8 元/kWh、18–23 时 2.0 元/kWh；原始费用非零的订单不重复估算。
- 总计与各月金额均按未舍入的订单费用先求和、再显示两位小数；分月显示值相加可能与总计显示值有 0.02 元的舍入差，不影响原始订单级计算。
- `cleanData.py` 生成 DWD 订单、站点、电池明细和 ADS 分析表；`analytics.py` 只从 MySQL 读取清洗结果，`/api/health` 返回 API 状态。
- 热力图在前端将原始 `[星期, 小时, 订单数]` 映射为 ECharts 所需的 `[小时, 星期, 订单数]`，逐格按真实订单数着色；定位点默认在 0 单，点击渐变条任意位置可直接锚定，订单数 ≥ 定位值的块保持热力色，其余块显示背景色且不弹出独立标签，底层订单不被删除。周三 13:00 为 61 单。
- 高负荷充电站展示 TOP 10；用户和收费树图点击模块放大整图、点击空白恢复。
- 时长模型目前是探索性对照：历史训练用的 `kwhTotal` 按 `data/explanation/nvv2t_explained.csv` 是本次实际电量，不能视为充电前的计划量；`data/explanation/dsv13r2_explained.csv` 把 `esd` 定义为设备标识，而 `sessionId` 是会话 ID，当前数值拼接的 1575 条电池状态没有业务映射证明。1576 条数值重合记录的 `record_time` 均等于订单创建时间去秒，无法独立证明采样先后。21 维正则化 XGBoost 在 3339 条有效时长样本的时间留出测试上 MAE 0.67 小时、R² 0.326；去掉实际电量及其派生量、仍保留探索性电池数值拼接的离线对照 R² 0.199，而只用充电前订单字段的对照 R² 0.186。电池原说明将“可用能量”标为 kW，其量纲不宜直接当成 kWh。获得设备到会话的映射、充电前计划电量或目标 SOC、额定功率后，才可进行可靠的充电前预测验证。
- 数据质量从原始订单、站点、电池记录与清洗后跨表关联分别统计：首页展示 12 项跨域摘要，质量详情展示 33 项指标及各自分母和清洗口径。

## 启动

首先进入项目自带的 `venv` 环境：

```powershell
cd Neusoft-EV-Charging-Data-Visualization
.\.venv\Scripts\activate
```

然后确认本地 MySQL 的 `car_data` 数据库可用，随后再运行清洗与分析：

```powershell
python cleanData.py
```

脚本写入 `dwd_orders`、`dwd_stations`、`dwd_battery`；`ads_analysis.py` 统一生成 `ads_facility`、`ads_monthly`、`ads_hourly`、`ads_station`、`ads_user`、`ads_revenue`、`ads_battery`、`ads_quality`，对应的 CSV 目录使用同名。

先启动后端：

```powershell
cd flask_project
python run.py
```

也可以直接双击 `startback.cmd`。

然后再另开一个终端启动前端：

```powershell
cd front
npm run dev
```

也可以直接双击 `startfront.cmd`。

最后打开浏览器访问 `http://127.0.0.1:5173/`。

## 验证

```powershell
cd flask_project
& '../.venv/Scripts/python.exe' -m py_compile analytics.py duration_model.py fee_rules.py mysql_store.py user_business.py run.py utils/response.py

cd ..
& '.\.venv\Scripts\python.exe' -m py_compile cleanData.py ads_analysis.py

cd front
npm run build
```

接口：`/api/dashboard` 返回完整大屏数据（包括 `userBehavior` 和分项 `revenue`），`/api/predict/duration` 接受 GET 或 POST 参数进行充电时长预测。大屏的“查看详情”按钮使用 Vue Router 进入运营、站点、用户行为、费用、预测或数据质量详情页。
