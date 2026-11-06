/**
 * 日志行化工具。
 *
 * 后端经 WebSocket 推送的一条消息里可能合并了多行日志（批量发送，单批最多 32 行）。
 * 原先前端把整段日志拼成一个 HTML 字符串交给 `v-html`，每收到一条消息就要重建整份
 * 日志 DOM，开销随已累计日志量线性增长；叠加自动滚动的强制同步布局后，日志一多就会
 * 把 WebView2 渲染线程压满（见 issue #221）。
 *
 * 这里把一段带 ANSI 颜色的日志转成**逐行自闭合的 HTML 片段**，让每行可以单独渲染，
 * 每次更新只需要新增节点、不需要重建整份 DOM：
 *
 * 1. 先只对正文做 HTML 转义，ANSI 控制序列原样保留。这里不使用 ansi-to-html 的
 *    `escapeXML`，因为它会把每个中文字符转成 `&#xXXXX;` 实体，体积膨胀约 3 倍；
 * 2. 整段一次性转换，颜色状态因此能跨行延续，不会在换行处被截断；
 * 3. 按 `\n` 切开后，为每行补上行首仍然生效的开标签、行尾补上对应的闭合标签，
 *    使每行都是独立合法的 HTML。
 */
import Convert from 'ansi-to-html'

const ansiConverter = new Convert({
  fg: '#FFF',
  bg: '#000',
  newline: false,
  // 正文由 escapeLogText 预先转义，这里必须关掉，否则中文会被转成字符实体
  escapeXML: false,
  stream: false,
  colors: {
    4: '#49a4ff',
  },
})

/** ESC 控制符，用于把 ANSI 控制序列和正文分开。 */
const ESC = '\u001B'

/** 匹配一个完整的 ANSI CSI 控制序列。 */
const ANSI_SEQUENCE = new RegExp(String.raw`(${ESC}\[[0-9;?]*[a-zA-Z])`)

/** 匹配一个 HTML 标签，用于在按行切分时维护标签栈。 */
const HTML_TAG = /<\/?([a-zA-Z][^\s/>]*)[^>]*>/g

/** 空行占位符：零宽空格，保证空行也撑出一个行高，又不污染可见文本。 */
const EMPTY_LINE = '&#8203;'

/**
 * 转义日志正文中的 HTML 特殊字符，ANSI 控制序列保持原样。
 *
 * @param ansiText 后端推送的、带 ANSI 控制序列的原始日志文本
 * @returns 正文已转义、控制序列未改动的文本
 */
export function escapeLogText(ansiText: string): string {
  return ansiText
    .split(ANSI_SEQUENCE)
    .map((part) => {
      if (part.startsWith(`${ESC}[`)) {
        return part
      }
      return part.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    })
    .join('')
}

/**
 * 把一段日志 HTML 按换行切成逐行自闭合的片段。
 *
 * 颜色标签可能跨行（例如级别的颜色包住整条多行消息），切开后单独插进一行的容器里
 * 会被浏览器提前闭合、从第二行起丢颜色。因此这里维护一个标签栈：每行开头重新打开
 * 仍然生效的标签，行尾再补上闭合标签。
 *
 * @param html 已由 ansi-to-html 转换好的日志 HTML
 * @returns 每行一个可直接交给 `v-html` 的 HTML 片段
 */
export function splitHtmlLines(html: string): string[] {
  const rawLines = html.split('\n')
  // loguru 的每条记录都以换行结尾，切出来的最后一段空串不是一行日志
  if (rawLines.length > 0 && rawLines.at(-1) === '') {
    rawLines.pop()
  }

  // 两个数组始终保持同步：openNames 用于生成闭合标签，openTags 用于重新打开
  const openNames: string[] = []
  const openTags: string[] = []
  const lines: string[] = []

  for (const rawLine of rawLines) {
    // 换行符被当作行分隔后，残留的 \r 会被 HTML 解析器再次当成换行
    const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
    const prefix = openTags.join('')

    for (const tag of line.matchAll(HTML_TAG)) {
      const matched = tag[0]
      const name = (tag[1] ?? '').toLowerCase()
      if (!name) {
        continue
      }
      if (matched.startsWith('</')) {
        const index = openNames.lastIndexOf(name)
        if (index !== -1) {
          openNames.splice(index, 1)
          openTags.splice(index, 1)
        }
      } else if (!matched.endsWith('/>')) {
        openNames.push(name)
        openTags.push(matched)
      }
    }

    const suffix = openNames
      .map((name) => `</${name}>`)
      .toReversed()
      .join('')

    lines.push(prefix + (line === '' ? EMPTY_LINE : line) + suffix)
  }

  return lines
}

/**
 * 把后端推送的一段日志消息转成逐行的 HTML 片段。
 *
 * @param message 后端 WebSocket 推送的一条原始日志消息
 * @returns 每行一个可直接交给 `v-html` 的 HTML 片段
 */
export function ansiToHtmlLines(message: string): string[] {
  return splitHtmlLines(ansiConverter.toHtml(escapeLogText(message)))
}
