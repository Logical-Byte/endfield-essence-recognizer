<template>
  <v-container>
    <h1>友情链接</h1>

    <!-- 加载状态 -->
    <div v-if="loading" class="d-flex flex-column justify-center align-center gr-4 my-8">
      <v-progress-circular color="primary" indeterminate size="40" />
      <p>加载中……</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="d-flex flex-column justify-center align-center gr-4 my-8">
      <v-alert type="error">{{ error }}</v-alert>
      <v-btn color="primary" @click="fetchLinks">重试</v-btn>
    </div>

    <!-- 正常状态 -->
    <v-row v-else>
      <v-col v-for="link in links" :key="link.id" cols="12" sm="6" lg="4" xl="3" class="d-flex">
        <v-card class="flex-grow-1 d-flex flex-column gr-6 pa-8" hover rounded="xl">
          <div class="d-flex flex-row align-center gc-4">
            <v-avatar rounded size="48">
              <v-img
                v-if="link.icon_url"
                :alt="`${link.localized_name.zh_CN}图标`"
                :src="link.icon_url"
              />
              <v-icon v-else>mdi-link</v-icon>
            </v-avatar>
            <h2 class="font-weight-bold my-0">{{ link.localized_name.zh_CN }}</h2>
          </div>

          <!-- 标签 -->
          <v-chip-group v-if="link.localized_tags.zh_CN.length > 0" column>
            <v-chip v-for="(tag, index) in link.localized_tags.zh_CN" :key="index">
              {{ tag }}
            </v-chip>
          </v-chip-group>

          <!-- 描述 -->
          <p class="text-pre-wrap my-0 opacity-80">{{ link.localized_description.zh_CN }}</p>

          <!-- 标语 -->
          <div v-if="link.localized_slogan.zh_CN">
            <v-divider />
            <p class="text-primary my-2 text-pre-wrap font-weight-medium">
              <i>{{ link.localized_slogan.zh_CN }}</i>
            </p>
            <v-divider />
          </div>

          <!-- 链接按钮 -->
          <div class="mt-auto d-flex flex-row flex-wrap ga-2">
            <v-btn
              v-for="(linkItem, index) in link.links"
              :key="index"
              append-icon="mdi-open-in-new"
              color="primary"
              :href="linkItem.url"
              rel="noopener noreferrer"
              target="_blank"
              :variant="linkItem.primary ? 'flat' : 'outlined'"
            >
              {{ linkItem.localized_name.zh_CN }}
            </v-btn>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import extraFriendLinks from '@/assets/json/friendLinks.json'
import { onMounted, ref } from 'vue'

/**
 * 本地化值接口
 */
interface LocalizedValue {
  zh_CN: string
  en_US: string
}

/**
 * 本地化数组接口
 */
interface LocalizedArray {
  zh_CN: string[]
  en_US: string[]
}

/**
 * 链接项接口
 */
interface LinkItem {
  primary: boolean
  regionality: string
  localized_name: LocalizedValue
  url: string
}

/**
 * 友情链接接口
 */
interface FriendLink {
  id: string
  localized_name: LocalizedValue
  localized_description: LocalizedValue
  localized_slogan: LocalizedValue
  localized_tags: LocalizedArray
  icon_url: string
  links: LinkItem[]
}

/**
 * API 响应接口
 */
interface ApiResponse {
  code: string
  message: string
  data: FriendLink[]
}

const apiUrl = 'https://server-cdn.ceobecanteen.top/api/v1/cdn/operate/toolLink/list'

// 响应式状态
const links = ref<FriendLink[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

/**
 * 获取友情链接数据
 */
async function fetchLinks(): Promise<void> {
  loading.value = true
  error.value = null

  try {
    const response = await fetch(apiUrl)

    if (!response.ok) {
      throw new Error(`HTTP 错误: ${response.status} ${response.statusText}`)
    }

    const data: ApiResponse = await response.json()

    if (data.code !== '00000') {
      throw new Error(`API 错误: ${data.message}`)
    }

    links.value = [...extraFriendLinks, ...data.data]
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取数据失败'
    console.error('获取友情链接失败:', err)
  } finally {
    loading.value = false
  }
}

// 组件挂载时获取数据
onMounted(() => {
  fetchLinks()
})
</script>

<style scoped lang="scss"></style>
