import { describe, expect, it } from 'vitest'
import { ansiToHtmlLines, escapeLogText, splitHtmlLines } from '@/utils/logLines'

const ESC = '\u001B['
const GREEN = `${ESC}32m`
const BOLD = `${ESC}1m`
const RESET = `${ESC}0m`

describe('escapeLogText', () => {
  it('转义正文里的尖括号与 &', () => {
    expect(escapeLogText('<Queue at 0x1> & more')).toBe('&lt;Queue at 0x1&gt; &amp; more')
  })

  it('不动 ANSI 控制序列', () => {
    expect(escapeLogText(`${GREEN}宝藏${RESET}`)).toBe(`${GREEN}宝藏${RESET}`)
  })

  it('中文字符保持原样，不转成字符实体', () => {
    expect(escapeLogText(`${GREEN}中文日志${RESET}`)).toContain('中文日志')
  })
})

describe('splitHtmlLines', () => {
  it('去掉 loguru 记录末尾换行产生的空行', () => {
    expect(splitHtmlLines('第一行\n')).toEqual(['第一行'])
    expect(splitHtmlLines('第一行\n第二行\n')).toEqual(['第一行', '第二行'])
  })

  it('跨行颜色在每一行都保留，不被截断', () => {
    // 等价于 loguru 的 <green>第一行<换行>第二行</>
    const lines = splitHtmlLines('<span style="color:#0A0">第一行\n第二行</span>')
    expect(lines).toHaveLength(2)
    // 第一行在行尾补闭合，第二行在行首重新打开同名标签
    expect(lines[0]).toBe('<span style="color:#0A0">第一行</span>')
    expect(lines[1]).toBe('<span style="color:#0A0">第二行</span>')
  })

  it('嵌套标签跨行时按栈序重新打开与闭合', () => {
    const lines = splitHtmlLines('<b><u>粗体\n下划线</u></b>')
    expect(lines).toEqual(['<b><u>粗体</u></b>', '<b><u>下划线</u></b>'])
  })

  it('行内自行闭合的标签不会带到下一行', () => {
    const lines = splitHtmlLines('<b>粗体</b>\n普通')
    expect(lines).toEqual(['<b>粗体</b>', '普通'])
  })

  it('空行用零宽空格占位，保证占一个行高', () => {
    expect(splitHtmlLines('第一行\n\n第三行')).toEqual(['第一行', '&#8203;', '第三行'])
  })

  it('颜色块内的空行仍然保留颜色标签', () => {
    expect(splitHtmlLines('<span style="color:#0A0">上\n\n下</span>')[1]).toBe(
      '<span style="color:#0A0">&#8203;</span>',
    )
  })
})

describe('ansiToHtmlLines', () => {
  it('把一条多行彩色日志切成每行一个自闭合片段', () => {
    const message = `${GREEN}${BOLD}10-16 20:35:00${RESET} [${GREEN}INFO${RESET}] ${GREEN}第一行\n第二行${RESET}\n`
    const lines = ansiToHtmlLines(message)

    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain('10-16 20:35:00')
    expect(lines[0]).toContain('INFO')
    expect(lines[0]).toContain('第一行')
    expect(lines[1]).toContain('第二行')
    // 跨行的绿色在第二行依然生效
    expect(lines[1]).toContain('<span style="color:#0A0">')
    // 每一行都自闭合
    for (const line of lines) {
      expect(line.split('<span').length).toBe(line.split('</span>').length)
    }
  })

  it('日志正文里的尖括号不会变成真标签', () => {
    const [line] = ansiToHtmlLines(`${GREEN}<Queue at 0x1 maxsize=0>${RESET}\n`)
    expect(line).toBe('<span style="color:#0A0">&lt;Queue at 0x1 maxsize=0&gt;</span>')
  })

  it('空消息不产生任何行', () => {
    expect(ansiToHtmlLines('')).toEqual([])
  })

  it('后端批量拼接的多条记录不会互相串色', () => {
    // 后端把同一批记录直接首尾相连后推送，每条记录都以颜色复位 + 换行结尾
    const record = (text: string) =>
      `10-16 20:35:00 [${GREEN}INFO${RESET}] ${GREEN}${text}${RESET}\n`
    const lines = ansiToHtmlLines(record('第一条') + record('第二条'))

    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain('第一条')
    expect(lines[1]).toContain('第二条')
    // 前一条记录已经复位，后一条不应继承任何标签：自己的两个 span 之外不该多出来
    expect(lines[1].startsWith('<span')).toBe(false)
    expect(lines[1].split('<span')).toHaveLength(3)
  })
})
