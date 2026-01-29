<template>
  <v-app>
    <v-navigation-drawer v-model="drawer">
      <v-card to="/" variant="flat" class="pa-4" rounded="0">
        <logo class="d-block mb-4 w-50 h-auto mx-auto" />
        <h1 class="text-center ma-4">终末地基质<br />妙妙小工具</h1>
      </v-card>
      <v-divider />
      <v-list nav density="comfortable">
        <v-list-item
          v-for="(route, index) in router.options.routes"
          :key="index"
          :to="route.path"
          color="primary"
          :prepend-icon="(route.meta as any)?.icon"
        >
          {{ route.meta?.title ?? route.name }}
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app color="primary" flat density="comfortable">
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-app-bar-title>{{ route.meta?.title || '终末地基质妙妙小工具' }}</v-app-bar-title>
      <template #append>
        <v-tooltip location="start">
          仅游戏内文本支持多语言<br />界面文本目前仅支持简体中文
          <template v-slot:activator="{ props }">
            <v-btn icon v-bind="props">
              <v-icon icon="mdi-translate" />
              <v-menu activator="parent">
                <v-list density="compact">
                  <v-list-item
                    v-for="language in usedLanguages"
                    :key="language"
                    :value="language"
                    :active="currentLanguage === language"
                    @click="setLanguage(language)"
                  >
                    <v-list-item-title>{{ languageToText.get(language) }}</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-menu>
            </v-btn>
          </template>
        </v-tooltip>
        <v-btn icon="mdi-theme-light-dark" @click="theme.toggle()" />
      </template>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script lang="ts" setup>
import Logo from '@/components/icons/logo.vue'
import { useLanguage } from '@/composables/useLanguage'
import { useLogs } from '@/composables/useLogs'
import { initGameData } from '@/utils/gameData/gameData'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from 'vuetify'

const route = useRoute()
const router = useRouter()
const theme = useTheme()

const drawer = ref<boolean | null>(null)

// 语言切换
const { usedLanguages, languageToText, currentLanguage, setLanguage } = useLanguage()

// 初始化日志 WebSocket 连接
useLogs()

// 初始化游戏数据
onMounted(async () => {
  await initGameData()
})
</script>

<style scoped lang="scss"></style>
