<template>
  <v-expansion-panel value="武器总览">
    <v-expansion-panel-title>
      <v-icon class="mr-2">mdi-sword-cross</v-icon>
      武器总览
      <v-chip class="ml-2" color="success" size="small" variant="flat">
        {{ countText }}
      </v-chip>
    </v-expansion-panel-title>
    <v-expansion-panel-text>
      <v-alert border="start" class="mb-4" type="info" variant="tonal">
        左键点击武器图标查看基质属性，右键点击切换是否拥有该武器的基质。已满级（6/6/3）的武器会显示彩虹边框。鼠标悬停在有相同属性的武器上会显示粒子连线。
      </v-alert>

      <!-- 星级过滤开关 -->
      <div class="d-flex align-center gap-2 mb-4">
        <span class="text-body-2 text-medium-emphasis">显示星级：</span>
        <v-chip-group v-model="selectedRarities" column multiple>
          <v-chip color="primary" filter size="small" value="3" variant="outlined"> 3★ </v-chip>
          <v-chip color="primary" filter size="small" value="4" variant="outlined"> 4★ </v-chip>
          <v-chip color="primary" filter size="small" value="5" variant="outlined"> 5★ </v-chip>
          <v-chip color="primary" filter size="small" value="6" variant="outlined"> 6★ </v-chip>
          <v-chip color="primary" filter size="small" value="custom" variant="outlined">
            自定义
          </v-chip>
        </v-chip-group>
      </div>

      <!-- 自定义基质重合检测按钮 + 可切换提示模式 + 基质图标显示模式 -->
      <div class="d-flex align-center ga-2 mb-4">
        <v-btn
          color="warning"
          prepend-icon="mdi-swap-horizontal"
          size="small"
          variant="tonal"
          @click="checkCustomOverlap"
        >
          检查自定义基质重合
        </v-btn>
        <v-btn
          :prepend-icon="matrixBadgeModeIcons[matrixBadgeDisplayMode]"
          size="small"
          variant="tonal"
          @click="toggleMatrixBadgeDisplayMode"
        >
          {{ matrixBadgeModeLabels[matrixBadgeDisplayMode] }}
        </v-btn>
        <v-btn
          :prepend-icon="switchModeIcons[switchDisplayMode]"
          size="small"
          variant="tonal"
          @click="toggleSwitchDisplayMode"
        >
          {{ switchModeLabels[switchDisplayMode] }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-image-outline"
          size="small"
          variant="tonal"
          @click="showExportDialog = true"
        >
          导出为图片
        </v-btn>
      </div>

      <!-- 武器总览容器（包含连线层） -->
      <div ref="containerRef" class="weapon-overview-container">
        <!-- 连线层 -->
        <div class="connection-lines-layer">
          <transition-group name="connection-line">
            <div
              v-for="line in connectionLines"
              :key="line.targetId"
              class="connection-line"
              :style="line.style"
            />
          </transition-group>
        </div>

        <!-- 自定义基质区段 -->
        <template v-if="showCustomSection">
          <div class="d-flex align-center mb-1 mt-3">
            <span class="essence-icon-stack me-2">
              <img v-if="essenceBgSrc" alt="" :src="essenceBgSrc" />
              <img v-if="defaultIconSrc" alt="" :src="defaultIconSrc" />
            </span>
            <h4>自定义基质</h4>
          </div>
          <div class="weapon-overview-grid">
            <!-- [+] 新建按钮 -->
            <div
              aria-label="新建自定义基质"
              class="weapon-overview-item"
              role="button"
              tabindex="0"
              @click="showNewCustomDialog"
              @keydown.enter="showNewCustomDialog"
              @keydown.space.prevent="showNewCustomDialog"
            >
              <div class="weapon-add-button">
                <v-icon color="grey" size="28">mdi-plus</v-icon>
              </div>
            </div>
            <div
              v-for="entry in customMatrixEntries"
              :key="entry.syntheticId"
              class="weapon-overview-item"
              :data-weapon-id="entry.syntheticId"
              @click="showWeaponDetail(entry.syntheticId)"
              @contextmenu.prevent="toggleWeaponOwnership(entry.syntheticId)"
              @mouseenter="handleWeaponMouseEnter(entry.syntheticId)"
              @mouseleave="handleWeaponMouseLeave"
            >
              <!-- 武器悬浮面板：显示自定义基质的三条属性 -->
              <v-tooltip location="top" open-delay="0">
                <template #activator="{ props }">
                  <div v-bind="props" class="h-100">
                    <div
                      class="weapon-icon-wrapper"
                      :class="{
                        'weapon-not-owned': !isWeaponOwned(entry.syntheticId),
                        'weapon-maxed': isWeaponMaxed(entry.syntheticId),
                      }"
                    >
                      <custom-stat-icon
                        :name="entry.displayName"
                        :skill-stat-id="entry.skillStatId"
                      />

                      <!-- 满级的彩虹边框 -->
                      <div v-if="isWeaponMaxed(entry.syntheticId)" class="rainbow-border" />
                    </div>
                  </div>
                </template>
                <span>{{ getWeaponStatsText(entry.syntheticId) }}</span>
              </v-tooltip>
            </div>
          </div>
        </template>

        <template v-for="wType in filteredWeaponTypes" :key="wType.id">
          <div class="d-flex align-center mb-1 mt-3">
            <img :alt="wType.name" class="group-icon me-2" :src="wType.iconUrl" />
            <h4>{{ wType.name }}</h4>
          </div>
          <div class="weapon-overview-grid">
            <div
              v-for="weapon in wType.weapons"
              :key="weapon.id"
              class="weapon-overview-item"
              :data-weapon-id="weapon.id"
              @click="showWeaponDetail(weapon.id)"
              @contextmenu.prevent="toggleWeaponOwnership(weapon.id)"
              @mouseenter="handleWeaponMouseEnter(weapon.id)"
              @mouseleave="handleWeaponMouseLeave"
            >
              <!-- 武器悬浮面板：显示武器的三条基质属性 -->
              <v-tooltip location="top" open-delay="0">
                <template #activator="{ props }">
                  <div v-bind="props" class="h-100">
                    <div
                      class="weapon-icon-wrapper"
                      :class="{
                        'weapon-not-owned': !weapon.owned,
                        'weapon-maxed': weapon.maxed,
                        'switch-target-maxed': weapon.switchTargetMaxed,
                      }"
                    >
                      <item-icon :item-id="weapon.id" show-item-name />

                      <!-- 左上角：缩小版圆形基质图标（底板+技能属性叠加） -->
                      <div
                        v-if="matrixBadgeDisplayMode !== 'off'"
                        class="weapon-matrix-badge"
                        :class="{
                          'weapon-matrix-badge--medium': matrixBadgeDisplayMode === 'medium',
                        }"
                      >
                        <img
                          v-if="essenceBgSrc"
                          alt=""
                          class="weapon-matrix-badge-bg"
                          :src="essenceBgSrc"
                        />
                        <img
                          v-if="weapon.skillIcon"
                          alt=""
                          class="weapon-matrix-badge-skill"
                          :src="weapon.skillIcon"
                        />
                      </div>

                      <!-- 满级的彩虹边框 -->
                      <div v-if="weapon.maxed" class="rainbow-border" />
                    </div>
                  </div>
                </template>
                <span>{{ weapon.statsText }}</span>
              </v-tooltip>

              <!-- 可切换标记：根据模式显示标签/圆点/关闭 -->
              <v-chip
                v-if="switchDisplayMode === 'chip' && weapon.showSwitchHint"
                class="switchable-badge"
                color="warning"
                size="x-small"
                variant="flat"
              >
                可切换
              </v-chip>
              <div
                v-else-if="switchDisplayMode === 'dot' && weapon.showSwitchHint"
                class="switch-dot"
              />
            </div>
          </div>
        </template>
      </div>
    </v-expansion-panel-text>
  </v-expansion-panel>

  <!-- 武器详情弹窗（含删除确认弹窗） -->
  <weapon-detail-dialog v-model:weapon-id="detailWeaponId" />

  <!-- 自定义基质重合检测弹窗 -->
  <overlap-detection-dialog />

  <!-- 宝藏基质导出弹窗 -->
  <matrix-export-dialog v-model="showExportDialog" />
