<template>
  <!-- 武器详情弹窗 -->
  <v-dialog v-model="dialogOpen" max-width="680">
    <v-card v-if="weaponId">
      <v-card-item>
        <template #prepend>
          <custom-stat-icon
            v-if="isCustomEntry(weaponId) || isNewCustom"
            class="weapon-icon-detail"
            hide-name
            :name="customEntryName || '新基质'"
            :skill-stat-id="customEditSkill"
          />
          <item-icon v-else class="weapon-icon-detail" :item-id="weaponId" />
        </template>
        <v-card-title>
          <v-text-field
            v-if="isCustomEntry(weaponId) || isNewCustom"
            v-model="customEntryName"
            class="custom-name-field"
            density="compact"
            hide-details
            placeholder="自定义基质名称(点我进行修改)"
            variant="underlined"
          />
          <template v-else>
            {{ weaponsMap.get(weaponId)?.name || weaponId }}
          </template>
        </v-card-title>
        <template #append>
          <v-btn icon="mdi-close" variant="text" @click="dialogOpen = false" />
        </template>
      </v-card-item>
      <v-divider />
      <v-card-text>
        <!-- 基质属性 -->
        <div class="mb-4">
          <div class="text-subtitle-2 mb-2">基质属性</div>
          <v-row dense>
            <v-col cols="12" sm="4">
              <v-select
                :clearable="isCustomEntry(weaponId) || isNewCustom"
                density="compact"
                :disabled="!(isCustomEntry(weaponId) || isNewCustom)"
                hide-details
                :items="allAttributeStats.map((id) => ({ title: getGemTagName(id), value: id }))"
                label="基础属性"
                :model-value="
                  isCustomEntry(weaponId) || isNewCustom
                    ? customEditAttribute
                    : (weaponsMap.get(weaponId)?.attributeStatId ?? null)
                "
                variant="outlined"
                @update:model-value="
                  isCustomEntry(weaponId) || isNewCustom
                    ? (customEditAttribute = $event)
                    : undefined
                "
              />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select
                :clearable="isCustomEntry(weaponId) || isNewCustom"
                density="compact"
                :disabled="!(isCustomEntry(weaponId) || isNewCustom)"
                hide-details
                :items="allSecondaryStats.map((id) => ({ title: getGemTagName(id), value: id }))"
                label="附加属性"
                :model-value="
                  isCustomEntry(weaponId) || isNewCustom
                    ? customEditSecondary
                    : (weaponsMap.get(weaponId)?.secondaryStatId ?? null)
                "
                variant="outlined"
                @update:model-value="
                  isCustomEntry(weaponId) || isNewCustom
                    ? (customEditSecondary = $event)
                    : undefined
                "
              />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select
                :clearable="isCustomEntry(weaponId) || isNewCustom"
                density="compact"
                :disabled="!(isCustomEntry(weaponId) || isNewCustom)"
                hide-details
                :items="allSkillStats.map((id) => ({ title: getGemTagName(id), value: id }))"
                label="技能属性"
                :model-value="
                  isCustomEntry(weaponId) || isNewCustom
                    ? customEditSkill
                    : (weaponsMap.get(weaponId)?.skillStatId ?? null)
                "
                variant="outlined"
                @update:model-value="
                  isCustomEntry(weaponId) || isNewCustom ? (customEditSkill = $event) : undefined
                "
              />
            </v-col>
          </v-row>
        </div>

        <!-- 跳转基质规划：查看该基质的刷取方案 -->
        <v-btn
          v-if="!isNewCustom"
          class="mb-4"
          color="primary"
          prepend-icon="mdi-map-search"
          size="small"
          variant="tonal"
          @click="navigateToPlanner"
        >
          查看最优刷取方案
        </v-btn>

        <!-- 基质等级 -->
        <div class="mb-4 detail-level-outer">
          <div class="text-subtitle-2 mb-2">当前基质等级</div>
          <div class="detail-level-wrapper">
            <div class="detail-level-section">
              <div class="detail-attr-control detail-attr-control--primary">
                <span class="detail-attr-label">基础属性</span>
                <div class="detail-attr-pips">
                  <span
                    v-for="level in affixLevelItems"
                    :key="`d-a1-${level}`"
                    class="detail-pip"
                    :class="{
                      active: level <= detailAffix1,
                      'detail-pip--max': detailAffix1 === 6,
                    }"
                    @click="detailAffix1 = level"
                  />
                </div>
                <span
                  class="detail-attr-value"
                  :class="{ 'detail-attr-value--full': detailAffix1 === 6 }"
                >
                  +{{ detailAffix1 }} / 6
                </span>
              </div>

              <div class="detail-attr-control detail-attr-control--teal">
                <span class="detail-attr-label">附加属性</span>
                <div class="detail-attr-pips">
                  <span
                    v-for="level in affixLevelItems"
                    :key="`d-a2-${level}`"
                    class="detail-pip"
                    :class="{
                      active: level <= detailAffix2,
                      'detail-pip--max': detailAffix2 === 6,
                    }"
                    @click="detailAffix2 = level"
                  />
                </div>
                <span
                  class="detail-attr-value"
                  :class="{ 'detail-attr-value--full': detailAffix2 === 6 }"
                >
                  +{{ detailAffix2 }} / 6
                </span>
              </div>

              <div class="detail-attr-control detail-attr-control--indigo">
                <span class="detail-attr-label">技能属性</span>
                <div class="detail-attr-pips detail-attr-pips--skill">
                  <span
                    v-for="level in skillLevelItems"
                    :key="`d-a3-${level}`"
                    class="detail-pip"
                    :class="{
                      active: level <= detailAffix3,
                      'detail-pip--max': detailAffix3 === 3,
                    }"
                    @click="detailAffix3 = level"
                  />
                </div>
                <span
                  class="detail-attr-value"
                  :class="{ 'detail-attr-value--full': detailAffix3 === 3 }"
                >
                  +{{ detailAffix3 }} / 3
                </span>
              </div>
            </div>

            <!-- 未拥有斜向胶带遮罩（贯穿三个属性，可点击切换拥有） -->
            <transition name="tape-peel">
              <div
                v-if="!isDetailOwned"
                class="not-owned-tape-detail"
                @click="toggleDetailOwnership"
              >
                <span class="not-owned-tape-detail-text"
                  >» 未拥有 » NOT OWNED » 点击切换为拥有 » CLICK TO TOGGLE »
                </span>
              </div>
            </transition>
          </div>

          <!-- 未拥有遮罩：覆盖等级区域，阻止交互 -->
          <div
            v-if="!isDetailOwned"
            class="not-owned-block-overlay"
            @click="toggleDetailOwnership"
          />

          <!-- 拥有状态切换 -->
          <div class="mt-2">
            <v-chip
              :color="isDetailOwned ? 'success' : 'grey'"
              :prepend-icon="isDetailOwned ? 'mdi-check-circle' : 'mdi-close-circle'"
              size="small"
              variant="tonal"
              @click="toggleDetailOwnership"
            >
              {{ isDetailOwned ? '已拥有 · 点击可切换为 未拥有' : '未拥有 · 点击可切换为 已拥有' }}
            </v-chip>
          </div>
        </div>

        <!-- 优先级设置 -->
        <div class="mb-4">
          <div class="text-subtitle-2 mb-1">基质匹配优先级</div>
          <div class="d-flex flex-wrap align-center ga-2 mb-2">
            <v-chip
              v-for="p in [1, 2, 3, 4, 5, 6, 7, 8, 9]"
              :key="p"
              :color="getPriorityColor(p)"
              size="small"
              :variant="isPriorityActive(p) ? 'flat' : 'outlined'"
              @click="detailPriority = p"
            >
              {{ p }}
            </v-chip>
            <v-divider class="mx-1" vertical />
            <v-btn
              :color="detailPriority === 0 ? 'primary' : undefined"
              prepend-icon="mdi-restore"
              size="small"
              :variant="detailPriority === 0 ? 'flat' : 'outlined'"
              @click="detailPriority = 0"
            >
              默认 {{ defaultPriority }}
            </v-btn>
          </div>
          <div class="text-caption text-medium-emphasis" style="line-height: 1.6">
            当扫描到一个无暇基质同时匹配多把武器时，系统会按优先级将该基质分配给优先级最高的武器。<br />
            默认使用武器稀有度作为优先级（6★=6, 5★=5, 4★=4, 3★=3），自定义基质默认 6。<br />
            点击 1-9 手动设置优先级（数值越大越优先）；点击「默认
            {{ defaultPriority }}」恢复默认优先级。<br />
            已满级（6/6/3）的武器会被自动跳过。
          </div>
        </div>

        <!-- 同类武器（仅非自定义且非新建时显示） -->
        <div
          v-if="!isCustomEntry(weaponId) && !isNewCustom && getSameStatWeapons(weaponId).length > 0"
        >
          <div class="text-subtitle-2 mb-2">同类属性武器</div>
          <div class="d-flex flex-column ga-2">
            <v-card
              v-for="sameId in getSameStatWeapons(weaponId)"
              :key="sameId"
              class="pa-2"
              variant="outlined"
            >
              <div class="d-flex align-center justify-space-between">
                <div class="d-flex align-center ga-2">
                  <item-icon class="weapon-icon-same" :item-id="sameId" />
                  <div>
                    <div class="font-weight-bold text-body-2">
                      {{ weaponsMap.get(sameId)?.name || sameId }}
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      {{ getMatrixLevelText(sameId) }}
                      <span class="ml-1">优先级: {{ getWeaponPriority(sameId) }}</span>
                    </div>
                  </div>
                </div>
                <v-btn
                  color="primary"
                  size="small"
                  variant="tonal"
                  @click="swapMatrix(weaponId!, sameId)"
                >
                  交换
                </v-btn>
              </div>
            </v-card>
          </div>
        </div>
        <div
          v-else-if="!isCustomEntry(weaponId) && !isNewCustom"
          class="text-medium-emphasis text-caption"
        >
          没有其他武器与此武器共享相同属性组合。
        </div>
      </v-card-text>

      <!-- 操作按钮 -->
      <v-divider />
      <v-card-actions>
        <!-- 自定义基质（新建+编辑）：保存 + 删除 -->
        <template v-if="isCustomEntry(weaponId) || isNewCustom">
          <v-btn
            v-if="!isNewCustom"
            color="error"
            prepend-icon="mdi-delete"
            variant="text"
            @click="promptDeleteCustomEntry"
          >
            删除此自定义基质·无法恢复
          </v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            prepend-icon="mdi-content-save"
            variant="flat"
            @click="saveCustomEntry"
          >
            保存
          </v-btn>
        </template>
        <!-- 非自定义基质：清空 -->
        <template v-else>
          <v-btn
            v-if="isWeaponOwned(weaponId)"
            color="error"
            prepend-icon="mdi-delete-outline"
            variant="text"
            @click="removeNonCustomEntry(weaponId!)"
          >
            清空此基质的保存数据
          </v-btn>
          <v-spacer />
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除自定义基质确认弹窗 -->
  <v-dialog v-model="deleteCustomConfirm" max-width="460">
    <v-card>
      <v-card-title class="text-error">删除自定义基质</v-card-title>
      <v-card-text>
        确定要删除自定义基质「{{
          deleteCustomName
        }}」吗？将从设置中移除该基质定义，并从当前账号的基质数据中移除对应条目，此操作不可撤销。
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="cancelDeleteCustomEntry">取消</v-btn>
        <v-btn color="error" @click="confirmDeleteCustomEntry">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import CustomStatIcon from '@/components/CustomStatIcon.vue'
