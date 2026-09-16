<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Object, required: true } })
const fmt = (value, digits = 0) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
const columns = computed(() => {
  // 最长的指标组先入列，再按已分配的指标数选短列；新增分组也会自动填补空白。
  const groups = [...props.data.quality.groups].sort((a, b) => b.metrics.length - a.metrics.length)
  const result = [[], []]
  const totals = [0, 0]
  for (const group of groups) {
    const index = totals[0] <= totals[1] ? 0 : 1
    result[index].push(group)
    totals[index] += group.metrics.length
  }
  return result
})
</script>

<template>
  <div class="quality-page">
    <div class="quality-summary detail-summary">
      <article><span>原始订单</span><b>{{ fmt(data.kpis.rawOrders) }}</b></article>
      <article><span>有效订单率</span><b>{{ data.quality.validOrderRate }}%</b></article>
      <article><span>有效订单</span><b>{{ fmt(data.quality.validOrders) }}</b></article>
      <article><span>清洗后电池记录</span><b>{{ fmt(data.quality.batteryRecords) }}</b></article>
    </div>
    <div class="quality-audit">
      <div v-for="(column, index) in columns" :key="index" class="quality-audit-column">
        <section v-for="group in column" :key="group.title" class="detail-panel quality-group">
          <header><h2>{{ group.title }}</h2><span>{{ group.metrics.length }} 项</span></header>
          <div class="table-scroll"><table><thead><tr><th>质量维度</th><th>数量</th><th>占比</th><th>口径说明</th></tr></thead><tbody>
            <tr v-for="item in group.metrics" :key="item.key"><td>{{ item.label }}</td><td>{{ fmt(item.value, item.unit === '元' ? 2 : 0) }} {{ item.unit }}</td><td>{{ item.rate === null ? '—' : `${item.rate}%` }}</td><td>{{ item.note || '—' }}</td></tr>
          </tbody></table></div>
        </section>
      </div>
    </div>
    <section class="detail-panel quality-rules">
      <h2>清洗规则与指标口径</h2>
      <ul class="detail-rules"><li v-for="note in data.quality.notes" :key="note">{{ note }}</li></ul>
    </section>
  </div>
</template>