</template>

<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue'
import CustomStatIcon from '@/components/CustomStatIcon.vue'
import ItemIcon from '@/components/ItemIcon.vue'
import MatrixExportDialog from '@/components/MatrixExportDialog.vue'
import OverlapDetectionDialog from '@/components/OverlapDetectionDialog.vue'
import WeaponDetailDialog from '@/components/WeaponDetailDialog.vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useOverlapDetection } from '@/composables/useOverlapDetection'
import { useProfiles } from '@/composables/useProfiles'
import { useRarityFilters } from '@/composables/useRarityFilters'
import { useToast } from '@/composables/useToast'
import { useWeaponConnectionLines } from '@/composables/useWeaponConnectionLines'
import { useWeaponStats } from '@/composables/useWeaponStats'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  buildStatKey,
  findCustomStat,
  getGemTagName,
  getStatsForWeapon,
  toCustomStatId,
} from '@/utils/gameData/weapon'

const { weaponTypes, weaponsMap, matrixIcons, isLoaded: isStaticDataLoaded } = useStaticData()
const toast = useToast()
const { activeProfile, updateSwitchDisplayMode, updateMatrixBadgeDisplayMode } = useProfiles()
const { selectedRarities } = useRarityFilters()

// 使用 composables
const {
  matrixEntryByWeaponId,
  ownedWeaponIds,
  isWeaponOwned,
  isWeaponMaxed,
  isCustomEntry,
  getSameStatWeapons,
  isSwitchable,
  isSwitchTargetMaxed,
} = useWeaponStats()

