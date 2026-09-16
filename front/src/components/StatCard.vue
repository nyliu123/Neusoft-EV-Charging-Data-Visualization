<script setup>
defineProps({
  label: String,
  value: [String, Number],
  unit: String,
  icon: String,
  tone: { type: String, default: 'blue' },
})
</script>

<template>
  <article class="stat-card" :class="`tone-${tone}`">
    <div class="stat-icon">{{ icon }}</div>
    <div class="stat-body">
      <span class="stat-label">{{ label }}</span>
      <div class="stat-value">{{ value }} <small>{{ unit }}</small></div>
    </div>
  </article>
</template>
