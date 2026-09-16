<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ChartCard from '../components/ChartCard.vue'
import HeatmapLegend from '../components/HeatmapLegend.vue'
import BusinessInsights from '../components/BusinessInsights.vue'
import StatCard from '../components/StatCard.vue'
import DurationPredictor from '../components/DurationPredictor.vue'
import { coloredLegend } from '../chart-legend.js'
import { chartTooltip } from '../chart-tooltip.js'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const loading = ref(true)
const errorMessage = ref('')
const dashboard = ref(null)
const now = ref(new Date())
const heatmapFocus = ref(null)
let clockTimer

const platformColors = { Android: '#65d9a5', IOS: '#b5a0ff', Web: '#5ac8e9' }
const orderColor = '#8b7cf5'
const energyColor = '#fbbf5c'
const historyColor = '#d35b62'
const socColors = ['#35bee9', '#39d9bd', '#a8e0a8', '#fbbf5c', '#f48a6d']
const heatColors = ['#123d78', '#1c63a1', '#258dbb', '#55bfd1', '#e6d9ac', '#eeb985', '#e98b64', '#cf554d', '#89283f']
const axisStyle = {
  axisLine: { lineStyle: { color: '#53708e' } },
  axisTick: { show: false },
  axisLabel: { color: '#b9cee4', fontSize: 10 },
  nameTextStyle: { color: '#f3f8ff', fontSize: 11, fontWeight: 700 },
  splitLine: { lineStyle: { color: '#28415f' } },
}

const fmt = (value, digits = 0) => Number(value || 0).toLocaleString('zh-CN', {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
})

const loadDashboard = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await fetch(`${API_BASE}/dashboard`)
    const result = await response.json()
    if (!response.ok || result.code !== 200) throw new Error(result.msg || '接口请求失败')
    dashboard.value = result.data
  } catch (error) {
    errorMessage.value = `${error.message}。请确认 Flask 服务已在 5000 端口启动。`
  } finally {
    loading.value = false
  }
}

const commonTooltip = chartTooltip({ trigger: 'axis' })

const platformOption = computed(() => ({
  color: Object.values(platformColors),
  tooltip: chartTooltip({ formatter: '{b}<br/>{c} 位用户 · {d}%' }),
  legend: coloredLegend(Object.entries(platformColors).map(([name, color]) => [name, color]), { bottom: 0, left: 'center', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 10 } }),
  series: [{
    type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'],
    padAngle: 3, itemStyle: { borderRadius: 4 }, label: { show: false },
    data: (dashboard.value?.userBehavior.platformPreference || []).map(item => ({
      ...item, itemStyle: { color: platformColors[item.name] || '#f7c66e' },
    })),
  }],
}))

const facilityOption = computed(() => ({
  color: [orderColor, energyColor],
  tooltip: commonTooltip,
  grid: { left: 40, right: 36, top: 28, bottom: 30 },
  legend: coloredLegend([['订单数', orderColor], ['充电量', energyColor]], { top: 0, left: 'center', itemWidth: 10, itemHeight: 6, textStyle: { fontSize: 10 } }),
  xAxis: { type: 'category', data: (dashboard.value?.facility || []).map(item => item.name.replace('充电桩', '').replace('交直流一体桩', '一体桩')), ...axisStyle },
  yAxis: [
    { type: 'value', name: '订单数（单）', ...axisStyle, nameTextStyle: { color: orderColor, fontWeight: 700 } },
    { type: 'value', name: '充电量（kWh）', ...axisStyle, nameTextStyle: { color: energyColor, fontWeight: 700 } },
  ],
  series: [
    { name: '订单数', type: 'bar', barWidth: 18, itemStyle: { borderRadius: [5, 5, 0, 0] }, data: (dashboard.value?.facility || []).map(item => item.orders) },
    { name: '充电量', type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 6, data: (dashboard.value?.facility || []).map(item => item.kwh) },
  ],
}))

const districtOption = computed(() => ({
  color: [energyColor],
  tooltip: commonTooltip,
  grid: { left: 58, right: 68, top: 18, bottom: 26 },
  xAxis: { type: 'value', name: '累计充电量（kWh）', nameLocation: 'middle', nameGap: 22, ...axisStyle, nameTextStyle: { color: energyColor, fontWeight: 700 } },
  yAxis: { type: 'category', inverse: true, data: (dashboard.value?.districts || []).slice(0, 3).map(item => item.name), ...axisStyle },
  series: [
    { name: '充电量（kWh）', type: 'bar', barWidth: 20, itemStyle: { borderRadius: 8 }, label: { show: true, position: 'right', color: '#ffe0a5', fontSize: 10, formatter: '{c} kWh' }, data: (dashboard.value?.districts || []).slice(0, 3).map(item => item.kwh) },
  ],
}))

