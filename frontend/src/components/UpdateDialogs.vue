<template>
  <!-- 发现新版本 -->
  <v-snackbar v-model="hasNewVersionDialog" vertical>
    <p><strong>发现新版本！</strong></p>
    <p><strong>当前版本：</strong>{{ currentVersion }}</p>
    <p><strong>最新版本：</strong>{{ updateInfo?.latestVersion }}</p>
    <p v-if="updateInfo?.packageType === 'incremental'">
      <strong>更新方式：</strong>增量更新<span v-if="updateInfo?.size"
        >（约 {{ formatSize(updateInfo.size) }}）</span
      >
    </p>
    <template #actions>
      <v-btn class="ms-2" @click="hasNewVersionDialog = false">稍后提醒</v-btn>
      <v-btn class="ms-2" href="https://ef.yituliu.cn/resources/essence-recognizer" target="_blank"
        >前往官网</v-btn
      >
      <v-btn
        class="ms-2"
        color="primary"
        :loading="isUpdating"
        variant="elevated"
        @click="installUpdate(false)"
        >一键更新</v-btn
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

  <!-- 更新进度 -->
  <v-dialog v-model="updateProgressDialog" max-width="500" persistent>
    <v-card>
      <v-card-title>更新下载</v-card-title>
      <v-card-text>
        <v-alert v-if="downloadFailed" class="mb-4" color="error" variant="tonal">
          <strong>下载失败：</strong>{{ downloadErrorMessage }}
        </v-alert>

        <div class="mb-4">
          <div class="d-flex justify-space-between mb-2">
            <span>{{ currentVersion }} → {{ updateInfo?.latestVersion }}</span>
            <span v-if="totalKnown"
              >{{ formatSize(downloadedSize) }} / {{ formatSize(totalSize) }}</span
            >
            <span v-else>{{ formatSize(downloadedSize) }} 已下载</span>
          </div>
          <v-progress-linear
            color="primary"
            height="20"
            :indeterminate="!totalKnown && downloadedSize > 0"
            :model-value="totalKnown ? downloadProgress : 0"
          >
            <template #default>
              <strong v-if="totalKnown">{{ downloadProgress.toFixed(1) }}%</strong>
              <strong v-else>下载中…</strong>
            </template>
          </v-progress-linear>
          <div class="text-center mt-2 text-caption">
            {{ downloadSpeed > 0 ? formatSpeed(downloadSpeed) : '连接中…' }}
          </div>
        </div>

        <v-alert class="mb-3" type="info" variant="tonal">
          当前更新流程：{{ selectedFlowName }}
        </v-alert>

        <v-select
          v-if="selectedFlow === 'github'"
          v-model="selectedMirror"
          class="mb-3"
          density="comfortable"
          hide-details
          :items="mirrorOptions"
          label="下载源"
          variant="outlined"
        >
          <template #append-inner>
            <v-tooltip location="top">
              <template #activator="{ props }">
                <v-icon v-bind="props" size="small">mdi-information-outline</v-icon>
              </template>
              <span>当前选择: {{ selectedMirrorName }}</span>
            </v-tooltip>
          </template>
        </v-select>

        <v-expansion-panels v-model="showProxyInput" class="mb-3" flat>
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div class="d-flex align-center">
                <span>使用代理</span>
                <v-spacer />
                <v-switch
                  v-model="proxyEnabled"
                  class="ms-4"
                  color="primary"
                  density="compact"
                  hide-details
                  @click.stop
                />
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-text-field
                v-model="proxyPort"
                class="mb-2"
                density="comfortable"
                :disabled="!proxyEnabled"
                hide-details
                label="代理端口"
                placeholder="7890"
                type="number"
                variant="outlined"
              />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn v-if="downloadFailed" color="primary" @click="installUpdate()">重试</v-btn>
        <v-btn @click="cancelDownload">{{ downloadFailed ? '关闭' : '取消' }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- SHA-256 校验失败 -->
  <v-dialog v-model="sha256MismatchDialog" max-width="520" persistent>
    <v-card>
      <v-card-title class="text-error">
        <v-icon class="mr-2">mdi-shield-alert</v-icon>
        更新包完整性校验失败
      </v-card-title>
      <v-card-text>
        <v-alert class="mb-3" color="warning" variant="tonal">
          更新包的 SHA-256 哈希值与预期不符，可能是下载不完整、文件损坏，或源站/镜像被篡改。
        </v-alert>
        <div class="text-body-2 mb-2">
          <strong>期望：</strong>
          <code class="text-caption">{{ sha256Expected }}</code>
        </div>
        <div class="text-body-2 mb-3">
          <strong>实际：</strong>
          <code class="text-caption">{{ sha256Actual }}</code>
        </div>
        <p class="text-body-2">是否仍然继续安装？</p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="cancelSha256Mismatch">取消更新</v-btn>
        <v-btn color="warning" variant="elevated" @click="forceInstall">继续安装</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { useUpdateChecker } from '@/composables/useUpdateChecker'
import { useUpdateMirrors } from '@/composables/useUpdateMirrors'

const {
  hasNewVersionDialog,
  isLatestVersionDialog,
  checkUpdateFailedDialog,
  currentVersion,
  updateInfo,
  updateErrorMessage,
  isUpdating,
  updateProgressDialog,
  downloadProgress,
  downloadSpeed,
  downloadedSize,
  totalSize,
  totalKnown,
  selectedFlow,
  selectedMirror,
  proxyEnabled,
  proxyPort,
  showProxyInput,
  downloadFailed,
  downloadErrorMessage,
  sha256MismatchDialog,
  sha256Expected,
  sha256Actual,
  installUpdate,
  forceInstall,
  cancelSha256Mismatch,
  cancelDownload,
} = useUpdateChecker()

const { mirrorOptions } = useUpdateMirrors()

const selectedMirrorName = computed(() => {
  const mirror = mirrorOptions.value.find((m) => m.value === selectedMirror.value)
  return mirror ? mirror.title : 'GitHub 官方'
})

const selectedFlowName = computed(() => {
  if (selectedFlow.value === 'cn_yituliu') return '一图流 API (CN 镜像)'
  if (selectedFlow.value === 'cn_mirrorchyan') return 'Mirror 酱'
  return 'GitHub Release'
})

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

function formatSpeed(bytesPerSecond: number): string {
  return formatSize(bytesPerSecond) + '/s'
}
</script>
