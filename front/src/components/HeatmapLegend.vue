<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ max: { type: Number, required: true }, colors: { type: Array, required: true } })
const emit = defineEmits(['focus'])
const point = ref(0)
const dragging = ref(false)
const bar = ref(null)
const percent = computed(() => point.value / Math.max(props.max, 1) * 100)
const gradient = computed(() => `linear-gradient(90deg, ${props.colors.join(', ')})`)

const setPoint = value => {
  // 拖动期间按整数订单数更新阈值；静止悬停不会改变热力图。
  const next = Math.min(props.max, Math.max(0, Math.round(value)))
  if (next === point.value) return
  point.value = next
  if (dragging.value) emit('focus', next)
}
const setFromPointer = event => {
  const rect = bar.value.getBoundingClientRect()
  setPoint((event.clientX - rect.left) / rect.width * props.max)
}
const start = event => {
  event.preventDefault()
  dragging.value = true
  event.currentTarget.setPointerCapture(event.pointerId)
  // 按住手柄本身不筛选；只有手柄移动到新的整数阈值才更新热力块。
}
const anchor = event => {
  event.preventDefault()
  dragging.value = true
  bar.value.setPointerCapture(event.pointerId)
  // 点击渐变条时立即把定位点锚定到对应阈值，并按新阈值筛选热力块。
  setFromPointer(event)
}
const move = event => { if (dragging.value) setFromPointer(event) }
const stop = () => {
  if (!dragging.value) return
  dragging.value = false
}
const key = event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    dragging.value = true
    setPoint(point.value + (event.key === 'ArrowRight' ? 1 : -1))
    emit('focus', point.value)
  } else if (event.key === 'Escape') stop()
}
</script>

<template>
  <div class="heatmap-legend">
    <div ref="bar" class="heatmap-legend-bar" :style="{ background: gradient }"
      @pointerdown="anchor" @pointermove="move" @pointerup="stop" @pointercancel="stop">
      <button class="heatmap-legend-point" :style="{ left: `clamp(7px, ${percent}%, calc(100% - 7px))` }"
        type="button" role="slider" aria-label="点击渐变条或拖动定位点筛选热力图"
        :aria-valuemin="0" :aria-valuemax="max" :aria-valuenow="point"
        @pointerdown.stop="start" @pointermove="move" @pointerup="stop" @pointercancel="stop"
        @keydown="key" @keyup="stop" @blur="stop"></button>
    </div>
    <span class="heatmap-legend-focus" :style="{ left: `clamp(30px, ${percent}%, calc(100% - 30px))` }">≥ {{ point }} 单</span>
    <span v-if="point > max * .2" class="heatmap-legend-min">0 单</span><span v-if="point < max * .8" class="heatmap-legend-max">{{ max }} 单</span>
  </div>
</template>
