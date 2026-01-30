<template>
  <!-- 发现新版本 -->
  <v-snackbar v-model="hasNewVersionDialog" vertical>
    <p><strong>发现新版本！</strong></p>
    <p><strong>当前版本：</strong>{{ currentVersion }}</p>
    <p><strong>最新版本：</strong>{{ updateInfo?.latestVersion }}</p>
    <template #actions>
      <v-btn class="ms-2" @click="hasNewVersionDialog = false">稍后提醒</v-btn>
      <v-btn class="ms-2" href="https://ef.yituliu.cn/resources/essence-recognizer" target="_blank"
        >查看更新日志</v-btn
      >
      <v-btn
        class="ms-2"
        color="primary"
        variant="elevated"
        :href="updateInfo?.downloadUrl"
        target="_blank"
        >立即下载</v-btn
      >
    </template>
  </v-snackbar>

  <!-- 已是最新版本 -->
  <v-snackbar v-model="isLatestVersionDialog" color="info">
    <strong>已是最新版本：</strong>{{ currentVersion }}
    <template #actions>
      <v-btn text @click="isLatestVersionDialog = false">关闭</v-btn>
    </template>
  </v-snackbar>

  <!-- 检查更新失败 -->
  <v-snackbar v-model="checkUpdateFailedDialog" color="error">
    <strong>检查更新失败：</strong>{{ updateErrorMessage }}
    <template #actions>
      <v-btn text @click="checkUpdateFailedDialog = false">关闭</v-btn>
    </template>
  </v-snackbar>
</template>

<script lang="ts" setup>
import { useUpdateChecker } from '@/composables/useUpdateChecker'
const {
  hasNewVersionDialog,
  isLatestVersionDialog,
  checkUpdateFailedDialog,
  currentVersion,
  updateInfo,
  updateErrorMessage,
} = useUpdateChecker()
</script>