import ItemIcon from '@/components/ItemIcon.vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useProfiles } from '@/composables/useProfiles'
import { useWeaponStats } from '@/composables/useWeaponStats'
import { useStaticData } from '@/utils/gameData/staticData'
import { fallbackCustomStatName, findCustomStat, getGemTagName } from '@/utils/gameData/weapon'

// v-model:weapon-id：null 表示关闭，string 表示打开并编辑该武器
const weaponId = defineModel<string | null>('weaponId', { default: null })

const dialogOpen = computed({
  get: () => weaponId.value !== null,
  set: (open: boolean) => {
    if (!open) weaponId.value = null
  },
})

const router = useRouter()

/**
 * 跳转到基质规划页面，在武器预设中选中当前基质并计算最优刷取方案。
 * 不使用预刻券模式保持关闭（不传 noPrecraft 参数）。
 */
function navigateToPlanner() {
  const id = weaponId.value
  if (!id || id === '__new_custom__') return
  router.push({
    name: 'matrix-planner',
    query: { clear: 'true', weapon: id },
  })
  // 滚动到页面顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const { weaponsMap, essencesMap } = useStaticData()
const { treasureMatrix, updateTreasureMatrix, updateWeaponPriority } = useProfiles()
const {
  customStats,
  saveCustomEntry: saveCustomEntryBase,
  confirmDeleteCustomEntry: confirmDeleteCustomEntryBase,
  removeNonCustomEntry: removeNonCustomEntryBase,
  toggleWeaponOwnership,
} = useCustomStats()
const {
  matrixEntryByWeaponId,
  isWeaponOwned,
  isCustomEntry,
  getUserPriority,
  getWeaponPriority,
  getSameStatWeapons,
  getMatrixLevelText,
} = useWeaponStats()

// --- 详情弹窗编辑状态 ---

/** 新建模式标识 */
const isNewCustom = computed(() => weaponId.value === '__new_custom__')

/**
 * 未手动设置优先级时生效的默认值：自定义基质按 6★ 处理，普通武器取稀有度。
 * 直接显示在「默认」chip 上，用户无需对照武器颜色推算当前优先级。
 */
const defaultPriority = computed(() => {
  const id = weaponId.value
  if (!id || id === '__new_custom__' || isCustomEntry(id)) return 6
  return weaponsMap.value.get(id)?.rarity ?? 0
})

/**
 * 优先级的点亮颜色按区段区分：
 * 1-3 亮粉 → 紫，4-6 与武器稀有度色一致（4★紫/5★金橙/6★红橙），7-9 橙 → 红。
 * 颜色与宝藏基质页的 tier 样式保持一致。
 */
const priorityColors: Record<number, string> = {
  1: '#B7B8BE',
  2: '#539A31',
  3: '#009fe6',
  4: '#8e5cff',
  5: '#ffb020',
  6: '#ff5a36',
  7: '#FF0000',
  8: '#BD1F80',
  9: '#FF39FF',
}

function getPriorityColor(priority: number): string {
  return priorityColors[priority] ?? 'primary'
}

/**
 * chip 是否点亮：手动设置的值点亮；未设置时点亮默认值对应的数字，
 * 让用户不用盯着「默认 N」也能一眼看到当前生效的优先级。
 */
function isPriorityActive(priority: number): boolean {
  return (
    detailPriority.value === priority ||
    (detailPriority.value === 0 && priority === defaultPriority.value)
  )
}

/** 自定义基质编辑中的属性 */
const customEditAttribute = ref<string | null>(null)
const customEditSecondary = ref<string | null>(null)
const customEditSkill = ref<string | null>(null)

/** 等级编辑状态 */
const detailAffix1 = ref(1)
const detailAffix2 = ref(1)
const detailAffix3 = ref(1)

/** 优先级编辑状态 */
const detailPriority = ref(6)

/** 新建模式下的拥有状态（用户手动切换） */
const detailOwnedOverride = ref(false)

/** 当前弹窗中的条目是否已拥有 */
const isDetailOwned = computed(() => {
  const id = weaponId.value
  if (!id) return false
  if (id === '__new_custom__') return detailOwnedOverride.value
  return isWeaponOwned(id)
})

/** 自定义条目编辑中的名称 */
const customEntryName = ref('')

// --- 属性选项列表 ---
const allAttributeStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'ATTRIBUTE')
    .map((e) => e.id),
)
const allSecondaryStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'SECONDARY')
    .map((e) => e.id),
)
const allSkillStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((e) => e.type === 'SKILL')
    .map((e) => e.id),
)

