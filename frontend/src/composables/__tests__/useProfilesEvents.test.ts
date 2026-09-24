/**
 * useProfilesEvents 组合式函数测试。
 *
 * 通过 stub 全局 WebSocket / fetch / window，验证挂载连接、收到
 * profiles_changed 事件后刷新 profiles 数据、卸载断开。
 */

import type * as Vue from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let mountedCb: (() => void) | null = null
let unmountedCb: (() => void) | null = null

vi.mock('vue', async (importOriginal) => {
  const actual = (await importOriginal()) as typeof Vue
  return {
    ...actual,
    onMounted: (cb: () => void) => {
      mountedCb = cb
    },
    onBeforeUnmount: (cb: () => void) => {
      unmountedCb = cb
    },
  }
})

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  private listeners: Record<string, Array<(event?: unknown) => void>> = {}

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  addEventListener(type: string, cb: (event?: unknown) => void) {
    ;(this.listeners[type] ??= []).push(cb)
  }

  emit(type: string, event?: unknown) {
    const callbacks = this.listeners[type]
    if (!callbacks) return
    for (const cb of callbacks) cb(event)
  }

  close() {
    this.emit('close')
  }
}

function mockResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response
}

const COLLECTION = {
  version: 1,
  active_profile: 'default',
  default_profile: 'default',
  profiles: {
    default: { version: 1, name: 'default', treasure_matrix: [] },
  },
}

describe('useProfilesEvents', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.resetModules()
    mountedCb = null
    unmountedCb = null
    MockWebSocket.instances = []
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('window', {
      location: { protocol: 'http:', host: 'localhost:8000' },
      setTimeout,
      clearTimeout,
    })
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('挂载后连接 /ws/events', async () => {
    const { useProfilesEvents } = await import('../useProfilesEvents')
    useProfilesEvents()
    mountedCb?.()

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toBe('ws://localhost:8000/ws/events')
  })

  it('收到 profiles_changed 事件后刷新 profiles 数据', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(COLLECTION))
    const { useProfilesEvents } = await import('../useProfilesEvents')
    useProfilesEvents()
    mountedCb?.()

    const ws = MockWebSocket.instances[0]
    ws.emit('message', { data: JSON.stringify({ type: 'profiles_changed' }) })

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/profiles')
    })
  })

  it('收到其他类型事件时不刷新', async () => {
    const { useProfilesEvents } = await import('../useProfilesEvents')
    useProfilesEvents()
    mountedCb?.()

    const ws = MockWebSocket.instances[0]
    ws.emit('message', { data: JSON.stringify({ type: 'other_event' }) })

    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('卸载时关闭连接', async () => {
    const { useProfilesEvents } = await import('../useProfilesEvents')
    useProfilesEvents()
    mountedCb?.()

    const ws = MockWebSocket.instances[0]
    const closeSpy = vi.spyOn(ws, 'close')

    unmountedCb?.()

    expect(closeSpy).toHaveBeenCalled()
  })
})