const { customStats, customMatrixEntries, fetchCustomStats, toggleWeaponOwnership } =
  useCustomStats()

const { checkCustomOverlap: checkCustomOverlapBase } = useOverlapDetection()

const {
  containerRef,
  connectionLines,
  hoveredWeaponId,
  handleWeaponMouseEnter: handleWeaponMouseEnterBase,
  handleWeaponMouseLeave,
  setupResizeListener,
} = useWeaponConnectionLines()

// 可切换提示显示模式：'chip'=大号提示(默认), 'dot'=小橙点, 'off'=关闭
type SwitchDisplayMode = 'chip' | 'dot' | 'off'
const switchDisplayMode = ref<SwitchDisplayMode>(
  (activeProfile.value.switch_display_mode ?? 'chip') as SwitchDisplayMode,
)
const switchModeLabels: Record<SwitchDisplayMode, string> = {
  chip: '切换提示：标签',
  dot: '切换提示：圆点',
  off: '切换提示：关闭',
}
const switchModeIcons: Record<SwitchDisplayMode, string> = {
  chip: 'mdi-tag-outline',
  dot: 'mdi-circle-small',
  off: 'mdi-eye-off-outline',
}
function toggleSwitchDisplayMode() {
  const next: SwitchDisplayMode =
    switchDisplayMode.value === 'chip' ? 'dot' : switchDisplayMode.value === 'dot' ? 'off' : 'chip'
  const previous = switchDisplayMode.value
  switchDisplayMode.value = next
  updateSwitchDisplayMode(next).catch(() => {
    // 保存失败要退回原值，否则界面显示的模式与实际持久化的不一致，
    // 下次进入页面又会莫名其妙地变回去。
    // toast 已由 _handleError 统一弹出，此处不再重复。
    switchDisplayMode.value = previous
  })
}

// 切换账号时同步显示模式
watch(
  () => activeProfile.value.switch_display_mode,
  (mode) => {
    if (mode && mode !== switchDisplayMode.value) {
      switchDisplayMode.value = mode
    }
  },
)