// --- 等级选项 ---
const affixLevelItems = [1, 2, 3, 4, 5, 6]
const skillLevelItems = [1, 2, 3]

// --- 删除自定义基质 ---
const deleteCustomConfirm = ref(false)
const deleteCustomTargetId = ref<string | null>(null)
const deleteCustomName = ref('')

// 弹窗打开时，加载编辑状态
watch(weaponId, () => {
  // 弹窗关闭时清理防抖定时器，避免关窗后发起无效请求
  if (!weaponId.value) {
    clearDetailSaveTimers()
    return
  }

  const id = weaponId.value

  if (id === '__new_custom__') {
    // 新建模式：重置所有字段
    customEntryName.value = ''
    customEditAttribute.value = null
    customEditSecondary.value = null
    customEditSkill.value = null
    detailAffix1.value = 1
    detailAffix2.value = 1
    detailAffix3.value = 1
    detailPriority.value = 0
    detailOwnedOverride.value = false
  } else if (isCustomEntry(id)) {
    // 编辑自定义条目
    const stat = findCustomStat(id, customStats.value)?.stat
    customEntryName.value = stat?.name || ''
    customEditAttribute.value = stat?.attribute ?? null
    customEditSecondary.value = stat?.secondary ?? null
    customEditSkill.value = stat?.skill ?? null
    // 从 profile 中读取等级
    const entry = matrixEntryByWeaponId.value.get(id)
    detailAffix1.value = entry?.affix1_level ?? 1
    detailAffix2.value = entry?.affix2_level ?? 1
    detailAffix3.value = entry?.affix3_level ?? 1
    // 只回显用户显式设置过的优先级：把稀有度默认值当"用户设置"写回
    // 会污染数据，且此后没有入口清除。
    detailPriority.value = getUserPriority(id)
  } else {
    // 非自定义条目：从 profile 中读取等级
    const entry = matrixEntryByWeaponId.value.get(id)
    detailAffix1.value = entry?.affix1_level ?? 1
    detailAffix2.value = entry?.affix2_level ?? 1
    detailAffix3.value = entry?.affix3_level ?? 1
    detailPriority.value = getUserPriority(id)
  }
})

