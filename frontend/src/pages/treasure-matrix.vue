<template>
  <v-container class="treasure-matrix-page">
    <v-expansion-panels v-model="openedPanels" multiple>
      <!-- 武器总览 -->
      <weapon-overview />

      <!-- Treasure Matrix Config -->
      <v-expansion-panel :value="1">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-diamond-stone</v-icon>
          宝藏基质配置
          <v-chip class="ml-2" color="primary" size="small" variant="flat">
            {{ activeProfileName }}
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            保存你当前账号下每把武器的宝藏基质词条等级，用于计算建议刷取次数。点击武器卡片可切换是否参与计算。
          </v-alert>

          <!-- 星级过滤开关 -->
          <div class="d-flex align-center gap-2 mb-3">
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

          <!-- 显示满级武器开关 -->
          <div class="d-flex align-center mb-3">
            <v-switch
              v-model="showMaxedWeapons"
              color="primary"
              density="compact"
              hide-details
              label="显示满级武器（6/6/3）"
            />
          </div>

          <!-- Existing entries -->
          <v-card
            v-for="(entry, index) in filteredMatrixEntries"
            :key="entry.weapon_id"
            class="mb-3 entry-card"
            :class="{
              'entry-card--muted': entry.include_in_calculation === false,
            }"
            variant="outlined"
          >
            <v-card-text class="clickable-card pa-0" @click="toggleIncludeInCalculation(entry)">
              <div class="matrix-card-body">
                <section class="weapon-identity">
                  <div class="weapon-icon-wrap" :class="getWeaponTierClass(entry.weapon_id)">
                    <custom-stat-icon
                      v-if="isCustomEntry(entry.weapon_id)"
                      hide-name
                      :name="entry.weapon_name || entry.weapon_id"
                      :skill-stat-id="getCustomStatSkillId(entry.weapon_id, customStats)"
                      small
                    />
                    <item-icon v-else class="weapon-icon-small" :item-id="entry.weapon_id" />
                    <span class="weapon-tier">{{ getWeaponRarityText(entry.weapon_id) }}</span>
                  </div>
                  <div class="weapon-info">
                    <div class="weapon-name">{{ entry.weapon_name || entry.weapon_id }}</div>
                    <div class="weapon-traits">
                      <span
                        v-for="trait in getWeaponTraitNames(entry.weapon_id)"
                        :key="trait"
                        class="trait"
                      >
                        {{ trait }}
                      </span>
                    </div>
                    <v-chip
                      class="participation-chip"
                      :color="entry.include_in_calculation === false ? 'grey' : 'primary'"
                      size="x-small"
                      variant="tonal"
                    >
                      {{ entry.include_in_calculation === false ? '已排除' : '参与计算' }}
                    </v-chip>
                  </div>
                </section>

                <section class="attribute-section">
                  <div class="attr-control attr-control--primary" @click.stop>
                    <span class="attr-label">基础属性</span>
                    <div aria-label="基础属性等级" class="attr-pips" role="group">
                      <span
                        v-for="level in affixLevelItems"
                        :key="`a1-${level}`"
                        :aria-label="`设置基础属性为 +${level}`"
                        class="pip"
                        :class="{
                          active: level <= entry.affix1_level,
                          'pip--max': entry.affix1_level === AFFIX_MAX_LEVEL[0],
                        }"
                        role="button"
                        tabindex="0"
                        @click.stop="setEntryAffixLevel(entry, 1, level)"
                        @keydown.enter.stop.prevent="setEntryAffixLevel(entry, 1, level)"
                        @keydown.space.stop.prevent="setEntryAffixLevel(entry, 1, level)"
                      />
                    </div>
                    <span
                      class="attr-value"
                      :class="{ 'attr-value--full': entry.affix1_level === AFFIX_MAX_LEVEL[0] }"
                    >
                      +{{ entry.affix1_level }} / {{ AFFIX_MAX_LEVEL[0] }}
                    </span>
                    <span v-if="entry.affix1_level === AFFIX_MAX_LEVEL[0]" class="max-label"
                      >MAX</span
                    >
                  </div>

                  <div class="attr-control attr-control--teal" @click.stop>
                    <span class="attr-label">附加属性</span>
                    <div aria-label="附加属性等级" class="attr-pips" role="group">
                      <span
                        v-for="level in affixLevelItems"
                        :key="`a2-${level}`"
                        :aria-label="`设置附加属性为 +${level}`"
                        class="pip"
                        :class="{
                          active: level <= entry.affix2_level,
                          'pip--max': entry.affix2_level === AFFIX_MAX_LEVEL[1],
                        }"
                        role="button"
                        tabindex="0"
                        @click.stop="setEntryAffixLevel(entry, 2, level)"
                        @keydown.enter.stop.prevent="setEntryAffixLevel(entry, 2, level)"
                        @keydown.space.stop.prevent="setEntryAffixLevel(entry, 2, level)"
                      />
                    </div>
                    <span
                      class="attr-value"
                      :class="{ 'attr-value--full': entry.affix2_level === AFFIX_MAX_LEVEL[1] }"
                    >
                      +{{ entry.affix2_level }} / {{ AFFIX_MAX_LEVEL[1] }}
                    </span>
                    <span v-if="entry.affix2_level === AFFIX_MAX_LEVEL[1]" class="max-label"
                      >MAX</span
                    >
                  </div>

                  <div class="attr-control attr-control--indigo" @click.stop>
                    <span class="attr-label">技能属性</span>
                    <div aria-label="技能属性等级" class="attr-pips attr-pips--skill" role="group">
                      <span
                        v-for="level in skillLevelItems"
                        :key="`a3-${level}`"
                        :aria-label="`设置技能属性为 +${level}`"
                        class="pip"
                        :class="{
                          active: level <= entry.affix3_level,
                          'pip--max': entry.affix3_level === AFFIX_MAX_LEVEL[2],
                        }"
                        role="button"
                        tabindex="0"
                        @click.stop="setEntryAffixLevel(entry, 3, level)"
                        @keydown.enter.stop.prevent="setEntryAffixLevel(entry, 3, level)"
                        @keydown.space.stop.prevent="setEntryAffixLevel(entry, 3, level)"
                      />
                    </div>
                    <span
                      class="attr-value"
                      :class="{ 'attr-value--full': entry.affix3_level === AFFIX_MAX_LEVEL[2] }"
                    >
                      +{{ entry.affix3_level }} / {{ AFFIX_MAX_LEVEL[2] }}
                    </span>
                    <span v-if="entry.affix3_level === AFFIX_MAX_LEVEL[2]" class="max-label"
                      >MAX</span
                    >
                  </div>
                </section>

                <section class="card-action-rail">
                  <v-tooltip text="计算此武器的刷取建议">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        class="matrix-action matrix-action--calc"
                        color="primary"
                        icon="mdi-calculator"
                        size="small"
                        variant="tonal"
                        @click.stop="computeSingle(entry)"
                      />
                    </template>
                  </v-tooltip>
                  <v-tooltip text="移除此武器">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        class="matrix-action matrix-action--delete"
                        color="error"
                        icon="mdi-delete-outline"
                        size="small"
                        variant="tonal"
                        @click.stop="removeEntry(index)"
                      />
                    </template>
                  </v-tooltip>
                </section>
              </div>
            </v-card-text>
          </v-card>

          <div v-if="filteredMatrixEntries.length === 0" class="text-center py-6">
            <v-icon class="mb-2" color="medium-emphasis" size="48">mdi-diamond-outline</v-icon>
            <div class="text-medium-emphasis">尚未添加任何武器，点击下方按钮开始配置</div>
          </div>

          <v-btn
            class="mt-2"
            color="primary"
            prepend-icon="mdi-plus"
            variant="flat"
            @click="showAddWeaponDialog = true"
          >
            添加武器
          </v-btn>
          <v-btn
            class="mt-2 ml-2"
            color="secondary"
            prepend-icon="mdi-image-outline"
            variant="tonal"
            @click="showExportDialog = true"
          >
            导出为图片
          </v-btn>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Farming Recommendations -->
      <v-expansion-panel :value="2">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-calculator</v-icon>
          刷取建议
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <!-- 目标属性：卡片式布局，横条 pip 选择 -->
          <section class="attr-grid target-attr-grid mb-4">
            <div v-for="slot in targetSlots" :key="slot.key" class="attr-card">
              <div class="attr-card-header">
                <span class="attr-card-label">{{ slot.label }}</span>
                <span class="attr-card-value" :class="{ max: slot.get() === slot.maxLevel }">
                  +{{ slot.get() }} / {{ slot.maxLevel }}
                  <span v-if="slot.get() === slot.maxLevel" class="max-badge">MAX</span>
                </span>
              </div>
              <div :aria-label="`${slot.label}等级`" class="attr-pip-row" role="group">
                <span
                  v-for="level in slot.levels"
                  :key="level"
                  :aria-label="`设置${slot.label}目标为 +${level}`"
                  class="attr-pip"
                  :class="[`attr-pip--${slot.color}`, { active: level <= slot.get() }]"
                  role="button"
                  tabindex="0"
                  @click="slot.set(level)"
                  @keydown.enter.prevent="slot.set(level)"
                  @keydown.space.prevent="slot.set(level)"
                />
              </div>
            </div>
          </section>

          <v-btn
            class="mb-4"
            color="primary"
            :loading="computing"
            prepend-icon="mdi-calculator"
            variant="flat"
            @click="computeAll"
          >
            计算所有武器的刷取建议
          </v-btn>

          <v-btn
            v-if="recommendations.length > 0"
            class="mb-4 ml-2"
            color="success"
            prepend-icon="mdi-map-search"
            variant="flat"
            @click="navigateToPlanner()"
          >
            查看最优刷取方案
          </v-btn>

          <v-alert v-if="recommendations.length === 0" border="start" type="info" variant="tonal">
            请先添加武器到宝藏基质配置，然后点击「计算所有武器的刷取建议」。
          </v-alert>

          <!-- 星级筛选 & 排序切换 -->
          <div v-if="recommendations.length > 0" class="d-flex align-center flex-wrap gap-2 mb-4">
            <span class="text-body-2 text-medium-emphasis">筛选：</span>
            <v-chip-group v-model="recSelectedRarities" column multiple>
              <v-chip color="primary" filter size="small" value="3" variant="outlined"> 3★ </v-chip>
              <v-chip color="primary" filter size="small" value="4" variant="outlined"> 4★ </v-chip>
              <v-chip color="primary" filter size="small" value="5" variant="outlined"> 5★ </v-chip>
              <v-chip color="primary" filter size="small" value="6" variant="outlined"> 6★ </v-chip>
              <v-chip color="primary" filter size="small" value="custom" variant="outlined">
                自定义
              </v-chip>
            </v-chip-group>
            <v-btn
              :prepend-icon="
                recSortMode === 'runs'
                  ? 'mdi-sort-numeric-ascending'
                  : recRarityDesc
                    ? 'mdi-sort-descending'
                    : 'mdi-sort-ascending'
              "
              size="small"
              variant="tonal"
              @click="toggleRecSort"
            >
              {{ recSortMode === 'runs' ? '按刷取次数' : '按等级' }}
            </v-btn>
          </div>

          <v-card
            v-for="rec in sortedRecommendations"
            :key="rec.weapon_id"
            class="mb-4 rec-card"
            variant="outlined"
          >
            <v-card-item class="rec-card-top">
              <template #prepend>
                <custom-stat-icon
                  v-if="isCustomEntry(rec.weapon_id)"
                  hide-name
                  :name="getCustomStatName(rec.weapon_id, customStats)"
                  :skill-stat-id="getCustomStatSkillId(rec.weapon_id, customStats)"
                  small
                />
                <item-icon v-else class="weapon-icon-small" :item-id="rec.weapon_id" />
              </template>
              <v-card-title>{{
                isCustomEntry(rec.weapon_id)
                  ? getCustomStatName(rec.weapon_id, customStats)
                  : rec.weapon_name
              }}</v-card-title>
              <v-card-subtitle class="weapon-progress">
                当前: +{{ rec.current_levels[0] }} / +{{ rec.current_levels[1] }} / +{{
                  rec.current_levels[2]
                }}
                <span class="arrow">→</span>
                目标:
                <span class="target"
                  >+{{ rec.target_levels[0] }} / +{{ rec.target_levels[1] }} / +{{
                    rec.target_levels[2]
                  }}</span
                >
              </v-card-subtitle>
              <template #append>
                <div class="farming-badge">
                  <span class="farming-badge-count">{{
                    Math.ceil(getAdjustedStats(rec).totalRuns)
                  }}</span>
                  <span class="farming-badge-label">刷取次数</span>
                </div>
              </template>
            </v-card-item>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col v-for="slot in recSlots" :key="slot.index" cols="12" md="4">
                  <v-list density="compact">
                    <v-list-subheader>
                      <span class="steps-col-dot" :class="`steps-col-dot--${slot.color}`" />
                      {{ slot.label }}
                    </v-list-subheader>
                    <v-list-item
                      v-for="step in rec.affix_results[slot.index]?.steps"
                      :key="`a${slot.index}-` + step.from_level"
                      class="rec-step-row"
                      :class="{
                        'bg-success-lighten-5': isUsingGrease(
                          rec.weapon_id,
                          slot.index,
                          step.from_level,
                        ),
                      }"
                      density="compact"
                      style="cursor: pointer"
                      @click="toggleUseGrease(rec.weapon_id, slot.index, step.from_level)"
                    >
                      <v-list-item-title>
                        <div class="d-flex align-center ga-2">
                          <span
                            :aria-label="`${step.to_level}/${slot.maxLevel} 级`"
                            class="rec-step-pips"
                            :class="`rec-step-pips--${slot.color}`"
                          >
                            <span
                              v-for="p in slot.maxLevel"
                              :key="p"
                              class="rec-step-pip"
                              :class="{ active: p <= step.to_level }"
                            />
                          </span>
                          <span class="text-body-2"
                            >+{{ step.from_level }} → +{{ step.to_level }}</span
                          >
                        </div>
                      </v-list-item-title>
                      <template #append>
                        <v-chip
                          :color="
                            isUsingGrease(rec.weapon_id, slot.index, step.from_level)
                              ? 'success'
                              : undefined
                          "
                          size="x-small"
                          :variant="
                            isUsingGrease(rec.weapon_id, slot.index, step.from_level)
                              ? 'flat'
                              : 'tonal'
                          "
                        >
                          {{
                            isUsingGrease(rec.weapon_id, slot.index, step.from_level)
                              ? '100%'
                              : (step.success_prob * 100).toFixed(1) + '%'
                          }}
                        </v-chip>
                        <span class="text-caption ml-2">
                          {{
                            isUsingGrease(rec.weapon_id, slot.index, step.from_level)
                              ? `冷却脂 ${step.grease_threshold}`
                              : `期望 ${step.expected_attempts.toFixed(1)} 次`
                          }}
                        </span>
                      </template>
                    </v-list-item>
                    <v-list-item
                      v-if="rec.affix_results[slot.index]?.steps.length === 0"
                      density="compact"
                    >
                      <v-list-item-title class="text-medium-emphasis">
                        <v-icon class="mr-1" color="success" size="small">mdi-check</v-icon>
                        已达标
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-col>
              </v-row>
              <v-divider class="my-2" />
              <div class="d-flex flex-wrap align-center justify-space-between ga-2">
                <div class="d-flex flex-wrap ga-4 text-caption">
                  <div class="d-flex align-center">
                    <v-icon class="mr-1" color="primary" size="small">mdi-diamond-stone</v-icon>
                    <strong>期望消耗无暇基质:</strong>&nbsp;{{
                      getAdjustedStats(rec).totalEssences
                    }}
                    个
                  </div>
                  <div class="d-flex align-center">
                    <v-icon class="mr-1" color="success" size="small">mdi-arrow-up-bold</v-icon>
                    <strong>期望获得冷却脂:</strong>&nbsp;
                    {{ getAdjustedStats(rec).totalGreaseGained }} 点
                  </div>
                  <div class="d-flex align-center">
                    <v-icon class="mr-1" color="warning" size="small">mdi-arrow-down-bold</v-icon>
                    <strong>消耗冷却脂:</strong>&nbsp;
                    {{ getAdjustedStats(rec).totalGreaseUsed }} 点
                  </div>
                </div>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-map-search"
                  size="small"
                  variant="tonal"
                  @click="navigateToPlanner()"
                >
                  查看最优刷取方案
                </v-btn>
              </div>
            </v-card-text>
          </v-card>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Add Weapon Dialog -->
    <v-dialog v-model="showAddWeaponDialog" max-width="800">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-sword</v-icon>
          选择武器
        </v-card-title>
        <v-card-text>
          <v-text-field
            id="treasure-matrix-weapon-search"
            v-model="weaponSearch"
            class="mb-4"
            clearable
            density="compact"
            hide-details
            label="搜索武器名称..."
            name="treasure-matrix-weapon-search"
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
          />
          <!-- 自定义基质区段 -->
          <template v-if="customMatrixEntries.length > 0">
            <h4 class="mt-4 mb-2 d-flex align-center">
              <img v-if="essenceBgSrc" alt="" class="essence-icon-small me-2" :src="essenceBgSrc" />
              自定义基质
            </h4>
            <div class="weapon-grid">
              <div
                v-for="entry in customMatrixEntries"
                :key="entry.syntheticId"
                class="weapon-item"
                @click="onAddCustomStat(entry.index)"
              >
                <custom-stat-icon :name="entry.displayName" :skill-stat-id="entry.skillStatId" />
              </div>
            </div>
          </template>
          <template v-for="wType in weaponTypes" :key="wType.id">
            <h4 class="mt-4 mb-2 d-flex align-center">
              <img :alt="wType.name" class="group-icon me-2" :src="wType.iconUrl" />
              {{ wType.name }}
            </h4>
            <div class="weapon-grid">
              <div
                v-for="weaponId in filteredWeaponIds(wType.weaponIds)"
                :key="weaponId"
                class="weapon-item"
                @click="onAddWeapon(weaponId)"
              >
                <item-icon :item-id="weaponId" show-item-name />
              </div>
            </div>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showAddWeaponDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 导出为图片弹窗 -->
    <matrix-export-dialog v-model="showExportDialog" />

    <!-- 回到顶部按钮 -->
    <back-to-top />
  </v-container>
