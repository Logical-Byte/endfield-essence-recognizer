<template>
  <v-container class="h-100 d-flex flex-column gr-4">
    <div>
      <h1 v-if="false">日志</h1>
      <div class="d-flex flex-row flex-wrap ga-3">
        <v-btn :color="isScanning ? 'warning' : 'primary'" @click="toggleScanning">
          {{ isScanning ? '停止扫描基质' : '开始扫描基质' }}
        </v-btn>
        <v-spacer />
        <v-btn
          color="info"
          prepend-icon="mdi-comment-question-outline"
          variant="tonal"
          @click="showFeedbackDialog = true"
        >
          识别有误？点我反馈
        </v-btn>
        <v-btn color="error" @click="clearLogs">清空日志</v-btn>
        <v-btn v-if="false" :color="autoScroll ? 'success' : 'warning'" @click="toggleAutoScroll">
          {{ autoScroll ? '自动滚动：开' : '自动滚动：关' }}
        </v-btn>
        <v-tooltip location="bottom" text="日志文件中的日志更全">
          <template #activator="{ props }">
            <v-badge v-bind="props" icon="mdi-help">
              <v-btn color="secondary" @click="openLogsFolder">打开日志文件目录</v-btn>
            </v-badge>
          </template>
        </v-tooltip>
      </div>
    </div>
    <!-- 卡片 id 供自动滚动取 DOM 用（v-card 上 ref 绑定的是组件实例而非 DOM 元素） -->
    <v-card id="log-card" class="log-card pa-4 overflow-auto" rounded="lg" variant="outlined">
      <template v-if="logs.length > 0">
        <pre
          v-for="line in logs"
          :key="line.id"
          class="log-line text-pre-wrap"
          v-html="line.html"
        />
      </template>
      <pre v-else>暂无日志...</pre>
    </v-card>

    <!-- 反馈 / 排查弹窗 -->
    <v-dialog v-model="showFeedbackDialog" max-width="640" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" color="info">mdi-comment-question-outline</v-icon>
          识别有误？试试这些解决方案
        </v-card-title>
        <v-divider />
        <v-card-text>
          <!-- 方案一 -->
          <h3 class="text-subtitle-1 font-weight-bold mb-1">方案一：清空数据后全量重扫</h3>
          <p class="text-body-2 text-medium-emphasis mb-2">
            可能是历史数据有误。仅清空当前账号「{{
              activeProfileName
            }}」的宝藏基质数据（<strong>不会删除账号</strong>），随后完整扫描一次即可全量重建。
          </p>
          <v-btn
            color="warning"
            prepend-icon="mdi-broom"
            variant="tonal"
            @click="clearActiveConfirm = true"
          >
            清空宝藏基质数据
          </v-btn>

          <v-divider class="my-4" />

          <!-- 方案二 -->
          <h3 class="text-subtitle-1 font-weight-bold mb-1">方案二：重置所有设置到默认值</h3>
          <p class="text-body-2 text-medium-emphasis mb-2">
            可能是设置中有冲突。建议前往设置页逐条查看，或点击下方按钮把所有设置恢复为默认值。
          </p>
          <div class="d-flex flex-wrap ga-2">
            <v-btn
              color="error"
              prepend-icon="mdi-restore"
              variant="tonal"
              @click="resetConfigConfirm = true"
            >
              重置所有设置到默认值
            </v-btn>
            <v-btn
              prepend-icon="mdi-cog"
              to="/settings"
              variant="text"
              @click="showFeedbackDialog = false"
            >
              前往设置页
            </v-btn>
          </div>

          <v-divider class="my-4" />

          <!-- 方案三 -->
          <h3 class="text-subtitle-1 font-weight-bold mb-1">方案三：反馈给我们</h3>
          <p class="text-body-2 text-medium-emphasis mb-2">
            前往 GitHub 提 Issue，或加入反馈交流群提交 bug。
          </p>
          <div class="d-flex flex-wrap ga-2">
            <v-btn
              append-icon="mdi-open-in-new"
              color="primary"
              href="https://github.com/Logical-Byte/endfield-essence-recognizer/issues"
              rel="noopener noreferrer"
              target="_blank"
              variant="tonal"
            >
              GitHub 提 Issue
            </v-btn>
            <v-menu content-class="qq-group-menu-content">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  append-icon="mdi-dots-vertical"
                  prepend-icon="mdi-qqchat"
                  style="background-color: rgb(24, 166, 189); color: rgb(255, 255, 255)"
                >
                  反馈交流群
                </v-btn>
              </template>
              <v-list density="compact">
                <v-list-item
                  v-for="(group, index) in qqGroups"
                  :key="index"
                  :href="group.link"
                  prepend-icon="mdi-qqchat"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  <v-list-item-title>{{ group.name }}</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showFeedbackDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 方案一确认：清空当前账号宝藏基质数据 -->
    <v-dialog v-model="clearActiveConfirm" max-width="440">
      <v-card>
        <v-card-title class="text-warning">确认清空数据</v-card-title>
        <v-card-text>
          确定要清空当前账号「{{
            activeProfileName
          }}」的宝藏基质数据吗？仅清空当前账号数据，不会删除账号，此操作不可撤销。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="clearActiveConfirm = false">取消</v-btn>
          <v-btn color="warning" @click="onClearActiveData">清空</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 方案二确认：重置所有设置 -->
    <v-dialog v-model="resetConfigConfirm" max-width="440">
      <v-card>
        <v-card-title class="text-error">确认重置设置</v-card-title>
        <v-card-text> 确定要把所有设置重置为默认值吗？此操作不可撤销。 </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="resetConfigConfirm = false">取消</v-btn>
          <v-btn color="error" @click="onResetConfig">重置</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts" setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { clearLogs, logs } from '@/composables/useLogs'
