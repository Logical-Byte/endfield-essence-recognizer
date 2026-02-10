import { createRouter, createWebHistory } from 'vue-router'
import Docs from '@/pages/docs.vue'
import FriendLinks from '@/pages/friend-links.vue'
import Index from '@/pages/index.vue'
import Monitor from '@/pages/monitor.vue'
import Settings from '@/pages/settings.vue'
import Yituliu from '@/pages/yituliu.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'logs',
      component: Index,
      meta: { title: '日志', icon: 'mdi-file-document-outline' },
    },
    {
      path: '/docs',
      name: 'docs',
      component: Docs,
      meta: { title: '文档', icon: 'mdi-file-document' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: Settings,
      meta: { title: '设置', icon: 'mdi-cog' },
    },
    {
      path: '/monitor',
      name: 'monitor',
      component: Monitor,
      meta: { title: '监控', icon: 'mdi-monitor' },
    },
    {
      path: '/friend-links',
      name: 'friend-links',
      component: FriendLinks,
      meta: { title: '友情链接', icon: 'mdi-link' },
    },
    {
      path: '/yituliu',
      name: 'yituliu',
      component: Yituliu,
      meta: { title: '终末地一图流', icon: 'mdi-map' },
    },
  ],
})

router.afterEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 终末地基质妙妙小工具`
  } else {
    document.title = '终末地基质妙妙小工具'
  }
})

export default router
