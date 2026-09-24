<template>
  <v-app>
    <v-navigation-drawer v-model="drawer">
      <v-card class="pa-4" rounded="0" to="/" variant="flat">
        <logo class="d-block mb-4 w-50 h-auto mx-auto" />
        <h1 class="text-center ma-4">终末地基质<br />妙妙小工具</h1>
      </v-card>
      <v-divider />
      <v-list density="comfortable" nav>
        <v-list-item
          v-for="(routeItem, index) in router.options.routes"
          :key="index"
          color="primary"
          :prepend-icon="getRouteIcon(routeItem)"
          :to="routeItem.path"
        >
          {{ routeItem.meta?.title ?? routeItem.name }}
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app color="primary" density="comfortable" flat>
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title>{{ route.meta?.title || '终末地基质妙妙小工具' }}</v-app-bar-title>
      <template #append>
        <profile-selector />
        <v-btn icon="mdi-update" @click="checkForUpdates(true)" />
        <v-btn icon="mdi-theme-light-dark" @click="theme.toggle()" />
      </template>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>

    <!-- 更新提示 -->
    <UpdateDialogs />

    <!-- 全局操作结果提示 -->
    <ToastHost />
  </v-app>
</template>

<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { type RouteRecordRaw, useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import Logo from '@/components/icons/logo.vue'
import ProfileSelector from '@/components/ProfileSelector.vue'
import ToastHost from '@/components/ToastHost.vue'
import UpdateDialogs from '@/components/UpdateDialogs.vue'
import { useLogs } from '@/composables/useLogs'
import { useProfilesEvents } from '@/composables/useProfilesEvents'
import { useUpdateChecker } from '@/composables/useUpdateChecker'
import { useStaticData } from '@/utils/gameData/staticData'

const route = useRoute()
const router = useRouter()
const theme = useTheme()

const drawer = ref<boolean | null>(null)

/** 从路由元信息中提取导航图标（meta 中的值类型未知，需先收窄） */
function getRouteIcon(routeItem: RouteRecordRaw): string {
  const icon = routeItem.meta?.icon
  return typeof icon === 'string' && icon ? icon : String(routeItem.name ?? '')
}

// 初始化日志 WebSocket 连接
useLogs()

// 订阅后端事件（扫描完成后自动刷新宝藏基质等页面数据）
useProfilesEvents()

// 检查更新
const { checkForUpdates } = useUpdateChecker()

const { fetchStaticData } = useStaticData()

function scheduleStartupUpdateCheck() {
  const runCheck = () => {
    void checkForUpdates(false, { silent: true, timeoutMs: 2500 })
  }

  // 页面加载完成后再等待浏览器空闲，尽量降低后台检查对启动体验的影响。
  const runWhenIdle = () => {
    const requestIdleCallback = (
      window as Window & {
        requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number
      }
    ).requestIdleCallback

    if (requestIdleCallback) {
      requestIdleCallback(runCheck, { timeout: 3000 })
    } else {
      window.setTimeout(runCheck, 1500)
    }
  }

  // 等页面资源完整加载后再做后台检查，避免启动阶段抢占交互体验。
  if (document.readyState === 'complete') {
    window.requestAnimationFrame(runWhenIdle)
  } else {
    window.addEventListener('load', () => window.requestAnimationFrame(runWhenIdle), { once: true })
  }
}

onMounted(() => {
  // 初始化游戏数据
  void fetchStaticData()
  // 初始检查更新放到后台空闲时执行，手动点击更新按钮仍然会立即检查。
  scheduleStartupUpdateCheck()
})
</script>

<style scoped lang="scss"></style>
