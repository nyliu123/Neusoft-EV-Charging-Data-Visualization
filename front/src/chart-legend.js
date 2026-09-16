export const coloredLegend = (entries, options = {}) => ({
  ...options,
  formatter: name => {
    const index = entries.findIndex(([label]) => label === name)
    return index < 0 ? name : `{legend${index}|${name}}`
  },
  textStyle: {
    ...options.textStyle,
    rich: Object.fromEntries(entries.map(([, color], index) => [`legend${index}`, { color }])),
  },
})
