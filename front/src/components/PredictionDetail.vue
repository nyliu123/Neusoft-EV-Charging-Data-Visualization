<script setup>
import { computed } from 'vue'

// 负荷模型和时长模型是两套独立口径：数据窗口、特征和验证方式都不同，指标不能混在一排。
// 页面按模型严格分成左右两栏，左栏只讲负荷模型，右栏只讲时长模型，各自带指标、数据和方法说明。
const props = defineProps({ data: { type: Object, required: true } })
const fmt = (value, digits = 0) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })

const loadMetrics = computed(() => {
  const model = props.data.loadPrediction
  return [
    { label: '训练天数', value: `${fmt(model.trainingDays)} 天`, note: '含无订单日，按自然日补齐' },
    { label: '特征维度', value: `${model.featureCount} 维`, note: '趋势、周滞后、站点规模与星期项' },
    { label: '样本外 RMSE', value: `${model.rmse} kWh`, note: '滚动回测，误差带用的就是这个值' },
    { label: '样本内 RMSE', value: `${model.inSampleRmse} kWh`, note: '同批数据既拟合又打分，偏乐观' },
    { label: '回测窗口', value: `最近 ${model.backtestSpan} 天`, note: '逐日滚动，每轮预测之后 7 天' },
    { label: '岭回归系数', value: `${model.penalty}`, note: '只惩罚非截距项' },
  ]
})

const durationMetrics = computed(() => {
  const model = props.data.durationModel
  return [
    { label: '建模样本', value: `${fmt(model.sampleCount)} 单`, note: '有充电时长的订单，按创建时间排序' },
    { label: '独立测试样本', value: `${fmt(model.testCount)} 单`, note: '最后 20% 时间样本' },
    { label: '测试集 MAE', value: `${model.mae} 小时`, note: '点预测的平均绝对误差' },
    { label: '测试集 R²', value: `${model.r2}`, note: '点预测解释的时长波动比例' },
    { label: '范围半宽', value: `±${model.p80HalfWidth} 小时`, note: '校准集 80% 分位的绝对误差' },
    { label: '测试覆盖率', value: `${model.intervalCoverage}%`, note: '独立测试落在参考范围内的比例' },
  ]
})

// 训练段样本数后端没有单独给出，由总样本减去校准段和测试段得到。
const durationSplit = computed(() => {
  const model = props.data.durationModel
  return [
    { stage: '有效时长样本', count: fmt(model.sampleCount), use: '进入建模的全部订单' },
    { stage: '训练段 · 前 60%', count: fmt(model.sampleCount - model.calibrationCount - model.testCount), use: '拟合点预测模型' },
    { stage: '校准段 · 接续 20%', count: fmt(model.calibrationCount), use: `定出 ±${model.p80HalfWidth} 小时的范围半宽` },
    { stage: '独立测试段 · 最后 20%', count: fmt(model.testCount), use: '检验 R²、MAE 与范围覆盖率' },
    { stage: '含电池状态字段', count: fmt(model.batterySampleCount), use: '可关联电池采样的订单' },
    { stage: '含电池字段的测试段', count: fmt(model.batteryTestCount), use: `子集对照：测试 R² ${model.batteryTestR2}` },
    { stage: '未关联电池字段', count: fmt(model.sampleCount - model.batterySampleCount), use: '训练与测试都按缺失处理' },
  ]
})
</script>

