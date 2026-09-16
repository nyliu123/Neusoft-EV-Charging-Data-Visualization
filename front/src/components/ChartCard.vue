<script setup>
import * as echarts from 'echarts/core'
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart, TreemapChart } from 'echarts/charts'
import {
  GridComponent, LegendComponent, MarkAreaComponent,
  PolarComponent, TooltipComponent, VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

echarts.use([
  BarChart, HeatmapChart, LineChart, PieChart, ScatterChart, TreemapChart,
  GridComponent, LegendComponent, MarkAreaComponent,
  PolarComponent, TooltipComponent, VisualMapComponent,
  CanvasRenderer,
])

const props = defineProps({
  title: { type: String, required: true },
  option: { type: Object, required: true },
  height: { type: String, default: '230px' },
  resetOnBlank: { type: Boolean, default: false },
  zoomOnClick: { type: Boolean, default: false },
})

const chartEl = ref(null)
const frameEl = ref(null)
const focus = ref(null)
// 压暗与卡片分开：卡片要沿原路缩回去，压暗得同时恢复，两者才能一起结束。
const dim = ref(false)
let chart
let resizeObserver
let collapseTimer

// 放大后的卡片固定占图表区域的比例，以及形变时长（需与样式里的过渡时长一致）。
const FOCUS_RATIO = 0.7
const MORPH_MS = 260

const graphicByName = name => {
  try {
    const data = chart?.getModel().getSeriesByIndex(0).getData()
    const index = data ? data.indexOfName(name) : -1
    return index >= 0 ? data.getItemGraphicEl(index) : null
  } catch {
    return null
  }
}
const collectGraphics = (el, test, depth = 0, found = []) => {
  if (!el || depth > 4) return found
  if (test(el)) found.push(el)
  const children = typeof el.children === 'function' ? el.children() : []
  for (const child of children) collectGraphics(child, test, depth + 1, found)
  return found
}
const isShape = el => typeof el.shape?.width === 'number' && el.style?.fill

// 每个模块画了两层矩形：外层是模块之间的间隙底色，内层才是模块本身。
const innerShapeOf = name => {
  const shapes = collectGraphics(graphicByName(name), isShape)
  return shapes[shapes.length - 1] || null
}

// 缩略图里该模块的底色与标签字体：直接读渲染结果的样式，保证放大后与缩略图一致。
const skinOf = (name, params) => {
  const label = props.option.series?.[0]?.label || {}
  const shape = innerShapeOf(name)
  const text = typeof shape?.getTextContent === 'function' ? shape.getTextContent() : null
  const style = text?.style || {}
  const palette = props.option.color
  return {
    // 优先用数据项自带的底色：画布上的矩形在悬停时已被 emphasis 提亮，直接读会拿到偏亮的颜色。
    background: params?.data?.itemStyle?.color
      || shape?.style?.fill
      || (Array.isArray(palette) ? palette[0] : palette)
      || 'rgba(20, 47, 72, .95)',
    color: style.fill || label.color || '#f2f8ff',
    // 数值（px）：放大时按模块放大的比例一起放大，缩回时回到这个值。
    fontSize: style.fontSize || label.fontSize || 12,
    fontWeight: style.fontWeight || label.fontWeight || 400,
    fontFamily: style.fontFamily || label.fontFamily || 'inherit',
  }
}

// 缩略图里该模块实际可见（有色）的那块矩形。放大和缩回都以它为起止，
// 用外层间隙矩形会比画布上的模块大一圈，缩回结束时就会硬跳一下。
const rectOf = name => {
  const shape = innerShapeOf(name)
  if (!shape) return null
  try {
    const rect = shape.getBoundingRect()
    const start = shape.transformCoordToGlobal(rect.x, rect.y)
    const end = shape.transformCoordToGlobal(rect.x + rect.width, rect.y + rect.height)
    return {
      left: Math.min(start[0], end[0]),
      top: Math.min(start[1], end[1]),
      width: Math.abs(end[0] - start[0]),
      height: Math.abs(end[1] - start[1]),
    }
  } catch {
    return null
  }
}

// 完整信息沿用该图的 tooltip 文本，缩略图里被截断的内容在这里补全。
// 首行是模块名，正好与缩略图上的标签一致；其余是明细，缩回时淡出，
// 于是缩到最小时卡片上只剩模块名，和画布上的标签重合，不会突然换一下。
// 放大后模块名（复充频次分层 / 桩型）要比下面的明细明显大一档。
// 这个倍数只在放大态显现：缩回最小的时候标题回到标签字号，才能和画布上的标签重合。
const TITLE_RATIO = 1.4
const DETAIL_LINE_HEIGHT = 1.35

// 量出元素在基准字号下的自然宽度（临时按内容撑开，测完立刻还原，不会闪烁）。
const naturalWidthOf = el => {
  if (!el) return 0
  const width = el.style.width
  el.style.width = 'max-content'
  const measured = el.getBoundingClientRect().width
  el.style.width = width
  return measured
}
const detailOf = params => {
  const formatter = props.option.tooltip?.formatter
  let html = ''
  if (typeof formatter === 'function') {
    try {
      html = formatter(params) || ''
    } catch {
      // 参数不匹配时退回名称与数值
    }
  }
  if (typeof html !== 'string' || !html) html = `${params.name}<br/>${params.value}`
  const rows = html.split(/<br\s*\/?>/i)
  return {
    title: rows[0],
    detail: rows.slice(1).join('<br/>'),
    detailRows: Math.max(0, rows.length - 1),
    detailMax: `${Math.max(0, rows.length - 1) * DETAIL_LINE_HEIGHT}em`,
  }
}

// 量出文字在基准字号下的自然宽度（临时让它按内容撑开，测完立刻还原，不会闪烁）。

const targetRect = () => {
  const width = chartEl.value.clientWidth * FOCUS_RATIO
  const height = chartEl.value.clientHeight * FOCUS_RATIO
  return {
    left: (chartEl.value.clientWidth - width) / 2,
    top: (chartEl.value.clientHeight - height) / 2,
    width,
    height,
  }
}

const openFocus = async params => {
  if (!chartEl.value) return
  const rect = rectOf(params.name)
  if (!rect) return
  clearTimeout(collapseTimer)
  dim.value = true
  const skin = skinOf(params.name, params)
  focus.value = {
    name: params.name,
    left: rect.left, top: rect.top, width: rect.width, height: rect.height,
    ...skin, ...detailOf(params),
    // 起始字号就是缩略图标签的字号，缩回时回到它。
    baseFontSize: skin.fontSize, fontSize: skin.fontSize, titleFontSize: skin.fontSize,
    morph: false,
    open: false,
  }
  await nextTick()
  const el = frameEl.value?.querySelector('.treemap-focus')
  const target = targetRect()
  // 倍数取几何放大比例，同时不超过“标题和明细刚好都放得下”的倍数，否则会折行或溢出。
  const padding = el ? el.offsetWidth - el.clientWidth : 0
  const textWidth = (target.width - padding) * 0.98
  const titleWidth = naturalWidthOf(el?.querySelector('.treemap-focus-title'))
  const detailWidth = naturalWidthOf(el?.querySelector('.treemap-focus-detail'))
  const lines = focus.value.detailRows
  const ratio = Math.min(target.width / (rect.width || 1), target.height / (rect.height || 1)) || 1
  const factor = Math.max(1, Math.min(
    2.2,
    ratio,
    titleWidth > 0 ? textWidth / titleWidth : Infinity,
    detailWidth > 0 ? (textWidth * TITLE_RATIO) / detailWidth : Infinity,
    (target.height - 20) / (DETAIL_LINE_HEIGHT * skin.fontSize * (1 + lines / TITLE_RATIO)),
  ))
  el?.getBoundingClientRect()   // 强制回流，保证过渡从缩略图矩形开始
  focus.value = {
    ...focus.value,
    ...target,
    // 标题按完整倍数放大，明细按 TITLE_RATIO 折下来，放大态下层级就拉开了。
    titleFontSize: skin.fontSize * factor,
    fontSize: (skin.fontSize * factor) / TITLE_RATIO,
    morph: true,
    open: true,
  }
}

const closeFocus = () => {
  const current = focus.value
  if (!current) return
  clearTimeout(collapseTimer)
  dim.value = false
  focus.value = {
    ...current,
    ...(rectOf(current.name) || {}),
    fontSize: current.baseFontSize,
    titleFontSize: current.baseFontSize,
    // open 关掉让明细淡出，morph 保持开着让几何继续走过渡 —— 这正是放大过程的逆运算。
    open: false,
    closing: true,
    morph: true,
  }
  // 兜底：尺寸没变化等情况下 transitionend 不触发，仍要清掉卡片。
  collapseTimer = setTimeout(() => { focus.value = null }, MORPH_MS + 150)
}

// 缩回动画真正结束再移除卡片，按固定时长猜会提前一帧硬切。
const onCardTransitionEnd = event => {
  if (event.propertyName !== 'width' || !focus.value?.closing) return
  clearTimeout(collapseTimer)
  focus.value = null
}

const focusTreemap = params => {
  if (!props.zoomOnClick || params.seriesType !== 'treemap') return
  // 各模块共用的衬底是层次图的根节点，不参与任何交互，只有真正的模块才响应。
  if (!(props.option.series?.[0]?.data || []).some(item => item.name === params.name)) return
  // 卡片已展开时点任何模块都只是收起，不切换到该模块。
  if (focus.value) { closeFocus(); return }
  openFocus(params)
}
const resetFocusOnBlank = event => {
  if (!props.resetOnBlank || !focus.value) return
  if (!event.target) closeFocus()
}
const closeFocusOnEscape = event => {
  if (event.key === 'Escape' && focus.value) closeFocus()
}

// 图例点掉统计图时同步坐标轴标注：
//  - 该轴上一条都不剩 -> 轴名、刻度、轴线、网格线一起收起；
//  - 只剩一条        -> 轴名用那条线的颜色；
//  - 两条都在        -> 轴名回到中性白（单一系列色代表不了整条轴）。
// 各图把轴名颜色直接写在 option 里，这里取不到"未指定"的默认值，所以中性色用设计里的常量。
// 恢复时每个 show 都要显式写回：setOption 是合并语义，
// 漏掉 show 的话之前设的 false 会一直留着，刻度就再也回不来了。
const NEUTRAL_AXIS_NAME = '#f3f8ff'
const axisVisibility = (axis, visible) => ({
  ...axis,
  name: visible ? axis.name : '',
  // 这里的默认值要用 ECharts 自己的默认：axisLabel/axisLine/splitLine 默认显示、
  // axisTick 默认也显示。写死 false 会把没在 axisStyle 里声明 axisTick 的轴（如月度图右轴）的刻度永久关掉。
  axisLabel: { ...axis.axisLabel, show: visible && (axis.axisLabel?.show ?? true) },
  axisLine: { ...axis.axisLine, show: visible && (axis.axisLine?.show ?? true) },
  axisTick: { ...axis.axisTick, show: visible && (axis.axisTick?.show ?? true) },
  splitLine: { ...axis.splitLine, show: visible && (axis.splitLine?.show ?? true) },
})

const syncAxisToLegend = params => {
  const option = chart?.getOption()
  const series = option?.series || []
  const base = Array.isArray(props.option.yAxis)
    ? props.option.yAxis
    : props.option.yAxis ? [props.option.yAxis] : []
  if (!series.length || !base.length) return
  const selected = params?.selected || {}
  const palette = Array.isArray(props.option.color) ? props.option.color : [props.option.color]
  const axes = base.map((axis, index) => {
    const onThisAxis = series.map((_, i) => i).filter(i => (series[i].yAxisIndex || 0) === index)
    if (!onThisAxis.length) return axis
    const shown = onThisAxis.filter(i => selected[series[i].name] !== false)
    const next = axisVisibility(axis, shown.length > 0)
    // 多系列共用一条轴时没有哪个系列色能代表整条轴，统一回到中性白。
    const color = shown.length === 1 ? palette[shown[0] % palette.length] : NEUTRAL_AXIS_NAME
    return color ? { ...next, nameTextStyle: { ...axis.nameTextStyle, color } } : next
  })
  // 必须用 replaceMerge 整体替换 yAxis：默认合并会先按 name 匹配组件（echarts/lib/util/model.js 的
  // mappingByName 先于 mappingByIndex 执行），而隐藏轴时我们会把 name 清空，
  // 于是恢复时"充电量（kWh）"会被匹配到另一条轴上，两条轴的配置互相串位。
  chart.setOption({ yAxis: axes }, { replaceMerge: 'yAxis' })
}

const focusStyle = computed(() => {
  const item = focus.value
  if (!item) return {}
  return {
    left: `${item.left}px`,
    top: `${item.top}px`,
    width: `${item.width}px`,
    height: `${item.height}px`,
    background: item.background,
    color: item.color,
    fontSize: `${item.fontSize}px`,
    fontWeight: item.fontWeight,
    fontFamily: item.fontFamily,
    '--detail-max': item.detailMax,
  }
})

const render = async () => {
  await nextTick()
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  chart.setOption(props.option, true)
  // 初次渲染也按同一条规则定轴名：一条线用它的颜色，多条线用中性白。
  syncAxisToLegend()
}

watch(() => props.option, render, { deep: true })

onMounted(async () => {
  await render()
  chart?.on('click', focusTreemap)
  chart?.on('legendselectchanged', syncAxisToLegend)
  chart?.getZr().on('click', resetFocusOnBlank)
  window.addEventListener('keydown', closeFocusOnEscape)
  resizeObserver = new ResizeObserver(() => {
    chart?.resize()
    // 画布尺寸变了，卡片目标尺寸和模块矩形都失效，直接收起。
    if (focus.value) { clearTimeout(collapseTimer); focus.value = null; dim.value = false }
  })
  resizeObserver.observe(chartEl.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  clearTimeout(collapseTimer)
  window.removeEventListener('keydown', closeFocusOnEscape)
  chart?.off('click', focusTreemap)
  chart?.off('legendselectchanged', syncAxisToLegend)
  chart?.getZr().off('click', resetFocusOnBlank)
  chart?.dispose()
})
</script>

<template>
  <section class="panel chart-card">
    <header class="panel-header">
      <div>
        <h2>{{ title }}</h2>
      </div>
    </header>
    <div class="chart-frame" ref="frameEl" :class="{ 'chart-frame--focused': dim }">
      <div ref="chartEl" class="chart" :style="{ height }"></div>
      <div
        v-if="focus"
        class="treemap-focus"
        :class="{ 'treemap-focus--morph': focus.morph, 'treemap-focus--open': focus.open }"
        :style="focusStyle"
        @click="closeFocus"
        @transitionend="onCardTransitionEnd"
      ><p class="treemap-focus-title" :style="{ fontSize: `${focus.titleFontSize}px` }" v-html="focus.title"></p><p class="treemap-focus-detail" v-html="focus.detail"></p></div>
    </div>
    <slot></slot>
  </section>
</template>

<style>
/* 缩略图模块点开后放大的详情卡片：底色与字体沿用缩略图里的模块。 */
.chart-frame .treemap-focus {
  position: absolute;
  z-index: 5;
  display: grid;
  place-items: center;
  padding: 10px 12px;
  overflow: hidden;
  text-align: center;
  line-height: 1.35;
  cursor: pointer;
  box-shadow: 0 14px 30px rgba(0, 8, 24, .45);
}
.chart-frame .treemap-focus p { margin: 0; }
/* 标题（模块名）自带字号，随卡片一起放大，缩回时回到标签字号。 */
.chart-frame .treemap-focus-title {
  transition: font-size 260ms cubic-bezier(.22, 1, .36, 1);
}
/* 明细默认收起。收起时它比几何更快淡出，所以缩到最小时只剩模块名，
   和缩略图上那一行标签重合，不会在移除卡片时突然换一下。 */
.chart-frame .treemap-focus-detail {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 180ms cubic-bezier(.22, 1, .36, 1), opacity 130ms ease;
}
.chart-frame .treemap-focus--open .treemap-focus-detail {
  max-height: var(--detail-max, 4em);
  opacity: 1;
  transition: max-height 260ms cubic-bezier(.22, 1, .36, 1), opacity 220ms ease 60ms;
}
/* 形变：位置、宽高与字号一起过渡，缩回就是同一条过渡的逆过程。卡片不做圆角。 */
.chart-frame .treemap-focus--morph {
  transition:
    left 260ms cubic-bezier(.22, 1, .36, 1), top 260ms cubic-bezier(.22, 1, .36, 1),
    width 260ms cubic-bezier(.22, 1, .36, 1), height 260ms cubic-bezier(.22, 1, .36, 1),
    font-size 260ms cubic-bezier(.22, 1, .36, 1);
}
/* 放大期间其余模块压暗虚化，突出被点中的模块。 */
.chart { transition: filter 260ms ease; }
.chart-frame--focused .chart { filter: brightness(.45) saturate(.55) blur(1.2px); }
</style>