</template>

<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BackToTop from '@/components/BackToTop.vue'
import CustomStatIcon from '@/components/CustomStatIcon.vue'
import ItemIcon from '@/components/ItemIcon.vue'
import MatrixExportDialog from '@/components/MatrixExportDialog.vue'
import WeaponOverview from '@/components/WeaponOverview.vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { type TreasureMatrixEntry, useProfiles } from '@/composables/useProfiles'
import { useRarityFilters } from '@/composables/useRarityFilters'
import { AFFIX_MAX_LEVEL, useWeaponStats } from '@/composables/useWeaponStats'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  fallbackCustomStatName,
  findCustomStat,
  getCustomStatName,
  getCustomStatSkillId,
  getGemTagName,
  getStatsForWeapon,
  toCustomStatId,
} from '@/utils/gameData/weapon'
import { safeLoadJson, safeRemoveJson, safeSetJson } from '@/utils/safeStorage'

const router = useRouter()

const {
  activeProfileName,
  treasureMatrix,
  fetchProfiles,
  updateTreasureMatrix,
  addTreasureMatrixEntry,
  removeTreasureMatrixEntry,
  getBatchFarmingRecommendations,
} = useProfiles()
const { selectedRarities } = useRarityFilters()
const { customStats, customMatrixEntries, fetchCustomStats } = useCustomStats()
const { isCustomEntry } = useWeaponStats()

