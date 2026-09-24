import { onMounted, ref } from 'vue'

export function useUpdateMirrors() {
  const mirrorOptions = ref<Array<{ title: string; value: string }>>([])
  const flowOptions = ref<Array<{ title: string; value: string }>>([])

  onMounted(async () => {
    try {
      // 更新流程由后端开关控制；GitHub 下载镜像只在 GitHub 流程内使用。
      const [mirrorsResponse, flowsResponse] = await Promise.all([
        fetch('/api/update/mirrors'),
        fetch('/api/update/flows'),
      ])
      const mirrorsData = await mirrorsResponse.json()
      const flowsData = await flowsResponse.json()
      mirrorOptions.value = mirrorsData.mirrors
      flowOptions.value = flowsData.flows
    } catch (error) {
      console.error('获取更新源列表失败：', error)
      mirrorOptions.value = [{ title: 'GitHub 官方', value: 'github' }]
      flowOptions.value = [
        { title: 'GitHub Release', value: 'github' },
        { title: '一图流 API (CN 镜像)', value: 'cn_yituliu' },
      ]
    }
  })

  return { mirrorOptions, flowOptions }
}
