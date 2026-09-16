// 图例文字用各系列自己的颜色，并让取消选中时文字和图形一起熄灭。
export const coloredLegend = (entries, options = {}) => ({
  ...options,
  // 颜色挂在每个数据项的 textStyle 上，不能用 textStyle.rich：
  // rich 片段里的 color 会盖掉 inactiveColor（LegendView 只在非 rich 时把 fill 换成 inactiveColor），
  // 结果是取消选中时线没了、图例文字却还亮着。
  inactiveColor: '#5b6b80',
  data: entries.map(([label, color]) => ({ name: label, textStyle: { color } })),
})
