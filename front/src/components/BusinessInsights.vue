<script setup>
import { computed } from 'vue'
import ChartCard from './ChartCard.vue'
import { coloredLegend } from '../chart-legend.js'
import { chartTooltip } from '../chart-tooltip.js'

const props = defineProps({ data: { type: Object, required: true }, platformOption: { type: Object, required: true } })
const user = computed(() => props.data.userBehavior)
const revenue = computed(() => props.data.revenue)
const money = value => Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const tooltip = chartTooltip()
const axis = { axisLine: { lineStyle: { color: '#53708e' } }, axisTick: { show: false }, axisLabel: { color: '#b9cee4', fontSize: 10 }, nameTextStyle: { color: '#f3f8ff', fontWeight: 700 }, splitLine: { lineStyle: { color: '#28415f' } } }

const frequencyOption = computed(() => ({
  color: ['#40305f', '#685197', '#9873dc', '#c9adff'],
  // 层次图不再用悬停标签，完整信息由点击后的放大卡片承担。
  tooltip: { ...tooltip, show: false, formatter: item => `${item.name}<br/>${item.data?.originalValue ?? item.value} 位用户` },
  series: [{
    type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false },
    // 根节点（depth 0）只做布局容器：不画底色，也不参与悬停高亮等任何交互。
    levels: [{ itemStyle: { color: 'transparent', borderColor: 'transparent' }, emphasis: { disabled: true } }],
    data: user.value.frequencySegments.map((item, index) => ({
      ...item, itemStyle: { color: ['#40305f', '#685197', '#9873dc', '#c9adff'][index] },
    })),
    label: { show: true, formatter: item => item.name, fontSize: 12 },
    itemStyle: { borderColor: '#102b48', borderWidth: 3, gapWidth: 3 },
  }],
}))

const userScatterOption = computed(() => ({
  color: ['#d1b5ff', '#b794ff', '#9873e9', '#e2a3cf'],
  tooltip: {
    ...tooltip, trigger: 'item',
    formatter: item => `用户标识 ${item.data.userId}<br/>${item.data.segment}<br/>${item.data.orders} 单<br/>单次平均 ${item.data.avgKwh} kWh<br/>累计 ${item.data.totalKwh} kWh`,
  },
  legend: coloredLegend([
    ['仅 1 单', '#d1b5ff'], ['2–5 单', '#b794ff'], ['6–20 单', '#9873e9'], ['21 单以上', '#e2a3cf'],
  ], { top: 0, left: 'center', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 9 } }),
  grid: { left: 46, right: 22, top: 53, bottom: 35 },
  xAxis: { type: 'value', name: '订单数（单）', nameLocation: 'middle', nameGap: 24, ...axis, nameTextStyle: { color: '#d1b5ff', fontWeight: 700 } },
  yAxis: { type: 'value', name: '平均电量（kWh/单）', nameGap: 22, ...axis, nameTextStyle: { color: '#d1b5ff', fontWeight: 700 } },
  series: ['仅 1 单', '2–5 单', '6–20 单', '21 单以上'].map(segment => ({
    name: segment, type: 'scatter',
    symbolSize: value => Math.max(6, Math.min(25, Math.sqrt(value[2]) * 0.65)),
    data: user.value.points.filter(item => item.segment === segment).map(item => ({
      ...item, value: [item.orders, item.avgKwh, item.totalKwh],
    })),
  })),
}))

const timeOption = computed(() => ({
  tooltip: { ...tooltip, trigger: 'item', formatter: item => `${item.name}<br/>${item.value} 位用户` },
  angleAxis: { type: 'category', data: user.value.timePreference.map(item => item.name), startAngle: 90, axisLabel: { color: '#d5c9ef', fontSize: 9, interval: 0 } },
  radiusAxis: { axisLabel: { color: '#c9bcdb', fontSize: 9 }, splitLine: { lineStyle: { color: '#3d3d64' } } },
  polar: { radius: '58%' },
  series: [{
    type: 'bar', coordinateSystem: 'polar', roundCap: true,
    data: user.value.timePreference.map((item, index) => ({
      name: item.name, value: item.value,
      itemStyle: { color: ['#6265b9', '#f2c36c', '#e99057', '#e67472', '#987bd1'][index] },
    })),
  }],
}))

