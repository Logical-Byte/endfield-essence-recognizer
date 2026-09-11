/**
 * useProfiles 组合式函数测试。
 *
 * 通过 stub 全局 fetch 模拟后端接口，验证请求参数、状态更新与错误处理。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { __resetProfilesStateForTests, useProfiles } from '../useProfiles'
import { useToast } from '../useToast'

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
    default: {
      version: 1,
      name: 'default',
      treasure_matrix: [],
    },
  },
}

describe('useProfiles', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    // collection 是模块级单例，跨用例共享；不重置会让用例之间产生
    // 顺序依赖，新增测试时极易踩到。
    __resetProfilesStateForTests()
    useToast().clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchProfiles 成功时保存整份集合（含 default_profile）', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(COLLECTION))
    const { fetchProfiles, collection, isLoaded, defaultProfileName } = useProfiles()

    await fetchProfiles()

    expect(collection.value.active_profile).toBe('default')
    expect(collection.value.default_profile).toBe('default')
    expect(collection.value.profiles.default.name).toBe('default')
    expect(isLoaded.value).toBe(true)
    expect(defaultProfileName.value).toBe('default')
  })

  it('后端未返回 default_profile（旧版本）时回退为 default', async () => {
    const { active_profile, profiles, ...legacy } = COLLECTION
    void active_profile
    void profiles
    fetchMock.mockResolvedValueOnce(
      mockResponse({ ...legacy, active_profile: 'default', profiles: COLLECTION.profiles }),
    )
    const { fetchProfiles, defaultProfileName } = useProfiles()

    await fetchProfiles()

    expect(defaultProfileName.value).toBe('default')
  })

  it('switchProfile 发送 POST 请求体并重新拉取集合', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({ name: 'alt', version: 1, treasure_matrix: [] }))
      .mockResolvedValueOnce(
        mockResponse({
          ...COLLECTION,
          active_profile: 'alt',
          profiles: {
            ...COLLECTION.profiles,
            alt: { version: 1, name: 'alt', treasure_matrix: [] },
          },
        }),
      )
    const { switchProfile, activeProfileName, profileNames } = useProfiles()

    await switchProfile('alt')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/switch',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'alt' }),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/profiles')
    expect(activeProfileName.value).toBe('alt')
    expect(profileNames.value).toContain('alt')
  })

  it('renameProfile 发送重命名请求并重新拉取集合', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({ name: '新名', version: 1, treasure_matrix: [] }))
      .mockResolvedValueOnce(mockResponse(COLLECTION))
    const { renameProfile } = useProfiles()

    await renameProfile('default', '新名')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/rename',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ old_name: 'default', new_name: '新名' }),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/profiles')
  })

  it('deleteProfile 发送删除请求并重新拉取集合', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 'ok' })).mockResolvedValueOnce(
      mockResponse({
        ...COLLECTION,
        active_profile: 'default',
        profiles: COLLECTION.profiles,
      }),
    )
    const { deleteProfile } = useProfiles()

    await deleteProfile('alt')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/delete',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'alt' }),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/profiles')
  })

  it('接口失败时设置 lastError 并抛出异常', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse({ detail: '账号不存在' }, false, 400))
    const { fetchProfiles, lastError } = useProfiles()

    await expect(fetchProfiles()).rejects.toThrow('账号不存在')
    expect(lastError.value).toContain('账号不存在')
  })

  it('删除激活账号时乐观回退到默认账号，重拉失败也不残留', async () => {
    // 先加载含两个账号的集合
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        ...COLLECTION,
        active_profile: 'alt',
        profiles: {
          ...COLLECTION.profiles,
          alt: { version: 1, name: 'alt', treasure_matrix: [] },
        },
      }),
    )
    const { fetchProfiles, deleteProfile, activeProfileName, lastError } = useProfiles()
    await fetchProfiles()
    expect(activeProfileName.value).toBe('alt')

    // 删除成功，但随后重新拉取集合失败（网络抖动）
    fetchMock
      .mockResolvedValueOnce(mockResponse({ status: 'ok' }))
      .mockRejectedValueOnce(new Error('network down'))

    await expect(deleteProfile('alt')).rejects.toThrow()

    // 本地 active_profile 已乐观回退到默认账号，不会指向已删除的账号
    expect(activeProfileName.value).toBe('default')
    expect(lastError.value).toContain('network down')
  })

  it('删除非激活账号时不做乐观回退，保持当前激活账号', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse({ status: 'ok' }))
      .mockResolvedValueOnce(mockResponse(COLLECTION))
    const { deleteProfile, activeProfileName } = useProfiles()

    await deleteProfile('other')

    expect(activeProfileName.value).toBe('default')
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/profiles')
  })

  it('clearProfileData 不带 name 时清空当前激活账号并重新拉取集合', async () => {
    fetchMock
      .mockResolvedValueOnce(
        mockResponse({
          version: 1,
          name: 'default',
          treasure_matrix: [],
          weapon_priorities: {},
        }),
      )
      .mockResolvedValueOnce(mockResponse(COLLECTION))
    const { clearProfileData } = useProfiles()

    await clearProfileData()

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/clear_data',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({}),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/profiles')
  })

  it('clearProfileData 带 name 时清空指定账号', async () => {
    fetchMock
      .mockResolvedValueOnce(
        mockResponse({
          version: 1,
          name: 'alt',
          treasure_matrix: [],
          weapon_priorities: {},
        }),
      )
      .mockResolvedValueOnce(mockResponse(COLLECTION))
    const { clearProfileData } = useProfiles()

    await clearProfileData('alt')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/clear_data',
      expect.objectContaining({
        body: JSON.stringify({ name: 'alt' }),
      }),
    )
  })

  it('updateSwitchDisplayMode 发送模式并更新本地账号快照', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        version: 1,
        name: 'default',
        treasure_matrix: [],
        switch_display_mode: 'dot',
      }),
    )
    const { updateSwitchDisplayMode, activeProfile } = useProfiles()

    await updateSwitchDisplayMode('dot')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/switch_display_mode',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ mode: 'dot' }),
      }),
    )
    expect(activeProfile.value.switch_display_mode).toBe('dot')
  })

  it('updateMatrixBadgeDisplayMode 发送模式并更新本地账号快照', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        version: 1,
        name: 'default',
        treasure_matrix: [],
        matrix_badge_display_mode: 'medium',
      }),
    )
    const { updateMatrixBadgeDisplayMode, activeProfile } = useProfiles()

    await updateMatrixBadgeDisplayMode('medium')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/matrix_badge_display_mode',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ mode: 'medium' }),
      }),
    )
    expect(activeProfile.value.matrix_badge_display_mode).toBe('medium')
  })

  it('updateMatrixPlannerFarmingLocations 发送地点筛选并更新本地账号快照', async () => {
    const locations = {
      world_energy_point_group01: true,
      world_energy_point_group02: false,
    }
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        version: 1,
        name: 'default',
        treasure_matrix: [],
        matrix_planner_farming_locations: locations,
      }),
    )
    const { updateMatrixPlannerFarmingLocations, activeProfile } = useProfiles()

    await updateMatrixPlannerFarmingLocations(locations)

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/profiles/matrix_planner_farming_locations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ locations }),
      }),
    )
    expect(activeProfile.value.matrix_planner_farming_locations).toEqual(locations)
  })

  it('写操作接口返回 ProfileData 时直接更新本地快照，不重复拉取', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        version: 1,
        name: 'default',
        treasure_matrix: [
          {
            weapon_id: 'wpn_001',
            weapon_name: 'W1',
            affix1_level: 3,
            affix2_level: 3,
            affix3_level: 2,
          },
        ],
      }),
    )
    const { addTreasureMatrixEntry, treasureMatrix } = useProfiles()

    await addTreasureMatrixEntry({
      weapon_id: 'wpn_001',
      weapon_name: 'W1',
      affix1_level: 3,
      affix2_level: 3,
      affix3_level: 2,
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(treasureMatrix.value).toHaveLength(1)
    expect(treasureMatrix.value[0].weapon_id).toBe('wpn_001')
  })
})