const { weaponsMap, weaponTypes, matrixIcons } = useStaticData()

// 底板图片路径
const essenceBgSrc = computed(() => matrixIcons.value.essenceBg)

const showAddWeaponDialog = ref(false)
const showExportDialog = ref(false)
const weaponSearch = ref('')
const computing = ref(false)

// --- 自定义基质相关 ---
// customStats / customMatrixEntries / fetchCustomStats 统一走 useCustomStats 的
// 模块级单例：此前这里另存了一份副本，在别处增删自定义基质后本页不会同步。

/** 添加自定义基质条目到宝藏基质配置 */
async function onAddCustomStat(index: number) {
  const stat = customStats.value[index]
  if (!stat) return
  const syntheticId = toCustomStatId(stat)
  // 检查是否已添加
  if (matrixEntries.value.some((e) => e.weapon_id === syntheticId)) return
  try {
    await addTreasureMatrixEntry({
      weapon_id: syntheticId,
      weapon_name: stat.name || fallbackCustomStatName(index),
      affix1_level: 1,
      affix2_level: 1,
      affix3_level: 1,
    })
    showAddWeaponDialog.value = false
  } catch {
    // toast 已由 _handleError 统一弹出，此处不再重复。
  }
}

const targetAffix1 = ref(6)
const targetAffix2 = ref(6)
const targetAffix3 = ref(3)