const monthlyOption = computed(() => ({
  color: [energyColor, orderColor],
  tooltip: commonTooltip,
  grid: { left: 46, right: 42, top: 32, bottom: 28 },
  legend: coloredLegend([['充电量', energyColor], ['订单数', orderColor]], { top: 0, left: 'center', itemWidth: 12, itemHeight: 7 }),
  xAxis: { type: 'category', data: (dashboard.value?.monthly || []).map(item => item.month.slice(2)), ...axisStyle },
  yAxis: [
    { type: 'value', name: '充电量（kWh）', ...axisStyle, nameTextStyle: { color: energyColor, fontWeight: 700 } },
    { type: 'value', name: '订单数（单）', nameTextStyle: { color: orderColor, fontWeight: 700 }, splitLine: { show: false }, axisLabel: { color: '#b9cee4', fontSize: 10 } },
  ],
  series: [
    { name: '充电量', type: 'bar', barMaxWidth: 23, itemStyle: { borderRadius: [4, 4, 0, 0] }, data: (dashboard.value?.monthly || []).map(item => item.kwh) },
    { name: '订单数', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, areaStyle: { opacity: 0.08 }, data: (dashboard.value?.monthly || []).map(item => item.orders) },
  ],
}))

const hourlyOption = computed(() => ({
  color: [orderColor, energyColor],
  tooltip: commonTooltip,
  grid: { left: 46, right: 44, top: 32, bottom: 30 },
  legend: coloredLegend([['订单数', orderColor], ['充电量', energyColor]], { top: 0, left: 'center', itemWidth: 12, itemHeight: 7 }),
  xAxis: { type: 'category', data: (dashboard.value?.hourly || []).map(item => item.hour.slice(0, 2)), ...axisStyle },
  yAxis: [{ type: 'value', name: '订单数（单）', ...axisStyle, nameTextStyle: { color: orderColor, fontWeight: 700 } }, { type: 'value', name: '充电量（kWh）', nameTextStyle: { color: energyColor, fontWeight: 700 }, splitLine: { show: false }, axisLabel: { color: '#b9cee4', fontSize: 10 } }],
  series: [
    { name: '订单数', type: 'bar', barMaxWidth: 15, itemStyle: { borderRadius: [3, 3, 0, 0] }, data: (dashboard.value?.hourly || []).map(item => item.orders) },
    { name: '充电量', type: 'line', yAxisIndex: 1, smooth: true, showSymbol: false, lineStyle: { width: 2.5 }, data: (dashboard.value?.hourly || []).map(item => item.kwh) },
  ],
}))

const forecastOption = computed(() => {
  const predictionData = dashboard.value?.loadPrediction
  if (!predictionData) return {}
  const history = predictionData.history
  const forecast = predictionData.forecast
  const labels = [...history.map(item => item.date.slice(5)), ...forecast.map(item => item.date.slice(5))]
  const historyValues = [...history.map(item => item.value), ...Array(forecast.length).fill(null)]
  const predictedValues = [...Array(history.length - 1).fill(null), history.at(-1).value, ...forecast.map(item => item.value)]
  return {
    color: [historyColor, energyColor], tooltip: commonTooltip,
    grid: { left: 48, right: 18, top: 30, bottom: 30 },
    legend: coloredLegend([['历史负荷', historyColor], ['预测负荷', energyColor]], { top: 0, left: 'center', itemWidth: 12, itemHeight: 7 }),
    xAxis: { type: 'category', data: labels, ...axisStyle, axisLabel: { interval: 5, color: '#b9cee4', fontSize: 10 } },
    yAxis: { type: 'value', name: '负荷（kWh）', ...axisStyle, nameTextStyle: { color: historyColor, fontWeight: 700 } },
    series: [
      { name: '历史负荷', type: 'line', showSymbol: false, smooth: true, data: historyValues, lineStyle: { width: 2 } },
      { name: '预测负荷', type: 'line', showSymbol: true, symbolSize: 5, smooth: true, data: predictedValues, lineStyle: { width: 3, type: 'dashed' }, areaStyle: { opacity: 0.08 }, markArea: { silent: true, itemStyle: { color: 'rgba(245,158,11,.05)' }, data: [[{ xAxis: forecast[0].date.slice(5) }, { xAxis: forecast.at(-1).date.slice(5) }]] } },
    ],
  }
})

