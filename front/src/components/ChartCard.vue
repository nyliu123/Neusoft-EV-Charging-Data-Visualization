<script setup>
import * as echarts from 'echarts/core'
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart, TreemapChart } from 'echarts/charts'
import {
  GridComponent, LegendComponent, MarkAreaComponent,
  PolarComponent, TooltipComponent, VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
let chart
let resizeObserver
let zoomed = false
const resetTreemap = () => {
  // 只复位画布的缩放，不重新计算层次图布局，模块相对位置因此保持不变。
  const surface = chartEl.value?.firstElementChild
  if (surface) surface.style.transform = ''
  zoomed = false
}
const zoomTreemapOnClick = params => {
  if (!props.zoomOnClick || params.seriesType !== 'treemap') return
  const surface = chartEl.value?.firstElementChild
  const data = chart.getModel().getSeriesByIndex(0).getData()
  const graphic = data.getItemGraphicEl(data.indexOfName(params.name))
  const rect = graphic?.getBoundingRect()
  const center = rect && graphic.transformCoordToGlobal(rect.x + rect.width / 2, rect.y + rect.height / 2)
  const centerX = center?.[0]
  const centerY = center?.[1]
  if (!Number.isFinite(centerX) || !Number.isFinite(centerY)) return
  // 缩放整张图使目标模块进入中央；边缘模块允许被裁切，但原始排列不变。
  const scale = Math.min(4, Math.max(1.25, Math.min(
    chartEl.value.clientWidth * 0.78 / rect.width,
    chartEl.value.clientHeight * 0.78 / rect.height,
  )))
  const dx = chartEl.value.clientWidth / 2 - centerX * scale
  const dy = chartEl.value.clientHeight / 2 - centerY * scale
  surface.style.transformOrigin = '0 0'
  surface.style.transition = 'transform 250ms ease-out'
  surface.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`
  zoomed = true
}
const resetTreemapOnBlank = event => {
  if (props.resetOnBlank && zoomed && !event.target) resetTreemap()
}

const render = async () => {
  await nextTick()
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  if (zoomed) resetTreemap()
  chart.setOption(props.option, true)
}

watch(() => props.option, render, { deep: true })

onMounted(async () => {
  await render()
  chart?.on('click', zoomTreemapOnClick)
  chart?.getZr().on('click', resetTreemapOnBlank)
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartEl.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.off('click', zoomTreemapOnClick)
  chart?.getZr().off('click', resetTreemapOnBlank)
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
    <div class="chart-frame">
      <div ref="chartEl" class="chart" :style="{ height }"></div>
    </div>
    <slot></slot>
  </section>
</template>
