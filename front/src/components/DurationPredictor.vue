<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const predicting = ref(false)
const prediction = ref(null)
const errorMessage = ref('')
const form = reactive({
  kwh: 10, startHour: 18, facilityType: 3, managerVehicle: 0, weekday: 2,
  soc: '', packVoltage: '', chargeCurrent: '', maxTemperature: '',
  minTemperature: '', availableEnergy: '', availableCapacity: '',
  maxCellVoltage: '', minCellVoltage: '',
})

// 电流正负由记录约定决定；界面显示的功率仅是该时刻的电压×电流。
const samplePower = computed(() => {
  const voltage = Number(form.packVoltage)
  const current = Number(form.chargeCurrent)
  return form.packVoltage !== '' && form.chargeCurrent !== '' && voltage > 0 && current !== 0
    ? (voltage * Math.abs(current) / 1000).toFixed(2) : null
})

const predictDuration = async () => {
  predicting.value = true
  errorMessage.value = ''
  try {
    // 空白电池字段不发送，服务端按真实缺失值经过 XGBoost 缺失分支。
    const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ''))
    const response = await fetch(`${API_BASE}/predict/duration`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    if (!response.ok || result.code !== 200) throw new Error(result.msg || '预测失败')
    prediction.value = result.data
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    predicting.value = false
  }
}

onMounted(predictDuration)
</script>

<template>
  <section class="panel model-panel model-tile duration-predictor">
    <header class="panel-header"><div><h2>充电时长范围估算</h2></div></header>
    <form class="predict-form" @submit.prevent="predictDuration">
      <label>预计电量 <input v-model.number="form.kwh" type="number" min="0.1" max="60" step="0.1" required><em>kWh</em></label>
      <label>开始时段 <select v-model.number="form.startHour"><option v-for="hour in 24" :key="hour" :value="hour - 1">{{ String(hour - 1).padStart(2, '0') }}:00</option></select></label>
      <label>充电桩型 <select v-model.number="form.facilityType"><option :value="1">交流桩</option><option :value="2">直流桩</option><option :value="3">交直流一体桩</option><option :value="4">其他</option></select></label>
      <label>车辆类型 <select v-model.number="form.managerVehicle"><option :value="0">普通车辆</option><option :value="1">运营车辆</option></select></label>
      <label>星期 <select v-model.number="form.weekday"><option v-for="(name,index) in ['周一','周二','周三','周四','周五','周六','周日']" :key="name" :value="index">{{ name }}</option></select></label>
      <p class="predict-caveat">历史训练使用实际电量；这里的预计电量仅作情景代理。电池设备与会话的映射尚未核实。</p>
      <div class="battery-heading">电池状态 <small>填写充电开始前已知值；空白按缺失处理</small></div>
      <label>初始 SOC <input v-model.number="form.soc" type="number" min="0" max="100" step="0.1" placeholder="可选"><em>%</em></label>
      <label>电池包电压 <input v-model.number="form.packVoltage" type="number" min="1" max="1000" step="0.1" placeholder="可选"><em>V</em></label>
      <label>采样电流 <input v-model.number="form.chargeCurrent" type="number" min="-1000" max="1000" step="0.1" placeholder="可选"><em>A</em></label>
      <label>可用容量 <input v-model.number="form.availableCapacity" type="number" min="0" max="1000" step="0.1" placeholder="可选"><em>Ah</em></label>
      <label>最高温度 <input v-model.number="form.maxTemperature" type="number" min="-50" max="150" step="0.1" placeholder="可选"><em>°C</em></label>
      <label>最低温度 <input v-model.number="form.minTemperature" type="number" min="-50" max="150" step="0.1" placeholder="可选"><em>°C</em></label>
      <label>可用能量 <input v-model.number="form.availableEnergy" type="number" min="0" max="200" step="0.1" placeholder="可选"><em>原表 kW</em></label>
      <div class="power-readout">采样功率 <b>{{ samplePower === null ? '填写电压和电流后计算' : `${samplePower} kW` }}</b></div>
      <details class="cell-fields"><summary>补充单体电压</summary><div class="cell-inputs">
        <label>最高单体电压 <input v-model.number="form.maxCellVoltage" type="number" min="0" max="10" step="0.01" placeholder="可选"><em>V</em></label>
        <label>最低单体电压 <input v-model.number="form.minCellVoltage" type="number" min="0" max="10" step="0.01" placeholder="可选"><em>V</em></label>
      </div></details>
      <button :disabled="predicting" type="submit">{{ predicting ? '计算中…' : '开始预测' }}</button>
    </form>
    <p v-if="errorMessage" class="predict-error" role="alert">{{ errorMessage }}</p>
    <div v-if="prediction" class="prediction-result">
      <!-- 结果和独立测试指标同时展示，避免只有点预测而忽略模型误差。 -->
      <div class="prediction-main"><span>估算时长</span><strong>{{ prediction.hours }}</strong><em>小时</em></div>
      <div class="prediction-meta"><p>参考范围 {{ prediction.lower }}–{{ prediction.upper }} 小时</p><p>独立测试覆盖 {{ prediction.intervalCoverage }}% · MAE {{ prediction.mae }} 小时</p><p>R² {{ prediction.r2 }}；仅供数据探索</p></div>
    </div>
  </section>
</template>

<style scoped>
.duration-predictor .battery-heading { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 8px; margin-top: 2px; color: #73d9ee; font-weight: 700; font-size: 11px; }
.duration-predictor .predict-caveat { grid-column: 1 / -1; margin: 0; color: #d7c6a7; font-size: 10px; }
.duration-predictor .battery-heading small { color: #abc9dc; font-size: 10px; font-weight: 400; }
.duration-predictor .power-readout { align-self: end; padding: 8px; color: #bed5e6; background: #102e4c; border: 1px solid #3c617f; border-radius: 5px; font-size: 10px; }
.duration-predictor .power-readout b { display: block; color: #75dcf0; font-size: 11px; }
.duration-predictor .cell-fields { grid-column: 1 / -1; color: #b5d6e8; font-size: 10px; }
.duration-predictor .cell-fields summary { cursor: pointer; }
.duration-predictor .cell-inputs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 8px; }
.duration-predictor .predict-error { color: #ffc1a6; font-size: 11px; margin: 6px 0; }
.duration-predictor .predict-form > button { grid-column: 1 / -1; cursor: pointer; }
.duration-predictor .prediction-result { margin-top: 8px; }
@media (max-width: 620px) { .duration-predictor .battery-heading { display: block; } .duration-predictor .battery-heading small { display: block; } }
</style>
