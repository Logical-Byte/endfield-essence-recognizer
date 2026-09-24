<template>
  <v-btn
    v-show="visible"
    aria-label="回到顶部"
    class="back-to-top-btn"
    color="primary"
    icon="mdi-chevron-up"
    size="large"
    @click="scrollToTop"
  />
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref } from 'vue'

const visible = ref(false)

function handleScroll() {
  // 当滚动超过 300px 时显示按钮
  visible.value = window.scrollY > 300
}

function scrollToTop() {
  window.scrollTo({
    top: 0,
    behavior: 'smooth',
  })
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped lang="scss">
.back-to-top-btn {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
  }
}
</style>