// 基质图标显示模式：'small'=小号(默认), 'medium'=中号(2倍), 'off'=关闭
type MatrixBadgeDisplayMode = 'small' | 'medium' | 'off'
const matrixBadgeDisplayMode = ref<MatrixBadgeDisplayMode>(
  (activeProfile.value.matrix_badge_display_mode ?? 'small') as MatrixBadgeDisplayMode,
)
const matrixBadgeModeLabels: Record<MatrixBadgeDisplayMode, string> = {
  small: '基质图标：小号',
  medium: '基质图标：中号',
  off: '基质图标：关闭',
}
const matrixBadgeModeIcons: Record<MatrixBadgeDisplayMode, string> = {
  small: 'mdi-circle-outline',
  medium: 'mdi-circle-double',
  off: 'mdi-eye-off-outline',
}
function toggleMatrixBadgeDisplayMode() {
  const next: MatrixBadgeDisplayMode =
    matrixBadgeDisplayMode.value === 'small'
      ? 'medium'
      : matrixBadgeDisplayMode.value === 'medium'
        ? 'off'
        : 'small'
  const previous = matrixBadgeDisplayMode.value
  matrixBadgeDisplayMode.value = next
  updateMatrixBadgeDisplayMode(next).catch(() => {
    // toast 已由 _handleError 统一弹出，此处不再重复。
    matrixBadgeDisplayMode.value = previous
  })
}

// 切换账号时同步基质图标显示模式
watch(
  () => activeProfile.value.matrix_badge_display_mode,
  (mode) => {
    if (mode && mode !== matrixBadgeDisplayMode.value) {
      matrixBadgeDisplayMode.value = mode
    }
  },
)

// 底板图片路径
const essenceBgSrc = computed(() => matrixIcons.value.essenceBg)
// 默认基质图标路径（叠加在底板上）
const defaultIconSrc = computed(() => matrixIcons.value.defaultIcon)

// --- 武器卡片辅助函数 ---

/** 获取武器的技能属性图标 URL；属性缺失或未匹配时兜底返回默认基质图标 */
function getWeaponSkillIcon(weaponId: string): string | null {
  const fallback = matrixIcons.value.defaultIcon || null
  const found = findCustomStat(weaponId, customStats.value)
  if (found) {
    if (!found.stat.skill) return fallback
    return matrixIcons.value.skills[found.stat.skill] || fallback
  }
  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon?.skillStatId) return fallback
  return matrixIcons.value.skills[weapon.skillStatId] || fallback
}

// 武器详情弹窗（null=关闭，string=打开编辑该武器）
const detailWeaponId = ref<string | null>(null)

// 导出为图片弹窗
const showExportDialog = ref(false)

/**
 * 计算指定武器的属性组合键。
 *
 * 自定义条目从配置读取（attribute/secondary/skill），内置武器从静态数据
 * 读取（attributeStatId/secondaryStatId/skillStatId），两类共用 buildStatKey
 * 生成的同一格式，才能互相匹配。
 */
function getWeaponStatKey(weaponId: string): string {
  const found = findCustomStat(weaponId, customStats.value)
  if (found) {
    return buildStatKey(found.stat.attribute, found.stat.secondary, found.stat.skill)
  }
  const stats = getStatsForWeapon(weaponId)
  return buildStatKey(stats.attribute, stats.secondary, stats.skill)
}

/**
 * 计算与指定武器属性组合相同的内置武器 ID 列表（不含自身）。
 *
 * 内置武器之间的匹配走 getSameStatWeapons（useWeaponStats 的索引）；
 * 自定义基质没有被该索引收录，需要按属性组合键扫描 weaponsMap 补齐。
 */
function getSameStatBuiltinWeaponIds(weaponId: string): string[] {
  if (!isCustomEntry(weaponId)) return getSameStatWeapons(weaponId)
  const key = getWeaponStatKey(weaponId)
  const matches: string[] = []
  for (const [id, weapon] of weaponsMap.value.entries()) {
    if (buildStatKey(weapon.attributeStatId, weapon.secondaryStatId, weapon.skillStatId) === key) {
      matches.push(id)
    }
  }
  return matches
}