const revenueOption = computed(() => ({
  color: ['#fbbf5c'],
  tooltip: { ...tooltip, trigger: 'axis', formatter: items => {
    const month = revenue.value.monthly[items[0].dataIndex]
    return `${month.month}<br/>原始记录 ${month.amount.toFixed(2)} 元<br/>规则估算 ${month.estimatedAmount.toFixed(2)} 元<br/>合计 ${month.combinedAmount.toFixed(2)} 元`
  } },
  grid: { left: 48, right: 16, top: 24, bottom: 28 },
  xAxis: { type: 'category', data: revenue.value.monthly.map(item => item.month.slice(2)), ...axis },
  yAxis: { type: 'value', name: '综合费用（元）', ...axis, nameTextStyle: { color: '#fbbf5c', fontWeight: 700 } },
  series: [{ name: '记录+估算', type: 'bar', barMaxWidth: 20, itemStyle: { borderRadius: [5, 5, 0, 0] }, data: revenue.value.monthly.map(item => item.combinedAmount) }],
}))

const revenueSourceOption = computed(() => ({
  // 层次图不再用悬停标签，完整信息由点击后的放大卡片承担。
  tooltip: { ...tooltip, show: false, formatter: item => `${item.name}<br/>原始记录 ${item.data.recordedAmount.toFixed(2)} 元<br/>规则估算 ${item.data.estimatedAmount.toFixed(2)} 元<br/>合计 ${Number(item.data?.originalValue ?? item.value).toFixed(2)} 元` },
  series: [{
    type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false },
    // 根节点（depth 0）只做布局容器：不画底色，也不参与悬停高亮等任何交互。
    levels: [{ itemStyle: { color: 'transparent', borderColor: 'transparent' }, emphasis: { disabled: true } }],
    data: revenue.value.facility.map((item, index) => ({
      name: item.name, value: item.combinedAmount, recordedAmount: item.amount, estimatedAmount: item.estimatedAmount,
      itemStyle: { color: ['#c8793d', '#dfa04c', '#e9b967', '#f3d088'][index] },
    })),
    label: { show: true, formatter: item => item.name, color: '#172c3c', fontSize: 11, fontWeight: 700 },
    itemStyle: { borderColor: '#102b48', borderWidth: 3, gapWidth: 3 },
  }],
}))
</script>

<template>
  <div class="business-mosaic">
    <section class="mosaic-section user-section">
      <div class="mosaic-heading"><h2>用户充电行为</h2><router-link to="/details/users">用户详情 →</router-link></div>
      <div class="user-mosaic">
        <ChartCard class="platform-tile" title="用户平台偏好" :option="platformOption" height="175px" />
        <ChartCard class="frequency-tile" title="复充频次分层" :option="frequencyOption" height="175px" zoom-on-click reset-on-blank />
        <ChartCard class="scatter-tile" title="用户充电频次与单次电量" :option="userScatterOption" height="208px" />
        <ChartCard class="time-tile" title="用户充电时段偏好" :option="timeOption" height="208px" />
      </div>
    </section>
    <section class="mosaic-section revenue-section">
      <div class="mosaic-heading"><h2>费用构成与趋势</h2><router-link to="/details/revenue">费用详情 →</router-link></div>
      <div class="revenue-mosaic">
        <ChartCard class="revenue-month-tile" title="月度记录与估算费用" :option="revenueOption" height="190px" />
        <ChartCard class="revenue-source-tile" title="桩型综合费用" :option="revenueSourceOption" height="180px" zoom-on-click reset-on-blank />
        <section class="panel revenue-note">
          <header class="panel-header"><div><h2>费用来源</h2></div></header>
          <div class="revenue-figures"><div><span>综合费用</span><b>{{ money(revenue.combinedAmount) }} 元</b></div><div><span>来源分项</span><b class="fee-split">记录 {{ money(revenue.recordedAmount) }} 元<br/>估算 {{ money(revenue.estimatedAmount) }} 元</b><small>{{ revenue.paidOrders }} 单记录；{{ revenue.estimatedOrders }} 单估算</small></div></div>
        </section>
      </div>
    </section>
  </div>
</template>
