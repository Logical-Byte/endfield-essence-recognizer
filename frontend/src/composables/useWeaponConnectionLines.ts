/**
 * 武器连线系统组合式函数。
 *
 * 管理武器之间的属性连线显示。
 */

import { onUnmounted, ref } from 'vue'

export interface ConnectionLine {
  /** 目标武器 ID，用作列表 key，保证过渡动画作用在正确的元素上 */
  targetId: string
  style: {
    left: string
    top: string
    width: string
    transform: string
  }
}

export function useWeaponConnectionLines() {
  /** 容器引用 */
  const containerRef = ref<HTMLElement | null>(null)

  /** 当前悬停的武器 ID */
  const hoveredWeaponId = ref<string | null>(null)

  /** 连线数据 */
  const connectionLines = ref<ConnectionLine[]>([])

  /** 获取武器图标元素位置（容器与其矩形由调用方一次性提供，避免重复重排） */
  function getWeaponElementPosition(
    weaponId: string,
    container: HTMLElement,
    containerRect: DOMRect,
  ): { x: number; y: number } | null {
    const element = container.querySelector(`[data-weapon-id="${CSS.escape(weaponId)}"]`)
    if (!element) return null

    const elementRect = element.getBoundingClientRect()

    return {
      x: elementRect.left - containerRect.left + elementRect.width / 2,
      y: elementRect.top - containerRect.top + elementRect.height / 2,
    }
  }

  /** 计算两点之间的距离和角度 */
  function calculateLine(
    startX: number,
    startY: number,
    endX: number,
    endY: number,
  ): { length: number; angle: number } {
    const dx = endX - startX
    const dy = endY - startY
    const length = Math.hypot(dx, dy)
    const angle = Math.atan2(dy, dx) * (180 / Math.PI)
    return { length, angle }
  }

  /** 更新连线 */
  function updateConnectionLines(sameStatWeapons: string[]) {
    if (!hoveredWeaponId.value) {
      connectionLines.value = []
      return
    }

    const container = containerRef.value
    if (!container) {
      connectionLines.value = []
      return
    }

    // 一次性读完所有几何信息再计算：在循环里交替读写会反复触发强制重排，
    // 武器数量一多就是肉眼可见的卡顿。
    const containerRect = container.getBoundingClientRect()
    const startPos = getWeaponElementPosition(hoveredWeaponId.value, container, containerRect)
    if (!startPos) {
      connectionLines.value = []
      return
    }

    const endPositions: Array<{ targetId: string; x: number; y: number }> = []
    for (const targetId of sameStatWeapons) {
      const endPos = getWeaponElementPosition(targetId, container, containerRect)
      if (endPos) endPositions.push({ targetId, ...endPos })
    }

    connectionLines.value = endPositions.map((endPos) => {
      const { length, angle } = calculateLine(startPos.x, startPos.y, endPos.x, endPos.y)
      return {
        targetId: endPos.targetId,
        style: {
          left: `${startPos.x}px`,
          top: `${startPos.y}px`,
          width: `${length}px`,
          transform: `rotate(${angle}deg)`,
        },
      }
    })
  }

  /** 鼠标进入武器 */
  function handleWeaponMouseEnter(weaponId: string, sameStatWeapons: string[]) {
    hoveredWeaponId.value = weaponId
    updateConnectionLines(sameStatWeapons)
  }

  /** 鼠标离开武器 */
  function handleWeaponMouseLeave() {
    hoveredWeaponId.value = null
    connectionLines.value = []
  }

  // 监听窗口大小变化，更新连线位置
  let resizeHandler: (() => void) | null = null
  let resizeFrame: number | null = null

  function setupResizeListener(getSameStatWeapons: () => string[]) {
    // 重复调用时先解绑：直接覆盖 resizeHandler 会丢掉旧引用，
    // 旧监听器再也移除不掉，既泄漏又会重复执行。
    cleanupResizeListener()
    resizeHandler = () => {
      if (!hoveredWeaponId.value) return
      // resize 是高频事件，合并到下一帧执行，避免每个事件都触发一轮测量
      if (resizeFrame !== null) return
      resizeFrame = window.requestAnimationFrame(() => {
        resizeFrame = null
        if (hoveredWeaponId.value) {
          updateConnectionLines(getSameStatWeapons())
        }
      })
    }
    window.addEventListener('resize', resizeHandler)
  }

  function cleanupResizeListener() {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    if (resizeFrame !== null) {
      window.cancelAnimationFrame(resizeFrame)
      resizeFrame = null
    }
  }

  onUnmounted(() => {
    cleanupResizeListener()
    connectionLines.value = []
  })

  return {
    // 状态
    containerRef,
    hoveredWeaponId,
    connectionLines,

    // 方法
    updateConnectionLines,
    handleWeaponMouseEnter,
    handleWeaponMouseLeave,
    setupResizeListener,
    cleanupResizeListener,
  }
}
