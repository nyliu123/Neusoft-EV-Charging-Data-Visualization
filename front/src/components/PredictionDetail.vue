<script setup>
// 预测评估、日负荷明细和方法说明各自成块，六项评估指标占满同一行。
defineProps({ data: { type: Object, required: true } })
const fmt = value => Number(value || 0).toLocaleString('zh-CN')
</script>

<template>
  <div class="prediction-page">
    <div class="prediction-summary detail-summary">
      <article><span>时长模型样本</span><b>{{ fmt(data.durationModel.sampleCount) }}</b></article>
      <article><span>时间留出测试样本</span><b>{{ fmt(data.durationModel.testCount) }}</b></article>
      <article><span>测试集 MAE</span><b>{{ data.durationModel.mae }} 小时</b></article>
      <article><span>测试集 R²</span><b>{{ data.durationModel.r2 }}</b></article>
      <article><span>范围半宽</span><b>±{{ data.durationModel.p80HalfWidth }} 小时</b></article>
      <article><span>独立测试范围覆盖率</span><b>{{ data.durationModel.intervalCoverage }}%</b></article>
    </div>
    <div class="prediction-content">
      <section class="detail-panel prediction-forecast">
        <header><h2>未来 7 日负荷估算</h2><span>kWh / 日</span></header>
        <p class="method-note">{{ data.loadPrediction.method }} · 样本外 RMSE {{ data.loadPrediction.rmse }} kWh（滚动回测）</p>
        <table><thead><tr><th>日期</th><th>星期</th><th>预测 kWh</th><th>误差下界</th><th>误差上界</th></tr></thead><tbody><tr v-for="item in data.loadPrediction.forecast" :key="item.date"><td>{{ item.date }}</td><td>{{ item.weekday }}</td><td>{{ item.value }}</td><td>{{ item.lower }}</td><td>{{ item.upper }}</td></tr></tbody></table>
      </section>
      <section class="detail-panel prediction-method">
        <header><h2>时长模型的评估口径</h2><span>时间顺序验证</span></header>
        <div class="prediction-method-grid">
          <div><b>01 · 训练</b><p>前 60% 时间样本训练正则化 XGBoost。共 {{ data.durationModel.featureCount }} 维，含历史实际充电量，以及电池状态和派生量。</p></div>
          <div><b>02 · 校准</b><p>接续 20% 样本校准误差范围；前 80% 样本训练最终点预测模型。</p></div>
          <div><b>03 · 测试</b><p>最后 20% 样本独立检验 R²、MAE 与范围覆盖率。范围不保证单次充电结果。</p></div>
        </div>
        <p class="prediction-limitation">匹配记录的 record_time 全等于订单创建时间去秒，不能独立证明真实采样时点。历史 kwhTotal 是本次实际电量，充电前不能直接使用；去掉它及相关派生量后，离线时间测试 R² 仅 0.199。可用能量的说明标为 kW，量纲亦待核实。当前结果仅是探索性对照。</p>
        <router-link :to="{ path: '/', hash: '#bottom' }" class="detail-cta">返回大屏填写预测场景 →</router-link>
      </section>
    </div>
  </div>
</template>