<template>
  <div class="prediction-page">
    <div class="prediction-split">
      <section class="prediction-column prediction-column--load">
        <header class="prediction-column-head">
          <div>
            <h2>充电负荷预测模型</h2>
            <p>岭回归 · 输出未来 7 个自然日的日充电量</p>
          </div>
          <span>kWh / 日</span>
        </header>
        <div class="detail-summary prediction-metrics">
          <article v-for="item in loadMetrics" :key="item.label"><span>{{ item.label }}</span><b>{{ item.value }}</b><small>{{ item.note }}</small></article>
        </div>
        <section class="detail-panel prediction-data">
          <header><h2>未来 7 日负荷估算</h2><span>滚动回测口径</span></header>
          <table>
            <thead><tr><th>日期</th><th>星期</th><th>预测 kWh</th><th>误差下界</th><th>误差上界</th></tr></thead>
            <tbody><tr v-for="item in data.loadPrediction.forecast" :key="item.date"><td>{{ item.date }}</td><td>{{ item.weekday }}</td><td>{{ item.value }}</td><td>{{ item.lower }}</td><td>{{ item.upper }}</td></tr></tbody>
          </table>
          <p class="method-note">上下界按样本外 RMSE 对称展开，只覆盖已观测到的趋势与周内模式。</p>
        </section>
        <section class="detail-panel prediction-method">
          <header><h2>负荷模型的评估口径</h2><span>滚动回测</span></header>
          <p class="method-note">{{ data.loadPrediction.method }}</p>
          <div class="prediction-method-grid">
            <div><b>01 · 特征</b><p>按自然日补齐连续序列，用趋势、周滞后（前 7 / 14 天）、近 7 天活跃站点数，以及星期哑变量和「趋势 × 星期」交互，共 {{ data.loadPrediction.featureCount }} 维。</p></div>
            <div><b>02 · 拟合</b><p>岭回归闭式解，除截距外对角加 {{ data.loadPrediction.penalty }} 的正则惩罚，压住共线趋势项的系数。</p></div>
            <div><b>03 · 回测</b><p>最近 {{ data.loadPrediction.backtestSpan }} 天逐日滚动：只用截止日前的数据拟合，再预测之后 7 天，误差带取自这批样本外误差。</p></div>
          </div>
          <p class="prediction-limitation">未来 7 天的趋势和站点规模都落在训练区间之外，树模型只能停在最后一个叶子的取值上，所以这里用可以外推的岭回归。样本内 RMSE 低于样本外，是同一批数据既拟合又打分的缘故，页面一律以样本外口径为准。</p>
        </section>
      </section>

      <section class="prediction-column prediction-column--duration">
        <header class="prediction-column-head">
          <div>
            <h2>充电时长预测模型</h2>
            <p>XGBoost 点预测加误差范围 · 按时间留出 20% 测试集</p>
          </div>
          <span>小时 / 单</span>
        </header>
        <div class="detail-summary prediction-metrics">
          <article v-for="item in durationMetrics" :key="item.label"><span>{{ item.label }}</span><b>{{ item.value }}</b><small>{{ item.note }}</small></article>
        </div>
        <section class="detail-panel prediction-data">
          <header><h2>时间留出与电池子集</h2><span>按订单创建时间排序</span></header>
          <table>
            <thead><tr><th>划分 / 子集</th><th>样本数</th><th>用途与口径</th></tr></thead>
            <tbody><tr v-for="item in durationSplit" :key="item.stage"><td>{{ item.stage }}</td><td>{{ item.count }}</td><td>{{ item.use }}</td></tr></tbody>
          </table>
          <p class="method-note">电池字段只在部分订单上可关联，子集与全量的测试样本不同，两个 R² 不能直接比较。</p>
        </section>
        <section class="detail-panel prediction-method">
          <header><h2>时长模型的评估口径</h2><span>时间顺序验证</span></header>
          <p class="method-note">{{ data.durationModel.method }}</p>
          <div class="prediction-method-grid">
            <div><b>01 · 训练</b><p>前 60% 时间样本训练正则化 XGBoost。共 {{ data.durationModel.featureCount }} 维，含历史实际充电量，以及电池状态和派生量。</p></div>
            <div><b>02 · 校准</b><p>接续 20% 样本校准误差范围；前 80% 样本训练最终点预测模型。</p></div>
            <div><b>03 · 测试</b><p>最后 20% 样本独立检验 R²、MAE 与范围覆盖率。范围不保证单次充电结果。</p></div>
          </div>
          <p class="prediction-limitation">匹配记录的 record_time 全等于订单创建时间去秒，不能独立证明真实采样时点。历史 kwhTotal 是本次实际电量，充电前不能直接使用；去掉它及相关派生量后，离线时间测试 R² 仅 0.199。可用能量的说明标为 kW，量纲亦待核实。当前结果仅是探索性对照。</p>
          <router-link :to="{ path: '/', hash: '#bottom' }" class="detail-cta">返回大屏填写时长预测场景 →</router-link>
        </section>
      </section>
    </div>
  </div>
</template>
