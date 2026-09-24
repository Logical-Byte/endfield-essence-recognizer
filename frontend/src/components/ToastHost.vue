<template>
  <!--
    全局提示容器：挂在 App 根部，任何组件通过 useToast() 上报的消息都在这里呈现。
    多条消息纵向堆叠，避免后一条把前一条顶掉导致用户漏看。
  -->
  <div aria-live="polite" class="toast-stack" role="status">
    <v-snackbar
      v-for="(message, index) in messages"
      :key="message.id"
      :color="message.level"
      :model-value="true"
      multi-line
      :style="{ '--toast-offset': `${index * 4.5}rem` }"
      :timeout="message.timeout"
      @update:model-value="(open: boolean) => !open && dismiss(message.id)"
    >
      {{ message.text }}
      <template #actions>
        <v-btn icon="mdi-close" size="small" variant="text" @click="dismiss(message.id)" />
      </template>
    </v-snackbar>
  </div>
</template>

<script lang="ts" setup>
import { useToast } from '@/composables/useToast'

const { messages, dismiss } = useToast()
</script>

<style lang="scss">
.toast-stack {
  .v-snackbar__wrapper {
    margin-bottom: var(--toast-offset, 0);
  }
}
</style>
