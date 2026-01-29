import { nextTick } from 'vue'

/**
 * 计算字体大小以适应容器宽度
 * @param element 需要调整字体大小的文本元素
 * @param containerWidth 容器宽度（像素）
 * @param minFontSize 最小字体大小（像素），默认 16
 * @param maxFontSize 最大字体大小（像素），默认 32
 * @returns {void}
 */
export function updateText(
  element: HTMLElement,
  containerWidth: number,
  minFontSize: number = 16,
  maxFontSize: number = 32,
): void {
  if (!element.textContent) return

  const currentOverflow = element.style.overflow
  const currentWhiteSpace = element.style.whiteSpace

  element.style.fontSize = `${maxFontSize}px`
  element.style.overflow = 'hidden'
  element.style.whiteSpace = 'nowrap'

  nextTick(() => {
    const elementWidth = element.scrollWidth
    if (elementWidth > containerWidth) {
      const newFontSize = Math.max((maxFontSize * containerWidth) / elementWidth, minFontSize)
      element.style.fontSize = `${newFontSize}px`
      console.log(
        `Adjusting ${element.textContent} font size from ${maxFontSize}px to ${newFontSize}px because element.scrollWidth (${elementWidth}px) > containerWidth (${containerWidth}px)`,
      )
    } else {
      console.log(`${element.textContent}: font size ${maxFontSize}`)
    }

    element.style.overflow = currentOverflow
    element.style.whiteSpace = currentWhiteSpace
  })
}
