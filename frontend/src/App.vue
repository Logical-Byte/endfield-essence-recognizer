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
          :prepend-icon="(routeItem.meta as any)?.icon"
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
        <v-btn icon="mdi-update" @click="checkForUpdates(true)" />
        <v-btn icon="mdi-theme-light-dark" @click="theme.toggle()" />
      </template>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>

    <!-- 更新提示 -->
    <UpdateDialogs />
  </v-app>
</template>

<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import Logo from '@/components/icons/logo.vue'
import UpdateDialogs from '@/components/UpdateDialogs.vue'
import { useLogs } from '@/composables/useLogs'
import { useUpdateChecker } from '@/composables/useUpdateChecker'
import { useStaticData } from '@/utils/gameData/staticData'

const route = useRoute()
const router = useRouter()
const theme = useTheme()

const drawer = ref<boolean | null>(null)

// 初始化日志 WebSocket 连接
useLogs()

// 检查更新
const { checkForUpdates } = useUpdateChecker()

const { fetchStaticData } = useStaticData()

onMounted(() => {
  // 初始化游戏数据
  fetchStaticData()
  // 初始检查更新
  checkForUpdates(false)
})
</script>

<style scoped lang="scss"></style>
