/**
 * 自定义淤积点状态维护的测试。
 *
 * 列表 GET 与保存 / 删除会同时存在：保存成功后状态直接以 POST 返回的完整列表为准，
 * 因此一次在保存前发出、保存后才返回的 GET 不能把结果盖回去，否则刚保存的地点会
 * 从弹窗和规划器里消失（删除则相反，会「复活」已删除的地点）。
 */

import type { CustomAlluvium } from '@/utils/gameData/alluvium'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCustomAlluviums } from '@/composables/useCustomAlluviums'
import { useToast } from '@/composables/useToast'

/** 构造一个成功的 JSON 响应 */
function jsonResponse(body: CustomAlluvium[]): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response
}

/** 手动控制的闸门，用于让某个请求停在「已发出、未返回」状态 */
function createGate() {
  let release = () => {}
  const wait = new Promise<void>((resolve) => {
    release = resolve
  })
  return { wait, release: () => release() }
}

describe('useCustomAlluviums', () => {
  beforeEach(() => {
    useCustomAlluviums().customAlluviums.value = []
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('保存前发出的列表请求不会覆盖保存结果', async () => {
    const gate = createGate()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === 'POST') return jsonResponse([{ id: 'new', name: '新地点' }])
        // 列表请求先挂起，模拟「保存先完成、列表后返回」
        await gate.wait
        return jsonResponse([{ id: 'stale', name: '旧快照' }])
      }),
    )

    const { customAlluviums, fetchCustomAlluviums, saveCustomAlluvium } = useCustomAlluviums()

    const pendingFetch = fetchCustomAlluviums()
    await saveCustomAlluvium({ id: '', name: '新地点' })
    expect(customAlluviums.value.map((item) => item.id)).toEqual(['new'])

    gate.release()
    await pendingFetch
    expect(customAlluviums.value.map((item) => item.id)).toEqual(['new'])
  })

  it('删除前发出的列表请求不会复活已删除的地点', async () => {
    const gate = createGate()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === 'POST') return jsonResponse([])
        await gate.wait
        return jsonResponse([{ id: 'deleted', name: '已删除的地点' }])
      }),
    )

    const { customAlluviums, fetchCustomAlluviums, deleteCustomAlluvium } = useCustomAlluviums()

    const pendingFetch = fetchCustomAlluviums()
    await deleteCustomAlluvium('deleted')
    expect(customAlluviums.value).toEqual([])

    gate.release()
    await pendingFetch
    expect(customAlluviums.value).toEqual([])
  })

  it('先发起的列表请求结果不覆盖后发起的那次', async () => {
    const firstGate = createGate()
    let callIndex = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        callIndex += 1
        if (callIndex === 1) {
          await firstGate.wait
          return jsonResponse([{ id: 'first', name: '先发出的快照' }])
        }
        return jsonResponse([{ id: 'second', name: '后发出的快照' }])
      }),
    )

    const { customAlluviums, fetchCustomAlluviums } = useCustomAlluviums()

    const firstFetch = fetchCustomAlluviums()
    await fetchCustomAlluviums()
    expect(customAlluviums.value.map((item) => item.id)).toEqual(['second'])

    firstGate.release()
    await firstFetch
    expect(customAlluviums.value.map((item) => item.id)).toEqual(['second'])
  })

  it('保存之后新发起的列表请求仍然生效', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method === 'POST') return jsonResponse([{ id: 'saved', name: '刚保存的' }])
        return jsonResponse([
          { id: 'saved', name: '刚保存的' },
          { id: 'other', name: '手工新增' },
        ])
      }),
    )

    const { customAlluviums, fetchCustomAlluviums, saveCustomAlluvium } = useCustomAlluviums()

    await saveCustomAlluvium({ id: '', name: '刚保存的' })
    await fetchCustomAlluviums()

    expect(customAlluviums.value.map((item) => item.id)).toEqual(['saved', 'other'])
  })

  it('拉取失败时给出可见提示，而不是把它当成「没有自定义地点」', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({ ok: false, status: 500, statusText: 'Internal Server Error' }) as unknown as Response,
      ),
    )

    await useCustomAlluviums().fetchCustomAlluviums()

    expect(useToast().messages.value.some((message) => message.level === 'error')).toBe(true)
    consoleError.mockRestore()
  })
})