/** 计算与指定武器属性组合相同的自定义基质 ID 列表（不含自身） */
function getSameStatCustomWeaponIds(weaponId: string): string[] {
  const key = getWeaponStatKey(weaponId)
  return customStats.value
    .filter((stat) => toCustomStatId(stat) !== weaponId)
    .filter((stat) => buildStatKey(stat.attribute, stat.secondary, stat.skill) === key)
    .map((stat) => toCustomStatId(stat))
}

/** 获取连线目标：内置同类武器 + 相同属性组合的自定义基质 */
function getConnectionTargets(weaponId: string): string[] {
  return [...getSameStatBuiltinWeaponIds(weaponId), ...getSameStatCustomWeaponIds(weaponId)]
}

/** 更新连线 */
/** 鼠标进入武器 */
function handleWeaponMouseEnter(weaponId: string) {
  handleWeaponMouseEnterBase(weaponId, getConnectionTargets(weaponId))
}

// 监听窗口大小变化，更新连线位置
onMounted(() => {
  setupResizeListener(() => {
    if (!hoveredWeaponId.value) return []
    return getConnectionTargets(hoveredWeaponId.value)
  })
})

/** 是否显示自定义基质区段（勾选了「自定义」筛选时显示） */
const showCustomSection = computed(() => selectedRarities.value.includes('custom'))

/** 打开新建自定义基质弹窗 */
function showNewCustomDialog() {
  detailWeaponId.value = '__new_custom__'
}

/** 检查自定义基质重合（手动触发：无视「不再提示」标记，已标记的条目也要显示） */
async function checkCustomOverlap() {
  try {
    await checkCustomOverlapBase(customStats.value, matrixEntryByWeaponId.value, {
      includeSuppressed: true,
    })
  } catch (error) {
    toast.reportError('重合检测失败', error)
  }
}

/** 进入页面时的自动重合检测：尊重「不再提示」标记，已标记的条目不弹窗 */
async function checkCustomOverlapAuto() {
  try {
    await checkCustomOverlapBase(customStats.value, matrixEntryByWeaponId.value)
  } catch (error) {
    toast.reportError('重合检测失败', error)
  }
}

onMounted(async () => {
  await fetchCustomStats()
  // 重合检测要比对内置武器词条，必须等静态数据就绪，
  // 否则 weaponsMap 为空会让检测静默地一无所获。
  if (isStaticDataLoaded.value) {
    void checkCustomOverlapAuto()
  } else {
    const stop = watch(isStaticDataLoaded, (loaded) => {
      if (!loaded) return
      stop()
      void checkCustomOverlapAuto()
    })
  }
})

/** 内置武器总数（分母） */
const totalCount = computed(() =>
  weaponTypes.value.reduce((sum, wType) => sum + wType.weaponIds.length, 0),
)

/** 已拥有的内置武器数：矩阵条目里排除自定义基质（含旧格式 custom_stat_ 前缀） */
const ownedBuiltinCount = computed(
  () => [...ownedWeaponIds.value].filter((weaponId) => !isCustomEntry(weaponId)).length,
)

/** 已拥有的自定义基质数：以配置里的自定义条目为准，幽灵引用（配置中已删除）不计入 */
const ownedCustomCount = computed(
  () => customMatrixEntries.value.filter((entry) => isWeaponOwned(entry.syntheticId)).length,
)

/** 配置中定义的自定义基质总数（分母） */
const customTotalCount = computed(() => customMatrixEntries.value.length)

/**
 * 标题计数文本：内置武器 xx/77，自定义基质 yy/YY。
 *
 * 自定义基质与内置武器分母不同源（一个是静态武器表，一个是配置里的自定义条目），
 * 合成一个分数会自相矛盾，因此拆成两段；没有自定义基质时只显示内置段。
 */