// AFFIX_MAX_LEVEL 由 useWeaponStats 统一导出，避免同一常量在多处各写一份
const affixLevelItems = [1, 2, 3, 4, 5, 6]
const skillLevelItems = [1, 2, 3]

interface Recommendation {
  weapon_id: string
  weapon_name: string
  current_levels: [number, number, number]
  target_levels: [number, number, number]
  total_expected_runs: number
  total_expected_essences: number
  affix_results: Array<{
    affix_name: string
    current_level: number
    target_level: number
    expected_attempts: number
    expected_essences_consumed: number
    expected_grease_gained: number
    expected_grease_used: number
    steps: Array<{
      from_level: number
      to_level: number
      success_prob: number
      grease_threshold: number
      expected_attempts: number
      expected_essences: number
      expected_grease_gained: number
      expected_grease_used: number
    }>
  }>
}

// 缓存 key 绑定到账号，避免跨账号数据污染
const recommendationsKey = computed(
  () => `treasureMatrixRecommendations:${activeProfileName.value}`,
)
const frozenOrderKey = computed(() => `treasureMatrixFrozenOrder:${activeProfileName.value}`)

const recommendations = ref<Recommendation[]>([])
let saveRecommendationsTimer: number | undefined
let saveFrozenOrderTimer: number | undefined

// 跟踪每个武器的每个步骤是否使用冷却脂
// 格式: { weaponId: { 'affixIndex-fromLevel': boolean } }
const useGreaseForSteps = ref<Record<string, Record<string, boolean>>>({})

// 排序后的推荐列表：初始排序后保持稳定，用户切换冷却脂时不重新排序
const frozenSortOrder = ref<string[] | null>(null)

// 刷取建议区域的星级筛选（独立于宝藏基质配置的筛选）
const recSelectedRarities = ref<string[]>(['custom', '6', '5', '4', '3'])
// 刷取建议排序模式：'runs' = 按刷取次数(默认), 'level' = 按稀有度
const recSortMode = ref<'runs' | 'level'>('runs')
// 稀有度排序方向：true = 高稀有度在前（6★ → 3★），false = 反向。
// 原名 recSortAsc 与实际行为相反（true 走的是降序分支），已按实际语义更名。
const recRarityDesc = ref(true)

function toggleRecSort() {
  if (recSortMode.value === 'runs') {
    recSortMode.value = 'level'
    recRarityDesc.value = true
  } else if (recRarityDesc.value) {
    recRarityDesc.value = false
  } else {
    recSortMode.value = 'runs'
  }
}

// 账号切换时重新加载缓存
watch(
  activeProfileName,
  () => {
    recommendations.value = safeLoadJson<Recommendation[]>(recommendationsKey.value, [])
    frozenSortOrder.value = safeLoadJson<string[] | null>(frozenOrderKey.value, null)
  },
  { immediate: true },
)

// Keep cached recommendations as the only initially open panel to avoid mounting every panel on route enter.
const openedPanels = ref<number[]>([])

// 监听 recommendations 变化，更新面板状态和保存到 localStorage
watch(
  recommendations,
  (newValue) => {
    openedPanels.value = newValue.length > 0 ? [2] : [0, 1, 2]
    window.clearTimeout(saveRecommendationsTimer)
    saveRecommendationsTimer = window.setTimeout(() => {
      if (newValue.length > 0) {
        safeSetJson(recommendationsKey.value, newValue)
      } else {
        safeRemoveJson(recommendationsKey.value)
      }
    }, 300)
  },
  { deep: true },
)

// 保存冻结的排序顺序到 localStorage
watch(
  frozenSortOrder,
  (newValue) => {
    window.clearTimeout(saveFrozenOrderTimer)
    saveFrozenOrderTimer = window.setTimeout(() => {
      if (newValue) {
        safeSetJson(frozenOrderKey.value, newValue)
      } else {
        safeRemoveJson(frozenOrderKey.value)
      }
    }, 300)
  },
  { deep: true },
)

onUnmounted(() => {
  window.clearTimeout(saveRecommendationsTimer)
  window.clearTimeout(saveFrozenOrderTimer)
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
})

// 监听 recommendations 变化，更新冻结顺序
watch(
  recommendations,
  (newRecommendations: Recommendation[]) => {
    const sorted = newRecommendations.toSorted((a: Recommendation, b: Recommendation) => {
      const aRuns = Math.ceil(a.total_expected_runs)
      const bRuns = Math.ceil(b.total_expected_runs)

      // 本身不需要刷取的武器置底
      if (aRuns === 0 && bRuns !== 0) return 1
      if (aRuns !== 0 && bRuns === 0) return -1

      // 按原始刷取次数升序排序
      return aRuns - bRuns
    })

    const currentIds = sorted.map((rec: Recommendation) => rec.weapon_id).join(',')

    // 如果还没有冻结顺序，或者是全新的推荐列表，则冻结
    if (frozenSortOrder.value === null || frozenSortOrder.value.join(',') !== currentIds) {
      frozenSortOrder.value = sorted.map((rec: Recommendation) => rec.weapon_id)
    }
  },
  { deep: true },
)