const batteryOption = computed(() => ({
  color: socColors,
  tooltip: chartTooltip({ formatter: '{b}<br/>{c} 条 · {d}%' }),
  series: [{
    type: 'pie', radius: ['48%', '72%'], center: ['50%', '48%'],
    itemStyle: { borderColor: '#112641', borderWidth: 3, borderRadius: 4 },
    label: { color: '#d0def0', fontSize: 10, formatter: '{b}\n{d}%' },
    data: (dashboard.value?.battery.socDistribution || []).map((item, index) => ({ ...item, label: { color: socColors[index] } })),
  }],
}))

const heatmapMax = computed(() => Math.max(1, ...(dashboard.value?.heatmap || []).map(item => item[2])))
const heatmapOption = computed(() => ({
  tooltip: chartTooltip({
    trigger: 'item',
    showDelay: 0,
    hideDelay: 0,
    transitionDuration: 0,
    position: 'top',
    padding: 0,
    borderWidth: 0,
    backgroundColor: 'transparent',
    extraCssText: 'box-shadow:none;',
    formatter: item => {
      const count = item.value[2]

      if (heatmapFocus.value !== null && count < heatmapFocus.value) {
        return ''
      }

      const weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][item.value[1]]
      const hour = String(item.value[0]).padStart(2, '0')

      return `
        <div style="
          position:relative;
          padding:8px 12px;
          background:rgba(9,25,47,.96);
          border:1px solid rgba(91,143,192,.65);
          border-radius:6px;
          color:#eaf4ff;
          box-shadow:0 6px 18px rgba(0,0,0,.28);
          white-space:nowrap;
        ">
          ${weekday} ${hour}:00<br/>
          <b>${count} 单</b>

          <span style="
            position:absolute;
            left:50%;
            bottom:-7px;
            width:0;
            height:0;
            transform:translateX(-50%);
            border-left:7px solid transparent;
            border-right:7px solid transparent;
            border-top:7px solid rgba(91,143,192,.65);
          "></span>

          <span style="
            position:absolute;
            left:50%;
            bottom:-6px;
            width:0;
            height:0;
            transform:translateX(-50%);
            border-left:6px solid transparent;
            border-right:6px solid transparent;
            border-top:6px solid rgba(9,25,47,.96);
          "></span>
        </div>
      `
    },
  }),
  grid: {
    left: 48,
    right: 16,
    top: 12,
    bottom: 50,
  },
  xAxis: {
    type: 'category',
    data: Array.from({ length: 24 }, (_, index) => `${index}时`),
    splitArea: { show: false },
    axisLabel: {
      color: '#b9cee4',
      fontSize: 9,
    },
  },
  yAxis: {
    type: 'category',
    data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    splitArea: { show: false },
    axisLabel: {
      color: '#b9cee4',
      fontSize: 10,
    },
  },
  visualMap: {
    type: 'continuous',
    show: false,
    dimension: 2,
    seriesIndex: 0,
    min: 0,
    max: heatmapMax.value,
    calculable: false,
    range: heatmapFocus.value === null
      ? [0, heatmapMax.value]
      : [heatmapFocus.value, heatmapMax.value],
    inRange: {
      color: heatColors,
    },
    outOfRange: {
      color: '#102b43',
    },
  },
  series: [{
    type: 'heatmap',
    data: (dashboard.value?.heatmap || []).map(([weekday, hour, count]) => {
      const inactive = heatmapFocus.value !== null && count < heatmapFocus.value

      return {
        value: [hour, weekday, count],
        tooltip: inactive
          ? {
              show: true,
              formatter: () => '',
              padding: 0,
              borderWidth: 0,
              backgroundColor: 'transparent',
              extraCssText: 'box-shadow:none;',
            }
          : undefined,
        emphasis: inactive
          ? {
              disabled: true,
            }
          : undefined,
      }
    }),
    itemStyle: {
      borderColor: '#10223a',
      borderWidth: 1,
    },
    emphasis: {
      itemStyle: {
        shadowBlur: 8,
        shadowColor: 'rgba(15,60,138,.25)',
      },
    },
  }],
}))

onMounted(async () => {
  clockTimer = window.setInterval(() => { now.value = new Date() }, 1000)
  await loadDashboard()
})

onBeforeUnmount(() => window.clearInterval(clockTimer))
</script>

