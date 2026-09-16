// 图表悬浮标签统一采用深蓝面板、亮蓝描边和浅色文字，与大屏面板一致。
export const chartTooltip = (overrides = {}) => ({
  trigger: 'item',
  renderMode: 'html',
  // 提示框挂到 body 并限制在图表视口内，避免被卡片或画布的 overflow 裁掉。
  appendTo: 'body',
  confine: true,
  backgroundColor: '#142f48',
  borderColor: '#62c9ec',
  borderWidth: 1,
  borderRadius: 6,
  padding: [10, 13],
  textStyle: { color: '#f2f8ff', fontSize: 12, lineHeight: 19, fontWeight: 500 },
  extraCssText: 'box-shadow: 0 12px 24px rgba(0, 8, 24, .42);',
  ...overrides,
})