const sortedRecommendations = computed(() => {
  // 星级筛选
  const filtered = recommendations.value.filter((rec) => {
    if (isCustomEntry(rec.weapon_id)) {
      return recSelectedRarities.value.includes('custom')
    }
    const rarity = getWeaponRarity(rec.weapon_id)
    if (rarity === null) return false
    return recSelectedRarities.value.includes(String(rarity))
  })

  if (recSortMode.value === 'runs') {
    // 按刷取次数排序：使用冻结顺序或按刷取次数升序
    if (frozenSortOrder.value) {
      const orderMap = new Map(frozenSortOrder.value.map((id, idx) => [id, idx]))
      return filtered.toSorted((a, b) => {
        // 冻结顺序里没有的条目排到末尾：默认 0 会让新出现的武器凭空跳到最前
        return (
          (orderMap.get(a.weapon_id) ?? Number.POSITIVE_INFINITY) -
          (orderMap.get(b.weapon_id) ?? Number.POSITIVE_INFINITY)
        )
      })
    }
    return filtered.toSorted((a, b) => a.total_expected_runs - b.total_expected_runs)
  }

  // 按稀有度排序：自定义基质按 6★ 与普通武器一同排序（6★ → 3★ 或反向）
  return filtered.toSorted((a, b) => {
    const aRarity = getWeaponRarity(a.weapon_id) ?? 0
    const bRarity = getWeaponRarity(b.weapon_id) ?? 0
    return recRarityDesc.value ? bRarity - aRarity : aRarity - bRarity
  })
})

const showMaxedWeapons = ref(false)

const matrixEntries = computed({
  get: () => treasureMatrix.value,
  set: (val) => {
    updateTreasureMatrix(val)
  },
})

const filteredMatrixEntries = computed(() => {
  let entries = matrixEntries.value

  // 过滤稀有度（自定义条目按 6★ 处理）
  entries = entries.filter((entry) => {
    if (isCustomEntry(entry.weapon_id)) {
      return selectedRarities.value.includes('custom')
    }
    const weapon = weaponsMap.value.get(entry.weapon_id)
    if (!weapon) return false
    return selectedRarities.value.includes(String(weapon.rarity))
  })

  // 过滤满级武器
  if (!showMaxedWeapons.value) {
    entries = entries.filter(
      (entry) =>
        !(
          entry.affix1_level === AFFIX_MAX_LEVEL[0] &&
          entry.affix2_level === AFFIX_MAX_LEVEL[1] &&
          entry.affix3_level === AFFIX_MAX_LEVEL[2]
        ),
    )
  }

  // 按优先级降序排序，优先级相同时按稀有度降序排序（6★ -> 3★）
  return entries.toSorted((a, b) => {
    // 自定义条目始终排在最前面
    const aCustom = isCustomEntry(a.weapon_id) ? 1 : 0
    const bCustom = isCustomEntry(b.weapon_id) ? 1 : 0
    if (aCustom !== bCustom) return bCustom - aCustom

    const pa = a.priority || 0
    const pb = b.priority || 0
    if (pa !== pb) return pb - pa
    const wa = weaponsMap.value.get(a.weapon_id)
    const wb = weaponsMap.value.get(b.weapon_id)
    if (wa && wb) return wb.rarity - wa.rarity
    return 0
  })
})

/**
 * 获取武器的属性名称列表
 * 自定义条目从 customStats 配置中读取
 */
function getWeaponTraitNames(weaponId: string): string[] {
  // 自定义条目：从配置中读取属性（兼容新旧格式 ID）
  if (isCustomEntry(weaponId)) {
    const found = findCustomStat(weaponId, customStats.value)
    if (!found) return ['自定义基质']
    const stat = found.stat
    const parts: string[] = []
    if (stat.attribute) parts.push(getGemTagName(stat.attribute))
    if (stat.secondary) parts.push(getGemTagName(stat.secondary))
    if (stat.skill) parts.push(getGemTagName(stat.skill))
    return parts.length > 0 ? parts : ['自定义基质']
  }

  const stats = getStatsForWeapon(weaponId)
  const parts: string[] = []
  if (stats.attribute) parts.push(getGemTagName(stats.attribute))
  if (stats.secondary) parts.push(getGemTagName(stats.secondary))
  if (stats.skill) parts.push(getGemTagName(stats.skill))
  return parts.length > 0 ? parts : ['无属性']
}

/**
 * 获取武器稀有度
 * 自定义条目默认为 6★
 */
function getWeaponRarity(weaponId: string): number | null {
  if (isCustomEntry(weaponId)) return 6
  return weaponsMap.value.get(weaponId)?.rarity ?? null
}

function getWeaponTierClass(weaponId: string): string {
  const rarity = getWeaponRarity(weaponId)
  return rarity ? `tier-${rarity}` : ''
}

function getWeaponRarityText(weaponId: string): string {
  const rarity = getWeaponRarity(weaponId)
  return rarity ? `${rarity}★` : '??'
}

function filteredWeaponIds(weaponIds: string[]): string[] {
  if (!weaponSearch.value.trim()) return weaponIds
  const search = weaponSearch.value.trim().toLowerCase()
  return weaponIds.filter((id) => {
    const weapon = weaponsMap.value.get(id)
    return weapon && weapon.name.toLowerCase().includes(search)
  })
}

async function onAddWeapon(weaponId: string) {
  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon) return

  // Check if already exists
  const existing = matrixEntries.value.find((e) => e.weapon_id === weaponId)
  if (existing) {
    showAddWeaponDialog.value = false
    return
  }

  await addTreasureMatrixEntry({
    weapon_id: weaponId,
    weapon_name: weapon.name,
    affix1_level: 1,
    affix2_level: 1,
    affix3_level: 1,
    include_in_calculation: true,
  })
  showAddWeaponDialog.value = false
}

async function removeEntry(index: number) {
  const entry = filteredMatrixEntries.value[index]
  if (entry) {
    await removeTreasureMatrixEntry(entry.weapon_id)
  }
}

// 刷取建议卡片内三个属性槽位的展示配置（pip 总量：基础/附加 6 格，技能 3 格）
// 颜色与配置区 attr-control 保持一致：primary / teal / indigo
const recSlots = [
  { index: 0, label: '基础属性', color: 'primary', maxLevel: AFFIX_MAX_LEVEL[0] },
  { index: 1, label: '附加属性', color: 'teal', maxLevel: AFFIX_MAX_LEVEL[1] },
  { index: 2, label: '技能属性', color: 'indigo', maxLevel: AFFIX_MAX_LEVEL[2] },
]

// 目标属性卡片配置（attr-card 布局）
const targetSlots = [
  {
    key: 'affix1',
    label: '目标基础属性',
    color: 'primary',
    maxLevel: AFFIX_MAX_LEVEL[0],
    levels: affixLevelItems,
    get: () => targetAffix1.value,
    set: (v: number) => {
      targetAffix1.value = v
    },
  },
  {
    key: 'affix2',
    label: '目标附加属性',
    color: 'teal',
    maxLevel: AFFIX_MAX_LEVEL[1],
    levels: affixLevelItems,
    get: () => targetAffix2.value,
    set: (v: number) => {
      targetAffix2.value = v
    },
  },
  {
    key: 'affix3',
    label: '目标技能属性',
    color: 'indigo',
    maxLevel: AFFIX_MAX_LEVEL[2],
    levels: skillLevelItems,
    get: () => targetAffix3.value,
    set: (v: number) => {
      targetAffix3.value = v
    },
  },
]