const countText = computed(() => {
  const builtinText = `内置 ${ownedBuiltinCount.value} / ${totalCount.value}`
  if (customTotalCount.value === 0) return builtinText
  return `${builtinText} · 自定义 ${ownedCustomCount.value} / ${customTotalCount.value}`
})

// 过滤后的武器类型列表
//
// 每个格子要用到的派生状态在这里一次算好：模板里的函数调用不会被 Vue 缓存，
// 同一个值在 v-if 和绑定里各调一次就会算两遍。
const filteredWeaponTypes = computed(() => {
  return weaponTypes.value
    .map((wType) => ({
      ...wType,
      weapons: wType.weaponIds
        .filter((weaponId) => {
          const weapon = weaponsMap.value.get(weaponId)
          if (!weapon) return false
          return selectedRarities.value.includes(String(weapon.rarity))
        })
        .toSorted((a, b) => {
          // 按稀有度降序排序（6★ -> 3★）
          const wa = weaponsMap.value.get(a)
          const wb = weaponsMap.value.get(b)
          if (wa && wb) return wb.rarity - wa.rarity
          return 0
        })
        .map((weaponId) => {
          const maxed = isWeaponMaxed(weaponId)
          const switchable = isSwitchable(weaponId)
          return {
            id: weaponId,
            owned: isWeaponOwned(weaponId),
            maxed,
            switchable,
            switchTargetMaxed: switchable && isSwitchTargetMaxed(weaponId) && !maxed,
            showSwitchHint: switchable && !maxed,
            skillIcon: getWeaponSkillIcon(weaponId),
            statsText: getWeaponStatsText(weaponId),
          }
        }),
    }))
    .filter((wType) => wType.weapons.length > 0)
})

/**
 * 显示武器详情弹窗（左键点击）
 */
function showWeaponDetail(weaponId: string) {
  detailWeaponId.value = weaponId
}

/**
 * 获取武器属性文本
 * 自定义条目从 customStats 配置中读取属性名
 */
function getWeaponStatsText(weaponId: string): string {
  // 自定义条目：从配置中读取属性
  const found = findCustomStat(weaponId, customStats.value)
  if (found) {
    const { stat } = found
    const parts: string[] = []
    if (stat.attribute) parts.push(getGemTagName(stat.attribute))
    if (stat.secondary) parts.push(getGemTagName(stat.secondary))
    if (stat.skill) parts.push(getGemTagName(stat.skill))
    return parts.join('、') || '自定义基质'
  }
  if (isCustomEntry(weaponId)) return '自定义基质'

  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon) return '未知武器'

  const parts: string[] = []
  if (weapon.attributeStatId) {
    parts.push(getGemTagName(weapon.attributeStatId))
  }
  if (weapon.secondaryStatId) {
    parts.push(getGemTagName(weapon.secondaryStatId))
  }
  if (weapon.skillStatId) {
    parts.push(getGemTagName(weapon.skillStatId))
  }

  return parts.join('、') || '无属性'
}
</script>

<style scoped lang="scss">
.group-icon {
  width: 1.5rem;
  height: 1.5rem;
  vertical-align: middle;
}

.weapon-overview-container {
  position: relative;
}

.connection-lines-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
  overflow: visible;
}

.connection-line {
  position: absolute;
  height: 2px;
  background-color: rgb(24, 103, 192);
  transform-origin: 0 50%;

  &::before {
    content: '';
    position: absolute;
    right: -4px;
    top: -3px;
    width: 8px;
    height: 8px;
    background-color: rgb(24, 103, 192);
    border-radius: 50%;
    box-shadow: 0 0 8px rgb(24, 103, 192);
  }
}

// 淡入淡出交给 transition-group：此前靠 [style*="opacity: 1"] 匹配内联样式，
// 而元素一创建 opacity 就是 1，那套写法实际上从未产生过淡入效果。
.connection-line-enter-active,
.connection-line-leave-active {
  transition: opacity 0.2s ease;
}

.connection-line-enter-from,
.connection-line-leave-to {
  opacity: 0;
}