/** 切换当前弹窗条目的拥有状态 */
async function toggleDetailOwnership() {
  const id = weaponId.value
  if (!id) return
  if (id === '__new_custom__') {
    detailOwnedOverride.value = !detailOwnedOverride.value
  } else {
    await toggleWeaponOwnership(id)
  }
}

/** 保存自定义基质（新建或编辑） */
async function saveCustomEntry() {
  const id = weaponId.value
  if (!id) return

  try {
    await saveCustomEntryBase({
      weaponId: id,
      name: customEntryName.value,
      attribute: customEditAttribute.value,
      secondary: customEditSecondary.value,
      skill: customEditSkill.value,
      affix1: detailAffix1.value,
      affix2: detailAffix2.value,
      affix3: detailAffix3.value,
      priority: detailPriority.value,
      isOwned: isDetailOwned.value,
      matrixEntryByWeaponId: matrixEntryByWeaponId.value,
      treasureMatrix: treasureMatrix.value,
    })
    dialogOpen.value = false
  } catch {
    // toast 已由 _handleError 统一弹出，此处不再重复。
  }
}

/** 非自定义基质：从基质配置中移除 */
async function removeNonCustomEntry(weaponId: string) {
  try {
    await removeNonCustomEntryBase(weaponId)
    dialogOpen.value = false
  } catch {
    // toast 已由 _handleError 统一弹出，此处不再重复。
  }
}