function toggleUseGrease(weaponId: string, affixIndex: number, fromLevel: number) {
  const key = `${affixIndex}-${fromLevel}`
  if (!useGreaseForSteps.value[weaponId]) {
    useGreaseForSteps.value[weaponId] = {}
  }
  useGreaseForSteps.value[weaponId][key] = !useGreaseForSteps.value[weaponId][key]
}

function isUsingGrease(weaponId: string, affixIndex: number, fromLevel: number): boolean {
  return useGreaseForSteps.value[weaponId]?.[`${affixIndex}-${fromLevel}`] || false
}

function calculateAdjustedStats(rec: Recommendation) {
  let totalEssences = 0
  let totalGreaseGained = 0
  let totalGreaseUsed = 0

  for (const [affixIndex, affixResult] of rec.affix_results.entries()) {
    for (const step of affixResult.steps) {
      const usingGrease = isUsingGrease(rec.weapon_id, affixIndex, step.from_level)
      if (usingGrease) {
        // 使用冷却脂：不消耗基质，不获得冷却脂，但要消耗固定冷却脂
        totalGreaseUsed += step.grease_threshold
      } else {
        // 不使用冷却脂：正常计算
        // 每个步骤的基质消耗向上取整
        totalEssences += Math.ceil(step.expected_essences)
        // 冷却脂获得取最接近的10的倍数
        totalGreaseGained += Math.round(step.expected_grease_gained / 10) * 10
        // 冷却脂消耗（正常升级时为0）
        totalGreaseUsed += Math.round(step.expected_grease_used / 10) * 10
      }
    }
  }

  // 计算刷取次数：每次刷取掉落 3 个无暇基质
  const ESSENCES_PER_RUN = 3
  const totalRuns = totalEssences / ESSENCES_PER_RUN

  return {
    totalEssences,
    totalGreaseGained,
    totalGreaseUsed,
    totalRuns,
  }
}

const adjustedStatsByWeaponId = computed(() => {
  const result = new Map<string, ReturnType<typeof calculateAdjustedStats>>()
  for (const rec of recommendations.value) {
    result.set(rec.weapon_id, calculateAdjustedStats(rec))
  }
  return result
})

function getAdjustedStats(rec: Recommendation) {
  // 模板中同一推荐项会多次读取统计值，集中缓存可避免每次渲染重复遍历升级步骤。
  return adjustedStatsByWeaponId.value.get(rec.weapon_id) ?? calculateAdjustedStats(rec)
}

function persistMatrix(entries: TreasureMatrixEntry[]) {
  void updateTreasureMatrix(entries).catch(() => {
    // 错误已由 useProfiles 的 lastError/toast 提示；本地条目已被就地修改，
    // 重新拉取后端状态覆盖，避免界面停留在与后端不一致的"假修改"上。
    void fetchProfiles().catch(() => {})
  })
}

function toggleIncludeInCalculation(entry: TreasureMatrixEntry) {
  entry.include_in_calculation = !entry.include_in_calculation
  persistMatrix([...matrixEntries.value])
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function setEntryAffixLevel(entry: TreasureMatrixEntry, affixIndex: 1 | 2 | 3, level: number) {
  if (affixIndex === 1) entry.affix1_level = level
  if (affixIndex === 2) entry.affix2_level = level
  if (affixIndex === 3) entry.affix3_level = level
  onEntryChange()
}

function onEntryChange() {
  // 检查是否有武器达到满级（6/6/3），自动取消勾选
  for (const entry of matrixEntries.value) {
    if (
      entry.affix1_level === AFFIX_MAX_LEVEL[0] &&
      entry.affix2_level === AFFIX_MAX_LEVEL[1] &&
      entry.affix3_level === AFFIX_MAX_LEVEL[2] &&
      entry.include_in_calculation !== false
    ) {
      entry.include_in_calculation = false
    }
  }

  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    persistMatrix([...matrixEntries.value])
    debounceTimer = null
  }, 500)
}

async function computeSingle(entry: TreasureMatrixEntry) {
  computing.value = true
  try {
    const results = await getBatchFarmingRecommendations([
      {
        weapon_id: entry.weapon_id,
        current_levels: [entry.affix1_level, entry.affix2_level, entry.affix3_level],
        target_levels: [targetAffix1.value, targetAffix2.value, targetAffix3.value],
      },
    ])
    if (results.length > 0) {
      frozenSortOrder.value = null
      recommendations.value = results

      // 计算完成后，折叠武器总览（value=0）和宝藏基质配置面板（value=1）
      // 只保留刷取建议（value=2）展开
      openedPanels.value = [2]
    }
  } finally {
    computing.value = false
  }
}

async function computeAll() {
  if (matrixEntries.value.length === 0) return
  computing.value = true
  try {
    // 只计算勾选了"参与计算"的武器，并且在选中的稀有度范围内
    const items = matrixEntries.value
      .filter((entry) => {
        // 必须勾选了"参与计算"
        if (entry.include_in_calculation === false) return false

        // 自定义基质始终参与计算
        if (isCustomEntry(entry.weapon_id)) return true

        // 必须在选中的稀有度范围内
        const weapon = weaponsMap.value.get(entry.weapon_id)
        if (!weapon) return false
        return selectedRarities.value.includes(String(weapon.rarity))
      })
      .map((entry) => ({
        weapon_id: entry.weapon_id,
        current_levels: [entry.affix1_level, entry.affix2_level, entry.affix3_level] as [
          number,
          number,
          number,
        ],
        target_levels: [targetAffix1.value, targetAffix2.value, targetAffix3.value] as [
          number,
          number,
          number,
        ],
      }))
    const results = await getBatchFarmingRecommendations(items)
    // Sort by expected runs (ascending - least runs first)
    const sortedResults = results.toSorted(
      (a: Recommendation, b: Recommendation) => a.total_expected_runs - b.total_expected_runs,
    )
    frozenSortOrder.value = null
    recommendations.value = sortedResults

    // 计算完成后，折叠武器总览（value=0）和宝藏基质配置面板（value=1）
    // 只保留刷取建议（value=2）展开
    openedPanels.value = [2]
  } finally {
    computing.value = false
  }
}

/**
 * 跳转到基质规划页面，开启不使用预刻券模式。
 * 不传递特定武器，让用户根据未获得数量排序后的方案自行选择。
 */
function navigateToPlanner() {
  router.push({
    name: 'matrix-planner',
    query: { clear: 'true', noPrecraft: 'true' },
  })
  // 滚动到页面顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  fetchProfiles()
  fetchCustomStats()
})
</script>

