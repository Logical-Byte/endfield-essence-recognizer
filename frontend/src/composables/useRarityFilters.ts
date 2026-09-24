/**
 * 星级过滤器组合式函数。
 *
 * 从 profile 加载/保存武器星级过滤设置，并提供响应式的 selectedRarities ref。
 */

import { ref, watch } from 'vue'
import { useProfiles } from '@/composables/useProfiles'

export function useRarityFilters() {
  const { activeProfile, updateWeaponOverviewFilters } = useProfiles()

  const selectedRarities = ref<string[]>(['3', '4', '5', '6'])

  // 从 profile 加载过滤器设置
  watch(
    () => activeProfile.value.weapon_overview_filters,
    (filters) => {
      if (filters) {
        const newRarities: string[] = []
        if (filters['3star']) newRarities.push('3')
        if (filters['4star']) newRarities.push('4')
        if (filters['5star']) newRarities.push('5')
        if (filters['6star']) newRarities.push('6')
        if (filters['custom']) newRarities.push('custom')

        // 只有在实际不同时才更新，避免循环
        const current = selectedRarities.value.toSorted().join(',')
        const updated = newRarities.toSorted().join(',')
        if (current !== updated) {
          selectedRarities.value = newRarities
        }
      }
    },
    { immediate: true },
  )

  // 保存过滤器设置到 profile
  watch(
    selectedRarities,
    async (newValue, oldValue) => {
      // 避免初始化时触发
      if (!oldValue) return

      // 检查是否真的有变化
      const oldSorted = oldValue.toSorted().join(',')
      const newSorted = newValue.toSorted().join(',')
      if (oldSorted === newSorted) return

      try {
        await updateWeaponOverviewFilters({
          '3star': newValue.includes('3'),
          '4star': newValue.includes('4'),
          '5star': newValue.includes('5'),
          '6star': newValue.includes('6'),
          custom: newValue.includes('custom'),
        })
      } catch {
        // 错误已由 useProfiles 的 lastError 处理
      }
    },
    { deep: true },
  )

  return { selectedRarities }
}
