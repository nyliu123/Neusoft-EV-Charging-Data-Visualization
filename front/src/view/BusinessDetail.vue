<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const dashboard = ref(null)
const error = ref('')
const isRevenue = computed(() => route.params.section === 'revenue')
const fmt = (value, digits = 0) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })

onMounted(async () => {
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE || '/api'}/dashboard`)
    const result = await response.json()
    if (!response.ok) throw new Error(result.msg)
    dashboard.value = result.data
  } catch (cause) {
    error.value = cause.message
  }
})
</script>

<template>
  <main class="detail-shell">
    <header class="detail-header">
      <div><router-link to="/" class="back-link">← 返回大屏</router-link><h1>{{ isRevenue ? '费用记录与规则估算' : '用户充电行为' }}</h1><p>{{ isRevenue ? '原始费用与分时估算分项' : '按用户标识去重的行为统计' }}</p></div>
      <nav>
        <router-link to="/details/operations">运营分析</router-link><router-link to="/details/stations">站点详情</router-link>
        <router-link to="/details/users" :class="{ active: !isRevenue }">用户行为</router-link><router-link to="/details/revenue" :class="{ active: isRevenue }">收费分析</router-link>
        <router-link to="/details/prediction">预测分析</router-link><router-link to="/details/quality">数据质量</router-link>
      </nav>
    </header>
    <div v-if="error" class="detail-error">数据加载失败：{{ error }}</div>
    <div v-else-if="!dashboard" class="detail-loading">正在加载详情数据…</div>

    <template v-else-if="!isRevenue">
      <div class="detail-summary">
        <article><span>已服务用户（样本期订单 ≥1 单）</span><b>{{ dashboard.kpis.users }} 人</b></article>
        <article><span>复充用户（样本期订单 ≥2 单）</span><b>{{ dashboard.userBehavior.repeatUsers }} 人</b></article>
        <article><span>站点粘性用户（使用最多的站点订单占比 ≥50%）</span><b>{{ dashboard.userBehavior.stationLoyaltyUsers }} 人</b></article>
        <article><span>重度用户（样本期订单 ≥21 单）</span><b>{{ dashboard.userBehavior.frequencySegments[3].value }} 人</b></article>
      </div>
      <p class="detail-caveat">{{ dashboard.userBehavior.note }}。时段与桩型偏好也按每位用户的最多记录归类，不能解释未观测到的选择原因。</p>
      <div class="detail-columns">
        <section class="detail-panel"><h2>平台偏好</h2><table><thead><tr><th>偏好平台</th><th>用户人数</th><th>用户占比</th></tr></thead><tbody><tr v-for="item in dashboard.userBehavior.platformPreference" :key="item.name"><td>{{ item.name }}</td><td>{{ item.value }} 人</td><td>{{ (item.value / dashboard.kpis.users * 100).toFixed(1) }}%</td></tr></tbody></table><h2 class="detail-subhead">复充频次分层</h2><table><thead><tr><th>样本期订单频次</th><th>用户人数</th></tr></thead><tbody><tr v-for="item in dashboard.userBehavior.frequencySegments" :key="item.name"><td>{{ item.name }}</td><td>{{ item.value }} 人</td></tr></tbody></table></section>
        <section class="detail-panel"><h2>充电时段偏好</h2><table><thead><tr><th>时段</th><th>用户人数</th></tr></thead><tbody><tr v-for="item in dashboard.userBehavior.timePreference" :key="item.name"><td>{{ item.name }}</td><td>{{ item.value }} 人</td></tr></tbody></table><h2 class="detail-subhead">充电桩型偏好</h2><table><thead><tr><th>桩型</th><th>用户人数</th></tr></thead><tbody><tr v-for="item in dashboard.userBehavior.facilityPreference" :key="item.name"><td>{{ item.name }}</td><td>{{ item.value }} 人</td></tr></tbody></table></section>
      </div>
      <section class="detail-panel"><h2>用户充电频次与电量明细</h2><p>按匿名用户标识展示，订单数说明复充频次；单次平均电量说明使用强度。不能据此推测用户收入或个人身份。</p><div class="table-scroll user-ledger-scroll"><table><thead><tr><th>用户标识</th><th>订单数（单）</th><th>单次平均（kWh/单）</th><th>累计电量（kWh）</th><th>频次分层</th></tr></thead><tbody><tr v-for="item in dashboard.userBehavior.points" :key="item.userId"><td>{{ item.userId }}</td><td>{{ item.orders }}</td><td>{{ item.avgKwh }}</td><td>{{ item.totalKwh }}</td><td>{{ item.segment }}</td></tr></tbody></table></div></section>
    </template>

    <template v-else>
      <div class="detail-summary">
        <article><span>综合费用</span><b>{{ fmt(dashboard.revenue.combinedAmount, 2) }} 元</b></article>
        <article><span>原始记录费用</span><b>{{ fmt(dashboard.revenue.recordedAmount, 2) }} 元</b><small>{{ dashboard.revenue.paidOrders }} 单有效充电订单</small></article>
        <article><span>按分时估算规则估算</span><b>{{ fmt(dashboard.revenue.estimatedAmount, 2) }} 元</b><small>{{ dashboard.revenue.estimatedOrders }} 单零费用订单</small></article>
        <article><span>估算覆盖率</span><b>{{ (dashboard.revenue.estimatedOrders / dashboard.kpis.orders * 100).toFixed(1) }}%</b></article>
      </div>
      <p class="detail-caveat">{{ dashboard.revenue.note }} 原始费用列另有 {{ dashboard.revenue.excludedRecordedOrders }} 单、{{ fmt(dashboard.revenue.excludedRecordedAmount, 2) }} 元属于零电量记录，单独列为异常；原始费用列合计 {{ fmt(dashboard.revenue.rawRecordedAmount, 2) }} 元。</p>
      <div class="detail-columns fee-columns">
        <section class="detail-panel"><h2>月度费用分项</h2><table><thead><tr><th>月份</th><th>有效订单</th><th>记录（元）</th><th>估算（元）</th><th>合计（元）</th></tr></thead><tbody><tr v-for="item in dashboard.revenue.monthly" :key="item.month"><td>{{ item.month }}</td><td>{{ item.orders }} 单</td><td>{{ fmt(item.amount, 2) }}</td><td>{{ fmt(item.estimatedAmount, 2) }}</td><td>{{ fmt(item.combinedAmount, 2) }}</td></tr></tbody></table></section>
        <section class="detail-panel"><h2>桩型费用分项</h2><table><thead><tr><th>桩型</th><th>订单</th><th>记录（元）</th><th>估算（元）</th><th>合计（元）</th></tr></thead><tbody><tr v-for="item in dashboard.revenue.facility" :key="item.name"><td>{{ item.name }}</td><td>{{ item.orders }} 单</td><td>{{ fmt(item.amount, 2) }}</td><td>{{ fmt(item.estimatedAmount, 2) }}</td><td>{{ fmt(item.combinedAmount, 2) }}</td></tr></tbody></table><h2 class="detail-subhead">分时估算规则</h2><table><thead><tr><th>开始时段</th><th>估算单价</th></tr></thead><tbody><tr><td>00:00–06:59</td><td>1.2 元/kWh</td></tr><tr><td>07:00–11:59</td><td>1.5 元/kWh</td></tr><tr><td>12:00–17:59</td><td>1.8 元/kWh</td></tr><tr><td>18:00–23:59</td><td>2.0 元/kWh</td></tr></tbody></table><p class="fee-rule-note">注：只有原始费用为 0 的有效充电订单使用此规则。</p></section>
      </div>
    </template>
  </main>
</template>
