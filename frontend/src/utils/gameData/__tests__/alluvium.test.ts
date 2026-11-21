/**
 * 自定义能量淤积点标识工具测试。
 *
 * battleId 前缀是前后端之间的约定：前端按它生成筛选键，后端按它区分自定义
 * 地点与内置地点。前缀写错不会报错，只会让自定义地点在各账号里静默失去
 * 勾选状态，因此逐条锁定行为。
 */

import { describe, expect, it } from 'vitest'
import {
  createCustomAlluviumId,
  CUSTOM_ALLUVIUM_ID_PREFIX,
  fallbackCustomAlluviumName,
  isCustomAlluviumId,
  toCustomAlluviumId,
} from '../alluvium'

describe('isCustomAlluviumId', () => {
  it('识别自定义地点', () => {
    expect(isCustomAlluviumId('custom_alluvium:abc')).toBe(true)
  })

  it('内置地点与空值返回 false', () => {
    expect(isCustomAlluviumId('world_energy_point_group01')).toBe(false)
    expect(isCustomAlluviumId(null)).toBe(false)
    expect(isCustomAlluviumId(undefined)).toBe(false)
    expect(isCustomAlluviumId('')).toBe(false)
  })

  it('不会把自定义基质的 ID 误判成自定义地点', () => {
    expect(isCustomAlluviumId('custom:abc')).toBe(false)
  })
})

describe('toCustomAlluviumId', () => {
  it('拼接后能被识别回自定义地点', () => {
    const battleId = toCustomAlluviumId({ id: 'abc' })
    expect(battleId).toBe(`${CUSTOM_ALLUVIUM_ID_PREFIX}abc`)
    expect(isCustomAlluviumId(battleId)).toBe(true)
  })
})

describe('createCustomAlluviumId', () => {
  it('生成唯一的非空 ID', () => {
    const ids = new Set(Array.from({ length: 50 }, () => createCustomAlluviumId()))
    expect(ids.size).toBe(50)
    expect([...ids].every((id) => id.length > 0)).toBe(true)
  })
})

describe('fallbackCustomAlluviumName', () => {
  it('按下标生成 1 起算的兜底名', () => {
    expect(fallbackCustomAlluviumName(0)).toBe('自定义淤积点 1')
    expect(fallbackCustomAlluviumName(4)).toBe('自定义淤积点 5')
  })
})
