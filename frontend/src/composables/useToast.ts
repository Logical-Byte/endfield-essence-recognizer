/**
 * 全局提示组合式函数。
 *
 * 提供一个应用级的消息队列，供任意组件与 composable 上报操作结果。
 * 失败必须让用户看见：把错误吞进 console 会让"保存失败"看起来和
 * "保存成功"一模一样，而这类差异往往要等到数据对不上时才被发现。
 */

import { readonly, ref } from 'vue'

export type ToastLevel = 'success' | 'info' | 'warning' | 'error'

export interface ToastMessage {
  id: number
  text: string
  level: ToastLevel
  /** 展示时长（毫秒）；错误默认停留更久，便于阅读 */
  timeout: number
}

const messages = ref<ToastMessage[]>([])
let nextId = 0

/** 同时最多堆叠的消息数，超出时丢弃最旧的一条 */
const MAX_STACK = 3

function push(text: string, level: ToastLevel, timeout?: number) {
  const message: ToastMessage = {
    id: nextId++,
    text,
    level,
    timeout: timeout ?? (level === 'error' ? 6000 : 3500),
  }
  messages.value = [...messages.value, message].slice(-MAX_STACK)
  return message.id
}

/** 从 unknown 中提取可读的错误文案 */
export function toErrorMessage(error: unknown, fallback = '操作失败'): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string' && error) return error
  return fallback
}

export function useToast() {
  return {
    messages: readonly(messages),

    success: (text: string, timeout?: number) => push(text, 'success', timeout),
    info: (text: string, timeout?: number) => push(text, 'info', timeout),
    warning: (text: string, timeout?: number) => push(text, 'warning', timeout),
    error: (text: string, timeout?: number) => push(text, 'error', timeout),

    /**
     * 上报一个异常，返回展示出来的文案。
     *
     * @param context 操作描述，例如「保存自定义基质」
     */
    reportError(context: string, error: unknown): string {
      const text = `${context}：${toErrorMessage(error)}`
      push(text, 'error')
      return text
    },

    dismiss(id: number) {
      messages.value = messages.value.filter((m) => m.id !== id)
    },

    /** 仅供测试使用：清空队列 */
    clear() {
      messages.value = []
      nextId = 0
    },
  }
}
