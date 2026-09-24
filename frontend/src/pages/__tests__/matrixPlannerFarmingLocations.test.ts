import { describe, expect, it, vi } from 'vitest'
import { computed, nextTick, ref, watch } from 'vue'

/**
 * 基质规划页「刷取地点筛选」：配置回填与用户落盘的区分。
 *
 * 页面把筛选状态拆成两个 watcher（回填 / 落盘），二者都会改动
 * selectedFarmingLocations，靠「当前勾选是否等于已保存配置推出的勾选」来区分
 * 用户意图。这个判据不显眼，且回填的赋值会让落盘 watcher 在之后的 flush 中
 * 才执行，容易在后续改动中被破坏成「回填即回写」（把已保存配置写坏、账号切换
 * 时串号），因此用本测试固定住行为。
 *
 * 项目未引入 @vue/test-utils 与 DOM 环境，这里用与 matrix-planner.vue 中两个
 * watcher 逐行同构的 harness 覆盖该逻辑；改动组件里这两段时请同步更新本文件。
 */
function buildHarness(initialOptions?: { battleId: string; battleName: string }[]) {
  const save = vi.fn()
  const defaultOptions = [
    { battleId: 'opt1', battleName: 'A' },
    { battleId: 'opt2', battleName: 'B' },
    { battleId: 'opt3', battleName: 'C' },
  ]
  const alluviumLocationOptions = ref(initialOptions ?? defaultOptions)
  const savedFarmingLocations = ref<Record<string, boolean>>({})
  const selectedFarmingLocations = ref<string[]>([])
  const farmingLocationFilterReady = ref(false)

  watch(
    [alluviumLocationOptions, savedFarmingLocations],
    ([options, saved]) => {
      if (options.length === 0) return
      const next = options
        .filter((option) => saved[option.battleId] ?? true)
        .map((option) => option.battleId)
      const current = selectedFarmingLocations.value.toSorted().join(',')
      if (next.toSorted().join(',') !== current) {
        selectedFarmingLocations.value = next
      }
      farmingLocationFilterReady.value = true
    },
    { immediate: true },
  )

  watch(
    selectedFarmingLocations,
    async (newValue, oldValue) => {
      if (!farmingLocationFilterReady.value) return
      const oldSorted = oldValue.toSorted().join(',')
      const newSorted = newValue.toSorted().join(',')
      if (oldSorted === newSorted) return

      const synced = alluviumLocationOptions.value
        .filter((option) => savedFarmingLocations.value[option.battleId] ?? true)
        .map((option) => option.battleId)
      if (synced.toSorted().join(',') === newSorted) return

      const locations: Record<string, boolean> = {}
      for (const option of alluviumLocationOptions.value) {
        locations[option.battleId] = newValue.includes(option.battleId)
      }
      save(locations)
    },
    { deep: true },
  )

  const noFarmingLocationSelected = computed(
    () => farmingLocationFilterReady.value && selectedFarmingLocations.value.length === 0,
  )

  return {
    save,
    alluviumLocationOptions,
    savedFarmingLocations,
    selectedFarmingLocations,
    farmingLocationFilterReady,
    noFarmingLocationSelected,
    /** 模拟用户点击 chip */
    clickChip(newSelection: string[]) {
      selectedFarmingLocations.value = [...newSelection]
    },
  }
}

describe('刷取地点筛选：回填与落盘的区分', () => {
  it('首次挂载默认全勾选，不落盘', async () => {
    const h = buildHarness()
    await nextTick()

    expect(h.selectedFarmingLocations.value).toEqual(['opt1', 'opt2', 'opt3'])
    expect(h.save).not.toHaveBeenCalled()
  })

  it('刷新页面：配置异步到达后回填，不落盘', async () => {
    const h = buildHarness()
    await nextTick()

    // fetchProfiles 返回：opt1 未勾选
    h.savedFarmingLocations.value = { opt1: false, opt2: true, opt3: true }
    await nextTick()

    expect(h.selectedFarmingLocations.value).toEqual(['opt2', 'opt3'])
    expect(h.save).not.toHaveBeenCalled()
  })

  it('配置再次变化（新增取消勾选）仍不落盘', async () => {
    const h = buildHarness()
    await nextTick()
    h.savedFarmingLocations.value = { opt1: false, opt2: true, opt3: true }
    await nextTick()

    h.savedFarmingLocations.value = { opt1: false, opt2: true, opt3: false }
    await nextTick()

    expect(h.selectedFarmingLocations.value).toEqual(['opt2'])
    expect(h.save).not.toHaveBeenCalled()
  })

  it('切换账号：用新账号配置回填，不落盘', async () => {
    const h = buildHarness()
    await nextTick()
    h.savedFarmingLocations.value = { opt1: false, opt2: true, opt3: true }
    await nextTick()

    // 切到另一个账号：全勾选
    h.savedFarmingLocations.value = { opt1: true, opt2: true, opt3: true }
    await nextTick()

    expect(h.selectedFarmingLocations.value).toEqual(['opt1', 'opt2', 'opt3'])
    expect(h.save).not.toHaveBeenCalled()
  })

  it('用户取消勾选后落盘，且发送全量 map', async () => {
    const h = buildHarness()
    await nextTick()

    h.clickChip(['opt2', 'opt3'])
    await nextTick()

    expect(h.save).toHaveBeenCalledTimes(1)
    expect(h.save).toHaveBeenCalledWith({ opt1: false, opt2: true, opt3: true })
  })

  it('回填之后用户改动依然落盘（基准已更新，不误判）', async () => {
    const h = buildHarness()
    await nextTick()
    h.savedFarmingLocations.value = { opt1: false, opt2: true, opt3: true }
    await nextTick()

    h.clickChip(['opt2'])
    await nextTick()

    expect(h.save).toHaveBeenCalledTimes(1)
    expect(h.save).toHaveBeenCalledWith({ opt1: false, opt2: true, opt3: false })
  })

  it('改回与已保存配置一致时不落盘（无实际变更）', async () => {
    const h = buildHarness()
    await nextTick()
    h.clickChip(['opt2', 'opt3'])
    await nextTick()
    h.save.mockClear()

    // 再改回初始的全勾选，与已保存配置一致 —— 无需回写
    h.clickChip(['opt1', 'opt2', 'opt3'])
    await nextTick()

    expect(h.save).not.toHaveBeenCalled()
  })

  it('全部取消勾选：落盘全 false 并给出提示', async () => {
    const h = buildHarness()
    await nextTick()

    h.clickChip([])
    await nextTick()

    expect(h.noFarmingLocationSelected.value).toBe(true)
    expect(h.save).toHaveBeenCalledWith({ opt1: false, opt2: false, opt3: false })
  })

  it('静态数据未就绪时不回填、不落盘', async () => {
    const h = buildHarness([])
    await nextTick()

    expect(h.farmingLocationFilterReady.value).toBe(false)
    expect(h.save).not.toHaveBeenCalled()
    expect(h.noFarmingLocationSelected.value).toBe(false)

    // 静态数据到达后正常回填
    h.alluviumLocationOptions.value = [
      { battleId: 'opt1', battleName: 'A' },
      { battleId: 'opt2', battleName: 'B' },
    ]
    await nextTick()

    expect(h.selectedFarmingLocations.value).toEqual(['opt1', 'opt2'])
    expect(h.farmingLocationFilterReady.value).toBe(true)
    expect(h.save).not.toHaveBeenCalled()
  })
})