/** 非自定义基质：等级变化时自动保存（防抖）；未拥有的武器没有基质条目，等级无处可写 */
let detailSaveTimer: ReturnType<typeof setTimeout> | null = null
watch([detailAffix1, detailAffix2, detailAffix3], async () => {
  const id = weaponId.value
  // 仅对已存在的非自定义条目自动保存
  if (!id || id === '__new_custom__' || isCustomEntry(id)) return
  if (!isWeaponOwned(id)) return

  if (detailSaveTimer) clearTimeout(detailSaveTimer)
  detailSaveTimer = setTimeout(async () => {
    try {
      if (!matrixEntryByWeaponId.value.has(id)) return
      // 构造新数组提交，不就地改动响应式条目：写操作成功后本地快照会被
      // 后端返回值整体替换，此时对旧对象做的任何回滚都落不到实处。
      const nextMatrix = treasureMatrix.value.map((item) =>
        item.weapon_id === id
          ? {
              ...item,
              affix1_level: detailAffix1.value,
              affix2_level: detailAffix2.value,
              affix3_level: detailAffix3.value,
              priority: detailPriority.value,
            }
          : item,
      )
      await updateTreasureMatrix(nextMatrix)
      await updateWeaponPriority(id, detailPriority.value)
    } catch {
      // toast 已由 _handleError 统一弹出，此处不再重复。
    } finally {
      detailSaveTimer = null
    }
  }, 400)
})

/**
 * 非自定义基质：优先级变化时自动保存（防抖）。
 *
 * 优先级存在 profile.weapon_priorities，与「是否拥有基质」无关：只有它能表达
 * 「未拥有基质但用户设过优先级」，而未拥有的武器同样需要这个设置——扫描时它
 * 决定同属性武器中谁先认领基质。因此这条路径不设拥有状态守卫，否则在总览里
 * 给未拥有武器设的优先级一关弹窗就会丢。
 *
 * 打开弹窗/切换武器时的回填不写盘：那时 detailPriority 与已存值本就相等。
 */