<style scoped lang="scss">
$weapon-icon-size: clamp(2.5rem, 14vw, 5rem);
// 附加/技能属性槽位的主题色（与 attr-control、pip、步骤列圆点、步骤 pip 共用）
$attr-teal: #48a9a6;
$attr-indigo: #5c6bc0;

.treasure-matrix-page {
  .entry-card {
    position: relative;
    overflow: hidden;
    border-color: rgba(var(--v-border-color), 0.12);
    border-radius: 18px;
    background:
      linear-gradient(135deg, rgba(var(--v-theme-surface), 1), rgba(var(--v-theme-primary), 0.035)),
      rgb(var(--v-theme-surface));
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    transition:
      transform 0.18s ease,
      box-shadow 0.18s ease,
      border-color 0.18s ease,
      opacity 0.18s ease,
      filter 0.18s ease;

    &:hover {
      transform: translateY(-1px);
      border-color: rgba(var(--v-theme-primary), 0.35);
      box-shadow:
        0 12px 28px rgba(15, 23, 42, 0.09),
        0 2px 8px rgba(15, 23, 42, 0.06) !important;
    }

    &.entry-card--muted {
      opacity: 0.58;
      filter: grayscale(0.25);

      &:hover {
        opacity: 0.82;
        filter: grayscale(0);
      }
    }

    .clickable-card {
      cursor: pointer;
      user-select: none;
    }

    .matrix-card-body {
      display: flex;
      align-items: stretch;
      min-height: 76px;
    }

    .weapon-identity {
      position: relative;
      display: flex;
      flex: 0 0 270px;
      align-items: center;
      gap: 12px;
      padding: 0 20px;
      background: linear-gradient(
        135deg,
        rgba(var(--v-theme-surface), 0.98),
        rgba(var(--v-theme-primary), 0.06)
      );
      border-right: 1px solid rgba(var(--v-border-color), 0.12);

      &::after {
        content: '';
        position: absolute;
        top: 18px;
        right: 0;
        bottom: 18px;
        width: 1px;
        background: linear-gradient(
          to bottom,
          transparent,
          rgba(var(--v-border-color), 0.28),
          transparent
        );
      }
    }

    .weapon-icon-wrap {
      position: relative;
      width: 46px;
      height: 46px;
      flex-shrink: 0;
      border: 2px solid rgba(var(--v-theme-primary), 0.35);
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(var(--v-theme-primary), 0.16);
    }

    .weapon-icon-wrap .weapon-icon-small {
      width: 100% !important;
      height: 100% !important;
      border-radius: 8px;
    }

    /* 自定义基质条目图标样式 */
    .weapon-icon-wrap.tier-6 {
      border-color: #ff5a36;
      box-shadow: 0 4px 14px rgba(255, 90, 54, 0.28);
    }

    .weapon-icon-wrap.tier-6 .weapon-tier {
      background: #ff5a36;
    }

    .weapon-icon-wrap.tier-5 {
      border-color: #ffb020;
      box-shadow: 0 4px 14px rgba(255, 176, 32, 0.28);
    }

    .weapon-icon-wrap.tier-5 .weapon-tier {
      background: #ffb020;
    }

    .weapon-icon-wrap.tier-4 {
      border-color: #8e5cff;
      box-shadow: 0 4px 14px rgba(142, 92, 255, 0.24);
    }

    .weapon-icon-wrap.tier-4 .weapon-tier {
      background: #8e5cff;
    }

    .weapon-icon-wrap.tier-3 {
      border-color: #2196f3;
      box-shadow: 0 4px 14px rgba(33, 150, 243, 0.22);
    }

    .weapon-icon-wrap.tier-3 .weapon-tier {
      background: #2196f3;
    }

    .weapon-tier {
      position: absolute;
      right: -8px;
      bottom: -7px;
      padding: 1px 6px;
      border-radius: 999px;
      color: #fff;
      background: rgba(15, 23, 42, 0.82);
      font-size: 0.625rem;
      font-weight: 800;
      line-height: 1.5;
      box-shadow: 0 2px 6px rgba(15, 23, 42, 0.2);
    }

    .weapon-info {
      min-width: 0;
      flex: 1;
    }

    .weapon-name {
      overflow: hidden;
      color: rgba(var(--v-theme-on-surface), 0.92);
      font-size: 0.95rem;
      font-weight: 800;
      line-height: 1.3;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .weapon-traits {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 0;
      margin-top: 4px;
      color: rgba(var(--v-theme-on-surface), 0.58);
      font-size: 0.75rem;
      line-height: 1.35;
    }

    .trait {
      white-space: nowrap;

      &::after {
        content: ' / ';
        opacity: 0.42;
      }

      &:last-child::after {
        display: none;
      }
    }

    .participation-chip {
      margin-top: 8px;
      font-weight: 700;
    }

    .attribute-section {
      display: flex;
      flex: 1;
      align-items: center;
      gap: 12px;
      padding: 8px 18px;
    }

    .attr-control {
      position: relative;
      display: flex;
      flex: 1;
      min-width: 118px;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      padding: 0 10px;
      border: 1px solid transparent;
      border-radius: 12px;
      transition:
        background 0.18s ease,
        border-color 0.18s ease,
        transform 0.18s ease;

      &:hover {
        transform: translateY(-1px);
        border-color: rgba(var(--v-border-color), 0.16);
        background: rgba(var(--v-theme-on-surface), 0.035);
      }
    }

    .attr-label {
      color: rgba(var(--v-theme-on-surface), 0.52);
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .attr-pips {
      display: flex;
      align-items: center;
      gap: 3px;
      min-height: 18px;
    }

    .pip {
      width: 8px;
      height: 17px;
      border-radius: 999px;
      background: rgba(var(--v-theme-on-surface), 0.12);
      cursor: pointer;
      transition:
        background 0.18s ease,
        box-shadow 0.18s ease,
        transform 0.18s ease;

      &:hover,
      &:focus-visible {
        outline: none;
        transform: translateY(-1px) scaleY(1.08);
      }
    }

    .attr-control--primary .pip.active {
      background: rgb(var(--v-theme-primary));
      box-shadow: 0 2px 7px rgba(var(--v-theme-primary), 0.32);
    }

    .attr-control--teal .pip.active {
      background: $attr-teal;
      box-shadow: 0 2px 7px rgba($attr-teal, 0.34);
    }

    .attr-control--indigo .pip.active {
      background: $attr-indigo;
      box-shadow: 0 2px 7px rgba($attr-indigo, 0.34);
    }

    .pip.pip--max.active {
      animation: matrixPipPulse 2.2s ease-in-out infinite;
    }

    .attr-value {
      color: rgba(var(--v-theme-on-surface), 0.68);
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.82rem;
      font-weight: 800;
    }

    .attr-value--full {
      color: rgb(var(--v-theme-primary));
    }

    .max-label {
      position: absolute;
      top: 8px;
      right: 8px;
      padding: 1px 6px;
      border-radius: 999px;
      color: rgb(var(--v-theme-primary));
      background: rgba(var(--v-theme-primary), 0.1);
      font-size: 0.62rem;
      font-weight: 900;
      letter-spacing: 0.04em;
    }

    .card-action-rail {
      display: flex;
      flex: 0 0 auto;
      flex-direction: column;
      justify-content: center;
      gap: 8px;
      padding: 10px 16px 10px 0;
    }

    .matrix-action {
      border-radius: 10px;
    }
  }

  @keyframes matrixPipPulse {
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

  @media (max-width: 900px) {
    .entry-card {
      .matrix-card-body {
        flex-direction: column;
      }

      .weapon-identity {
        flex: none;
        border-right: none;
        border-bottom: 1px solid rgba(var(--v-border-color), 0.12);

        &::after {
          display: none;
        }
      }

      .attribute-section {
        padding: 14px 16px;
      }

      .card-action-rail {
        flex-direction: row;
        justify-content: flex-end;
        padding: 0 16px 14px;
      }
    }
  }

  @media (max-width: 640px) {
    .entry-card {
      .weapon-identity {
        padding: 16px;
      }

      .attribute-section {
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
      }

      .attr-control {
        display: grid;
        grid-template-columns: 72px 1fr 104px;
        align-items: center;
        width: 100%;
      }

      .attr-pips {
        justify-content: center;
      }

      .max-label {
        top: 50%;
        right: 122px;
        transform: translateY(-50%);
      }
    }
  }

  // 目标属性卡片（attr-card 布局）
  .target-attr-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }

  .attr-card {
    padding: 16px;
    border: 1px solid rgba(var(--v-border-color), 0.12);
    border-radius: 12px;
    background: rgba(var(--v-theme-on-surface), 0);
    transition: border-color 0.18s ease;

    &:hover {
      border-color: rgba(var(--v-border-color), 0.3);
    }
  }

  .attr-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .attr-card-label {
    color: rgba(var(--v-theme-on-surface), 0.52);
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  .attr-card-value {
    color: rgba(var(--v-theme-on-surface), 0.68);
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    font-weight: 800;

    &.max {
      color: rgb(var(--v-theme-success));
    }
  }

  .max-badge {
    margin-left: 4px;
    color: rgb(var(--v-theme-success));
    font-size: 0.6rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .attr-pip-row {
    display: flex;
    gap: 6px;
  }

  .attr-pip {
    width: 28px;
    height: 10px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.12);
    cursor: pointer;
    transition:
      background 0.18s ease,
      box-shadow 0.18s ease,
      transform 0.18s ease;

    &:hover,
    &:focus-visible {
      outline: none;
      transform: scaleY(1.25);
    }
  }

  .attr-pip--primary.active {
    background: rgb(var(--v-theme-primary));
    box-shadow: 0 0 8px rgba(var(--v-theme-primary), 0.25);
  }

  .attr-pip--teal.active {
    background: $attr-teal;
    box-shadow: 0 0 8px rgba($attr-teal, 0.25);
  }

  .attr-pip--indigo.active {
    background: $attr-indigo;
    box-shadow: 0 0 8px rgba($attr-indigo, 0.25);
  }

  @media (max-width: 640px) {
    .target-attr-grid {
      grid-template-columns: 1fr;
    }
  }

  .rec-card {
    border-color: rgba(var(--v-border-color), 0.25);
    transition:
      transform 0.2s ease,
      box-shadow 0.2s ease;
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
    }
  }

  // 武器卡头部：当前等级灰 → 箭头主题色 → 目标等级亮绿
  .rec-card-top {
    padding: 20px;
  }

  // 刷取次数徽章（卡片式：大数字 + 小标签）
  .farming-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 0 5px;
    border: 1px solid rgba(var(--v-theme-warning), 0.25);
    border-radius: 10px;
    background: rgba(var(--v-theme-warning), 0.12);
    flex-shrink: 0;
  }

  .farming-badge-count {
    color: rgb(var(--v-theme-warning));
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.1;
  }

  .farming-badge-label {
    margin-top: 2px;
    color: rgba(var(--v-theme-on-surface), 0.55);
    font-size: 0.7rem;
    white-space: nowrap;
  }

  .weapon-progress {
    color: rgba(var(--v-theme-on-surface), 0.45);
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-weight: 800;

    .arrow {
      margin: 0 4px;
      color: rgb(var(--v-theme-primary));
    }

    .target {
      color: rgb(var(--v-theme-success));
    }
  }

  // 步骤列头圆点（颜色与 attr-control 一致：primary / teal / indigo）
  .steps-col-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    margin-right: 6px;
    border-radius: 50%;
    flex-shrink: 0;

    &--primary {
      background: rgb(var(--v-theme-primary));
    }

    &--teal {
      background: $attr-teal;
    }

    &--indigo {
      background: $attr-indigo;
    }
  }

  // 步骤行分隔线
  .rec-step-row {
    border-bottom: 1px solid rgba(var(--v-border-color), 0.08);

    &:last-child {
      border-bottom: none;
    }
  }

  // 刷取建议步骤的方形 pip 展示（仅展示，点击行只切换冷却脂，不改变 pip 亮暗）
  .rec-step-pips {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
  }

  .rec-step-pip {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background: rgba(var(--v-theme-on-surface), 0.12);
    transition:
      background 0.18s ease,
      box-shadow 0.18s ease;

    &.active {
      background: rgb(var(--v-theme-primary));
      box-shadow: 0 0 6px rgba(var(--v-theme-primary), 0.3);
    }
  }

  .rec-step-pips--teal .rec-step-pip.active {
    background: $attr-teal;
    box-shadow: 0 0 6px rgba($attr-teal, 0.3);
  }

  .rec-step-pips--indigo .rec-step-pip.active {
    background: $attr-indigo;
    box-shadow: 0 0 6px rgba($attr-indigo, 0.3);
  }
}

.group-icon {
  width: 1.5rem;
  height: 1.5rem;
  vertical-align: middle;
}

.weapon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, $weapon-icon-size);
  gap: calc($weapon-icon-size / 10);
}

.weapon-item {
  width: $weapon-icon-size;
  height: $weapon-icon-size;
  cursor: pointer;
  transition: transform 0.15s;
  border-radius: 6px;
  &:hover {
    transform: scale(1.1);
  }
}

.weapon-icon-small {
  width: 2.5rem !important;
  height: 2.5rem !important;
  display: inline-block;
  flex-shrink: 0;
}
</style>