import { useProfiles } from '@/composables/useProfiles'
import { useScanningStatus } from '@/composables/useScanningStatus'
import { useToast } from '@/composables/useToast'
import { useWeaponStats } from '@/composables/useWeaponStats'
import { QQ_FEEDBACK_GROUPS } from '@/utils/feedbackGroups'

const autoScroll = ref(true)
const { isScanning } = useScanningStatus()
const { activeProfileName, clearProfileData, treasureMatrix, updateTreasureMatrix } = useProfiles()
const { fetchCustomStats } = useCustomStats()
const { isCustomEntry } = useWeaponStats()
const toast = useToast()

// --- 反馈 / 排查 ---
const showFeedbackDialog = ref(false)
const clearActiveConfirm = ref(false)
const resetConfigConfirm = ref(false)

const qqGroups = QQ_FEEDBACK_GROUPS

/** 方案一：清空当前激活账号的宝藏基质数据（不传 name，由后端取激活账号）。 */
async function onClearActiveData() {
  try {
    await clearProfileData()
    clearActiveConfirm.value = false
    showFeedbackDialog.value = false
    toast.success('已清空当前账号的宝藏基质数据，可重新扫描。')
  } catch (error: unknown) {
    toast.reportError('清空失败', error)
  }
}

/**
 * 方案二：重置所有设置到默认值。
 *
 * 重置会清空自定义基质列表，因此必须同步刷新前端缓存并清理 profile 中
 * 指向它们的条目——否则界面上会继续显示一批已经不存在的"幽灵基质"。
 */
async function onResetConfig() {
  try {
    const res = await fetch('/api/config/reset', { method: 'POST' })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body?.detail ?? detail
      } catch {
        // 响应体不是 JSON 时保留状态码
      }
      throw new Error(detail)
    }

    await fetchCustomStats()
    // 自定义基质已随配置清空，profile 里对它们的引用一并移除
    const remaining = treasureMatrix.value.filter((e) => !isCustomEntry(e.weapon_id))
    if (remaining.length !== treasureMatrix.value.length) {
      await updateTreasureMatrix(remaining)
    }

    resetConfigConfirm.value = false
    showFeedbackDialog.value = false
    toast.success('已重置所有设置到默认值。')
  } catch (error: unknown) {
    toast.reportError('重置失败', error)
  }
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

function toggleScanning() {
  fetch('/api/start_scanning', { method: 'POST' })
}

function openLogsFolder() {
  fetch('/api/open_logs_folder', { method: 'POST' })
}

// --- 日志自动滚动 ---
// 滚动容器缓存一次即可：卡片是 v-card 组件，ref 绑定的不是 DOM 元素，只能按 id 取。
let logCardElement: HTMLElement | null = null
// 每个刷新帧最多做一次布局读取，避免每条日志消息都触发一次强制同步布局。
let scrollFrame = 0

function scheduleScrollToBottom() {
  if (!autoScroll.value || scrollFrame !== 0) {
    return
  }
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = 0
    if (logCardElement) {
      logCardElement.scrollTop = logCardElement.scrollHeight
    }
  })
}

// 监听日志变化，自动滚动
// 最后一行的 id 变化就代表有新日志；用它做依赖，环形缓冲满了一直在滑动时也能触发。
watch(() => logs.value.at(-1)?.id, scheduleScrollToBottom)

// 初始滚动到底部
onMounted(() => {
  nextTick(() => {
    // 卡片是 v-card 组件，ref 绑定的不是 DOM 元素，所以按 id 取一次并缓存
    logCardElement = document.querySelector('#log-card')
    scheduleScrollToBottom()
  })
})
</script>

<style scoped lang="scss">
// 卡片要在剩余空间里自己滚动，所以这里必须把 flex-basis 取 0：
// .v-main 是 flex-shrink:0 的列向 flex 子项，只给 flex-grow 的话内容会把它撑高，
// 结果整个 index 页面变长、滚动的是页面而不是日志区域。
.log-card {
  flex: 1 1 0;
  // 允许收缩到比内容更矮，滚动条才会落在卡片自己身上
  min-height: 0;
}

// 一行一个 pre：去掉浏览器默认的上下外边距，否则行与行之间会空一行
.log-line {
  margin: 0;
  font-size: inherit;
}
</style>

<style lang="scss">
.qq-group-menu-content .v-list-item__spacer {
  width: 0 !important;
}
</style>