let detailPrioritySaveTimer: ReturnType<typeof setTimeout> | null = null
watch(detailPriority, () => {
  const id = weaponId.value
  if (!id || id === '__new_custom__' || isCustomEntry(id)) return
  if (detailPriority.value === getUserPriority(id)) return

  if (detailPrioritySaveTimer) clearTimeout(detailPrioritySaveTimer)
  detailPrioritySaveTimer = setTimeout(async () => {
    try {
      await updateWeaponPriority(id, detailPriority.value)
    } catch {
      // toast 已由 _handleError 统一弹出，此处不再重复。
    } finally {
      detailPrioritySaveTimer = null
    }
  }, 400)
})

/** 清理两个自动保存的防抖定时器，避免关窗/销毁后发起无效请求 */
function clearDetailSaveTimers() {
  if (detailSaveTimer) {
    clearTimeout(detailSaveTimer)
    detailSaveTimer = null
  }
  if (detailPrioritySaveTimer) {
    clearTimeout(detailPrioritySaveTimer)
    detailPrioritySaveTimer = null
  }
}

onUnmounted(clearDetailSaveTimers)

/** 打开删除自定义基质的二次确认弹窗 */
function promptDeleteCustomEntry() {
  const id = weaponId.value
  if (!isCustomEntry(id)) return
  const found = findCustomStat(id, customStats.value)
  if (!found) return
  deleteCustomTargetId.value = id
  deleteCustomName.value = found.stat.name || fallbackCustomStatName(found.index)
  deleteCustomConfirm.value = true
}

/** 取消删除 */
function cancelDeleteCustomEntry() {
  deleteCustomConfirm.value = false
}

/**
 * 确认删除自定义基质：
 * 1. 从 profile 中移除该条目（稳定 ID 让其余条目的引用不受影响）
 * 2. 从 config 的自定义列表移除该项
 */
async function confirmDeleteCustomEntry() {
  const targetId = deleteCustomTargetId.value
  if (!targetId) {
    cancelDeleteCustomEntry()
    return
  }

  try {
    await confirmDeleteCustomEntryBase({
      id: targetId,
      treasureMatrix: treasureMatrix.value,
    })
    deleteCustomConfirm.value = false
    dialogOpen.value = false
    weaponId.value = null
    deleteCustomTargetId.value = null
  } catch {
    // toast 已由 _handleError 统一弹出，此处不再重复。
  }
}

/**
 * 交换两把武器的基质数据
 *
 * 优先级只交换用户显式设置过的值（0 表示未设置）：把 `getEffectivePriority`
 * 算出来的稀有度默认值写回去，等于替用户"手动"设定了一个他从没设过的优先级，
 * 此后该武器就再也跟不上稀有度变化了。
 */
async function swapMatrix(weaponAId: string, weaponBId: string) {
  const entries = treasureMatrix.value.map((entry) => ({ ...entry }))
  const entryA = entries.find((e) => e.weapon_id === weaponAId)
  const entryB = entries.find((e) => e.weapon_id === weaponBId)

  const weaponA = weaponsMap.value.get(weaponAId)
  const weaponB = weaponsMap.value.get(weaponBId)

  const hasA = !!entryA
  const hasB = !!entryB

  if (!hasA && !hasB) return

  const priorityA = getUserPriority(weaponAId)
  const priorityB = getUserPriority(weaponBId)

  let nextEntries: typeof entries
  if (hasA && !hasB) {
    // A有基质、B无基质 → A移除、B添加A的数据
    nextEntries = entries
      .filter((entry) => entry.weapon_id !== weaponAId)
      .concat({
        ...entryA!,
        weapon_id: weaponBId,
        weapon_name: weaponB?.name || weaponBId,
        priority: priorityA,
      })
  } else if (!hasA && hasB) {
    // A无基质、B有基质 → A添加B的数据、B移除
    nextEntries = entries
      .filter((entry) => entry.weapon_id !== weaponBId)
      .concat({
        ...entryB!,
        weapon_id: weaponAId,
        weapon_name: weaponA?.name || weaponAId,
        priority: priorityB,
      })
  } else {
    // 两者都有基质，交换等级、计算开关和用户优先级
    const matrixA = {
      affix1: entryA!.affix1_level,
      affix2: entryA!.affix2_level,
      affix3: entryA!.affix3_level,
      includeInCalculation: entryA!.include_in_calculation,
    }
    entryA!.affix1_level = entryB!.affix1_level
    entryA!.affix2_level = entryB!.affix2_level
    entryA!.affix3_level = entryB!.affix3_level
    entryA!.include_in_calculation = entryB!.include_in_calculation
    entryA!.priority = priorityB

    entryB!.affix1_level = matrixA.affix1
    entryB!.affix2_level = matrixA.affix2
    entryB!.affix3_level = matrixA.affix3
    entryB!.include_in_calculation = matrixA.includeInCalculation
    entryB!.priority = priorityA

    nextEntries = entries
  }

  try {
    await updateTreasureMatrix(nextEntries)
    await updateWeaponPriority(weaponAId, priorityB)
    await updateWeaponPriority(weaponBId, priorityA)
    dialogOpen.value = false
  } catch {
    // toast 已由 _handleError 统一弹出，此处不再重复。
  }
}
</script>