<template>
  <main class="dashboard-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">⚡</span>
        <div><h1>东软汽车充电桩数据分析可视化大屏</h1><p>NEUSOFT EV CHARGING DATA VISUALIZATION</p></div>
      </div>
      <div class="meta-strip">
        <span class="live-dot"></span>
        <span>数据周期：{{ dashboard?.meta.dateRange || '加载中' }}</span>
        <i></i>
        <span>{{ now.toLocaleDateString('zh-CN') }} {{ now.toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
      </div>
    </header>

    <div v-if="loading" class="state-screen"><span class="loader"></span><p>正在校验原始数据并生成分析结果…</p></div>
    <div v-else-if="errorMessage && !dashboard" class="state-screen error-state"><b>数据服务暂不可用</b><p>{{ errorMessage }}</p><button @click="loadDashboard">重新连接</button></div>

    <template v-else-if="dashboard">
      <section class="stats-grid">
        <StatCard label="综合费用" :value="fmt(dashboard.revenue.combinedAmount, 2)" unit="元" icon="¥" tone="amber" />
        <StatCard label="有效充电订单" :value="fmt(dashboard.kpis.orders)" unit="单" icon="▣" />
        <StatCard label="累计充电量" :value="fmt(dashboard.kpis.totalKwh, 2)" unit="kWh" icon="ϟ" tone="green" />
        <StatCard label="平均单次电量" :value="fmt(dashboard.kpis.avgKwh, 2)" unit="kWh" icon="◈" tone="amber" />
        <StatCard label="服务用户" :value="fmt(dashboard.kpis.users)" unit="人" icon="♙" tone="purple" />
        <StatCard label="充电站 / 设备" :value="`${dashboard.kpis.stations} / ${dashboard.kpis.devices}`" unit="个" icon="▤" tone="cyan" />
        <StatCard label="平均充电时长" :value="fmt(dashboard.kpis.avgDuration, 2)" unit="h" icon="◷" tone="rose" />
      </section>

      <section class="mosaic-section demand-section">
        <div class="mosaic-heading"><h2>充电需求的时空分布</h2><router-link to="/details/operations">运营详情 →</router-link></div>
        <div class="demand-mosaic">
          <ChartCard class="monthly-tile" title="月度订单与充电量" :option="monthlyOption" height="260px" />
          <ChartCard class="hourly-tile" title="24 小时订单与充电量" :option="hourlyOption" height="260px" />
          <ChartCard class="district-tile" title="区域充电量 TOP 3" :option="districtOption" height="260px" />
          <ChartCard class="heatmap-tile" title="星期 × 小时订单热力图" :option="heatmapOption" height="420px">
            <HeatmapLegend :max="heatmapMax" :colors="heatColors" @focus="heatmapFocus = $event" />
          </ChartCard>
          <section class="panel station-panel station-tile">
            <header class="panel-header"><div><h2>高负荷充电站 TOP 10</h2></div></header>
            <div class="ranking-list">
              <div v-for="(station, index) in dashboard.topStations" :key="station.name" class="ranking-item">
                <span class="rank" :class="{ top: index < 3 }">{{ index + 1 }}</span>
                <div class="station-info"><div class="station-name-wrap"><b tabindex="0">{{ station.name }}</b><span class="station-name-tooltip">{{ station.name }}</span></div><small>{{ station.district }} · {{ station.orders }} 单</small></div>
                <strong>{{ fmt(station.kwh) }}<small> kWh</small></strong>
              </div>
            </div>
          </section>
        </div>
      </section>

      <BusinessInsights :data="dashboard" :platform-option="platformOption" />

      <section class="mosaic-section equipment-section">
        <div class="mosaic-heading"><h2>设备运营与负荷预测</h2><router-link to="/details/prediction">预测详情 →</router-link></div>
        <div class="equipment-mosaic">
          <ChartCard class="facility-tile" title="充电桩类型运营" :option="facilityOption" height="230px" />
          <ChartCard class="battery-tile" title="电池 SOC 分布" :option="batteryOption" height="230px" />
          <ChartCard class="forecast-tile" title="未来 7 日充电负荷预测" :option="forecastOption" height="230px" />
          <DurationPredictor />
          <section class="mosaic-section quality-section quality-tile">
            <div class="mosaic-heading"><h2>数据质量</h2><router-link to="/details/quality">口径详情 →</router-link></div>
            <!-- 跨订单、费用、站点和电池的十二项质量摘要由同一 ADS 质量表驱动。 -->
            <div class="quality-strip">
              <div v-for="item in dashboard.quality.summaryCards" :key="item.key">
                <span>{{ item.label }}</span>
                <b>{{ fmt(item.value, item.unit === '%' ? 1 : 0) }}<small>{{ item.unit }}</small></b>
                <em v-if="item.rate !== null">占比 {{ item.rate }}%</em>
              </div>
            </div>
          </section>
        </div>
      </section>

      <footer>数据来源：原始充电记录　｜　预测仅供运营参考</footer>
    </template>
  </main>
</template>