.weapon-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(3.5rem, 1fr));
  gap: 0.5rem;
}

.weapon-add-button {
  width: 100%;
  height: 100%;
  cursor: pointer;
  border: 2px dashed rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    border-color 0.15s,
    background 0.15s;

  &:hover {
    border-color: rgba(var(--v-theme-primary), 0.6);
    background: rgba(var(--v-theme-primary), 0.05);
  }
}

.weapon-overview-item {
  width: 3.5rem;
  height: 3.5rem;
  cursor: pointer;
  position: relative;

  &:hover .weapon-icon-wrapper {
    transform: scale(1.05);
  }

  // 彩虹环仅悬停时显示
  &:hover .rainbow-border {
    opacity: 1;
  }
}

.weapon-icon-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  transition:
    transform 0.15s,
    opacity 0.15s,
    filter 0.15s;
  border-radius: 6px;
  overflow: hidden;

  // 未拥有：灰色滤镜必须作用于上级容器，标记作为兄弟节点避免被叠加影响
  &.weapon-not-owned {
    opacity: 0.4;
    filter: grayscale(0.8);
  }

  // 可切换目标满级：灰色呼吸背景
  &.switch-target-maxed {
    animation: switch-target-breathe 2s ease-in-out infinite;
  }

  // 已满级：彩虹边框动画（优先级最高，必须在 switch-target-maxed 之后定义以覆盖）
  &.weapon-maxed {
    animation: rainbow-glow 3s linear infinite;
  }
}

// 左上角缩小版圆形基质图标（底板+技能叠加）
.weapon-matrix-badge {
  position: absolute;
  top: -3px;
  left: -3px;
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 50%;
  overflow: hidden;
  z-index: 5;
  pointer-events: none;
  border: 1.5px solid rgba(255, 255, 255, 0);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;

  // 中号模式：2倍大小
  &--medium {
    width: 2.4rem;
    height: 2.4rem;
    top: -5.3px;
    left: -5.3px;
    z-index: 5;
  }
}

.weapon-matrix-badge-bg {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
}

.weapon-matrix-badge-skill {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 1;
  transform: translate(5%, -5%);
}

// 可切换小橙点（通知 badge 样式）
.switch-dot {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #ff7100;
  z-index: 5;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(255, 113, 0, 0.6);
}

.rainbow-border {
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: linear-gradient(
    45deg,
    #fff,
    #ff4ada,
    #ff4e4e,
    #ff9832,
    #ff0,
    #0f0,
    #00ffff,
    #79a0fd,
    #d46eff,
    #ff8df0,
    #fff
  );
  background-size: 400% 400%;
  animation: rainbow-rotate 3s linear infinite;
  z-index: 1;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  // 只露出 2px 渐变环：mask 挖空中间，避免渐变覆盖图标与名称
  padding: 2px;
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
}

@keyframes rainbow-rotate {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

@keyframes rainbow-glow {
  0%,
  100% {
    box-shadow: 0 0 10px rgba(255, 0, 0, 0.8);
  }
  14% {
    box-shadow: 0 0 10px rgba(255, 127, 0, 0.8);
  }
  28% {
    box-shadow: 0 0 10px rgba(255, 255, 0, 0.8);
  }
  42% {
    box-shadow: 0 0 10px rgba(0, 255, 0, 0.8);
  }
  57% {
    box-shadow: 0 0 10px rgba(0, 0, 255, 0.8);
  }
  71% {
    box-shadow: 0 0 10px rgba(75, 0, 130, 0.8);
  }
  85% {
    box-shadow: 0 0 10px rgba(148, 0, 211, 0.8);
  }
}

.switchable-badge {
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 6;
  pointer-events: none;
  font-size: 0.55rem !important;
  height: 14px !important;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
}

@keyframes switch-target-breathe {
  0%,
  100% {
    box-shadow: 0 0 8px 2px rgba(128, 128, 128, 0.3);
  }
  50% {
    box-shadow: 0 0 14px 5px rgba(158, 158, 158, 0.85);
  }
}
</style>