<style scoped lang="scss">
// --- 详情弹窗等级编辑样式 ---
.detail-level-section {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.detail-attr-control {
  flex: 1;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  border-radius: 12px;
  transition: background 0.18s;

  &:hover {
    background: rgba(var(--v-theme-on-surface), 0.03);
  }
}

.detail-attr-label {
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.detail-attr-pips {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 20px;
}

.detail-pip {
  width: 10px;
  height: 20px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.12);
  cursor: pointer;
  transition:
    background 0.18s,
    box-shadow 0.18s,
    transform 0.18s;

  &:hover {
    transform: translateY(-1px) scaleY(1.08);
  }
}

.detail-attr-control--primary .detail-pip.active {
  background: rgb(var(--v-theme-primary));
  box-shadow: 0 2px 7px rgba(var(--v-theme-primary), 0.32);
}

.detail-attr-control--teal .detail-pip.active {
  background: #48a9a6;
  box-shadow: 0 2px 7px rgba(72, 169, 166, 0.34);
}

.detail-attr-control--indigo .detail-pip.active {
  background: #5c6bc0;
  box-shadow: 0 2px 7px rgba(92, 107, 192, 0.34);
}

.detail-pip.detail-pip--max.active {
  animation: detailPipPulse 2.2s ease-in-out infinite;
}

.detail-attr-value {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.85rem;
  font-weight: 800;
}

.detail-attr-value--full {
  color: rgb(var(--v-theme-primary));
}

@keyframes detailPipPulse {
  0%,
  100% {
    transform: scaleY(1);
    filter: brightness(1);
  }
  50% {
    transform: scaleY(1.08);
    filter: brightness(1.18);
  }
}

// 未拥有斜向胶带遮罩（弹窗内等级区域）
.detail-level-wrapper {
  position: relative;
}

.not-owned-tape-detail {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 110%;
  height: 24px;
  background: linear-gradient(
    135deg,
    rgba(255, 193, 7, 0.95) 0%,
    rgba(255, 193, 7, 0.88) 40%,
    rgba(255, 193, 7, 0.8) 100%
  );
  transform: translate(-50%, -50%) rotate(-8deg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  pointer-events: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.not-owned-tape-detail-text {
  color: rgba(0, 0, 0, 0.8);
  font-size: 0.8rem;
  font-weight: 900;
  letter-spacing: 0.2em;
  white-space: nowrap;
}

// 撕开胶布动画（左到右渐出/渐入）
.tape-peel-enter-active {
  animation: tape-peel-in 0.2s ease-out forwards;
}

.tape-peel-leave-active {
  animation: tape-peel-out 0.2s ease-in forwards;
}

@keyframes tape-peel-in {
  from {
    clip-path: inset(0 100% 0 0);
  }
  to {
    clip-path: inset(0 0 0 0);
  }
}

@keyframes tape-peel-out {
  from {
    clip-path: inset(0 0 0 0);
  }
  to {
    clip-path: inset(0 0 0 100%);
  }
}

// 未拥有遮罩层：覆盖等级区域，阻止点击
.detail-level-outer {
  position: relative;
}

.not-owned-block-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 6;
  cursor: pointer;
}

.weapon-icon-detail {
  width: 3rem !important;
  height: 3rem !important;
  min-width: 3rem !important;
  min-height: 3rem !important;
}

// 自定义基质名称输入框：字号与内置武器名（v-card-title 默认 1.25rem）保持一致
.custom-name-field :deep(.v-field__input) {
  font-size: 1.25em;
}

.weapon-icon-same {
  width: 2rem !important;
  height: 2rem !important;
  flex-shrink: 0;
}
</style>
