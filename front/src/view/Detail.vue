<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import PredictionDetail from '../components/PredictionDetail.vue'
import QualityDetail from '../components/QualityDetail.vue'

const route = useRoute()
const data = ref(null)
const error = ref('')
const sections = [
  { key: 'operations', label: '运营分析' },
  { key: 'stations', label: '站点详情' },
  { key: 'users', label: '用户行为' },
  { key: 'revenue', label: '收费分析' },
  { key: 'prediction', label: '预测分析' },
  { key: 'quality', label: '数据质量' },
]
const active = computed(() => sections.find(item => item.key === route.params.section) || sections[0])
const fmt = (value, digits = 0) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })

onMounted(async () => {
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE || '/api'}/dashboard`)
    const result = await response.json()
    if (!response.ok) throw new Error(result.msg)
    data.value = result.data
  } catch (cause) {
    error.value = cause.message
  }
})
</script>

<template>
  <main class="detail-shell" :class="{ 'detail-shell--dense': active.key === 'quality' || active.key === 'prediction', 'detail-shell--prediction': active.key === 'prediction' }">
    <header class="detail-header">
      <div><router-link to="/" class="back-link">← 返回大屏</router-link><h1>{{ active.label }}</h1><p>东软汽车充电桩数据分析可视化大屏的指标详情</p></div>
      <nav><router-link v-for="section in sections" :key="section.key" :to="`/details/${section.key}`" :class="{ active: active.key === section.key }">{{ section.label }}</router-link></nav>
    </header>
    <div v-if="error" class="detail-error">数据加载失败：{{ error }}</div>
    <div v-else-if="!data" class="detail-loading">正在加载详情数据…</div>

    <template v-else-if="active.key === 'operations'">
      <div class="detail-summary">
        <article><span>有效订单</span><b>{{ fmt(data.kpis.orders) }}</b></article>
        <article><span>累计充电量</span><b>{{ fmt(data.kpis.totalKwh, 2) }} kWh</b></article>
        <article><span>服务用户</span><b>{{ data.kpis.users }}</b></article>
        <article><span>平均时长</span><b>{{ data.kpis.avgDuration }} 小时</b></article>
      </div>
      <div class="detail-columns">
        <section class="detail-panel"><h2>月度趋势明细</h2><div class="table-scroll"><table><thead><tr><th>月份</th><th>订单数</th><th>充电量 kWh</th></tr></thead><tbody><tr v-for="item in data.monthly" :key="item.month"><td>{{ item.month }}</td><td>{{ fmt(item.orders) }}</td><td>{{ fmt(item.kwh, 2) }}</td></tr></tbody></table></div></section>
        <section class="detail-panel"><h2>充电桩类型明细</h2><table><thead><tr><th>桩型</th><th>订单</th><th>电量 kWh</th><th>平均时长</th></tr></thead><tbody><tr v-for="item in data.facility" :key="item.name"><td>{{ item.name }}</td><td>{{ fmt(item.orders) }}</td><td>{{ fmt(item.kwh, 2) }}</td><td>{{ item.avgDuration }} 小时</td></tr></tbody></table><h2 class="detail-subhead">订单来源平台（非用户偏好）</h2><table><thead><tr><th>平台</th><th>订单数</th><th>订单占比</th></tr></thead><tbody><tr v-for="item in data.platform" :key="item.name"><td>{{ item.name }}</td><td>{{ item.value }}</td><td>{{ (item.value / data.kpis.orders * 100).toFixed(1) }}%</td></tr></tbody></table></section>
      </div>
      <section class="detail-panel"><h2>24 小时订单与电量明细</h2><div class="hour-grid"><div v-for="item in data.hourly" :key="item.hour"><b>{{ item.hour }}</b><span>{{ item.orders }} 单</span><small>{{ fmt(item.kwh, 1) }} kWh</small></div></div></section>
    </template>

    <template v-else-if="active.key === 'stations'">
      <div class="detail-summary"><article><span>充电站</span><b>{{ data.kpis.stations }}</b></article><article><span>设备</span><b>{{ data.kpis.devices }}</b></article><article><span>覆盖区域</span><b>{{ data.districts.length }}</b></article><article><span>统计订单</span><b>{{ fmt(data.kpis.orders) }}</b></article></div>
      <div class="detail-columns">
        <section class="detail-panel"><h2>区域供需明细</h2><table><thead><tr><th>区域</th><th>充电站</th><th>设备</th><th>订单</th><th>电量 kWh</th></tr></thead><tbody><tr v-for="item in data.districts" :key="item.name"><td>{{ item.name }}</td><td>{{ item.stations }}</td><td>{{ item.devices }}</td><td>{{ item.orders }}</td><td>{{ fmt(item.kwh, 2) }}</td></tr></tbody></table></section>
        <section class="detail-panel"><h2>高负荷站点 TOP 10</h2><table><thead><tr><th>排名</th><th>站点</th><th>区域</th><th>订单</th><th>电量 kWh</th></tr></thead><tbody><tr v-for="(item,index) in data.topStations" :key="item.name"><td>{{ index + 1 }}</td><td>{{ item.name }}</td><td>{{ item.district }}</td><td>{{ item.orders }}</td><td>{{ fmt(item.kwh, 2) }}</td></tr></tbody></table></section>
      </div>
    </template>

    <template v-else-if="active.key === 'prediction'">
      <PredictionDetail :data="data" />
    </template>

    <template v-else>
      <QualityDetail :data="data" />
    </template>
  </main>
</template>
