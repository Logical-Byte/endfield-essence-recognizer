<template>
  <v-container class="h-100 d-flex flex-column matrix-planner-page">
    <v-row>
      <!-- 左侧：最优刷取方案 -->
      <v-col cols="12" lg="6">
        <v-expansion-panels :model-value="[0]">
          <v-expansion-panel :value="0">
            <v-expansion-panel-title>
              <v-icon class="mr-2">mdi-map-search</v-icon>
              最优刷取方案
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!-- 不使用预刻券模式：上下布局 -->
              <template v-if="noPrecraftMode">
                <div v-if="displayedLocationChoices.length > 0">
                  <v-card
                    v-for="(choice, i) in displayedLocationChoices"
                    :key="`loc-${i}`"
                    class="mb-4 choice-card"
                    :class="{ 'choice-card--top': i === 0 }"
                    elevation="2"
                    rounded="lg"
                    variant="outlined"
                  >
                    <v-card-item class="py-3" :class="i === 0 ? 'bg-primary' : 'bg-info'">
                      <v-card-title class="text-h6 font-weight-bold d-flex align-center">
                        <v-icon v-if="i === 0" class="mr-2" size="small">mdi-trophy</v-icon>
                        方案 {{ i + 1 }}
                      </v-card-title>
                      <template #append>
                        <v-chip class="font-weight-bold" color="white" size="small" variant="flat">
                          {{ choice.unobtainedCount }} 把未获得武器
                        </v-chip>
                      </template>
                    </v-card-item>
                    <v-divider />
                    <v-card-text class="pt-4">
                      <!-- 刷取地点 -->
                      <div class="mb-4">
                        <div class="d-flex align-center mb-3">
                          <v-icon class="mr-2" color="primary" icon="mdi-map-marker" size="small" />
                          <span class="text-subtitle-1 font-weight-bold">刷取地点</span>
                        </div>
                        <div class="pl-1">
                          <v-chip color="info" label size="large" variant="flat">
                            <v-icon size="small" start>mdi-sword-cross</v-icon>
                            {{ getDisplayName(choice.battleName) }}
                          </v-chip>
                        </div>
                      </div>
                      <v-divider class="my-4" />
                      <!-- 可刷取的武器 -->
                      <div>
                        <div class="d-flex align-center mb-3">
                          <v-icon class="mr-2" color="primary" icon="mdi-sword" size="small" />
                          <span class="text-subtitle-1 font-weight-bold">可刷取的武器</span>
                        </div>
                        <div class="pl-1">
                          <div class="d-flex flex-wrap ga-2">
                            <div
                              v-for="weaponId in sortedWeaponIdsByObtained(choice.matchedWeaponIds)"
                              :key="weaponId"
                              class="weapon-item-small"
                              :class="{
                                'weapon-obtained': isWeaponObtained(weaponId),
                                'weapon-matched': selectedWeaponForLocation === weaponId,
                              }"
                            >
                              <!-- 武器悬浮面板：显示武器的三条基质属性 -->
                              <v-tooltip location="top" open-delay="0">
                                <template #activator="{ props }">
                                  <div v-bind="props" class="h-100">
                                    <custom-stat-icon
                                      v-if="isCustomStatId(weaponId)"
                                      :name="getCustomStatName(weaponId, customStats)"
                                      :skill-stat-id="getCustomStatSkillId(weaponId, customStats)"
                                      small
                                    />
                                    <template v-else>
                                      <item-icon :item-id="weaponId" show-item-name />
                                    </template>
                                  </div>
                                </template>
                                <span>{{ getWeaponTooltipText(weaponId) }}</span>
                              </v-tooltip>
                              <v-chip
                                v-if="isWeaponObtained(weaponId)"
                                class="obtained-badge"
                                color="success"
                                size="x-small"
                                variant="flat"
                              >
                                已获得
                              </v-chip>
                            </div>
                          </div>
                        </div>
                      </div>
                    </v-card-text>
                  </v-card>
                </div>
                <v-alert v-else border="start" type="info" variant="tonal">
                  <template v-if="noFarmingLocationSelected">
                    未勾选任何刷取地点，请在右侧「需求设定」中至少勾选一个。
                  </template>
                  <template v-else> 开启「不使用预刻券」模式后，将显示所有刷取地点。 </template>
                </v-alert>
              </template>
              <!-- 使用预刻券模式：左右布局 -->
              <template v-else>
                <div v-if="displayedBattleChoices.length > 0">
                  <v-card
                    v-for="(choice, i) in displayedBattleChoices"
                    :key="`battle-${i}`"
                    class="mb-4 choice-card"
                    :class="{ 'choice-card--top': i === 0 }"
                    elevation="2"
                    rounded="lg"
                    variant="outlined"
                  >
                    <v-card-item class="py-3" :class="i === 0 ? 'bg-primary' : 'bg-info'">
                      <v-card-title class="text-h6 font-weight-bold d-flex align-center">
                        <v-icon v-if="i === 0" class="mr-2" size="small">mdi-trophy</v-icon>
                        方案 {{ i + 1 }}
                      </v-card-title>
                      <template #append>
                        <v-chip class="font-weight-bold" color="white" size="small" variant="flat">
                          匹配 {{ getSelectedWeaponMatchCount(choice) }}/{{
                            getSelectedWeaponCount()
                          }}
                          把已选武器
                        </v-chip>
                      </template>
                    </v-card-item>
                    <v-divider />
                    <v-card-text class="pt-4">
                      <v-row>
                        <v-col cols="12" md="5">
                          <div class="d-flex align-center mb-3">
                            <v-icon
                              class="mr-2"
                              color="primary"
                              icon="mdi-map-marker"
                              size="small"
                            />
                            <span class="text-subtitle-1 font-weight-bold">刷取地点</span>
                          </div>
                          <div class="pl-1 mb-4">
                            <v-chip color="info" label size="large" variant="flat">
                              <v-icon size="small" start>mdi-sword-cross</v-icon>
                              {{ getDisplayName(choice.battleName) }}
                            </v-chip>
                          </div>
                          <div class="d-flex align-center mb-3">
                            <v-icon class="mr-2" color="primary" icon="mdi-tune" size="small" />
                            <span class="text-subtitle-1 font-weight-bold">预刻属性</span>
                          </div>
                          <div class="pl-1">
                            <div class="mb-3">
                              <div class="text-medium-emphasis mb-1">基础属性</div>
                              <div class="d-flex flex-wrap ga-2">
                                <v-chip
                                  v-for="attr in choice.selectedAttribute"
                                  :key="attr"
                                  color="primary"
                                  label
                                  size="small"
                                  variant="flat"
                                >
                                  {{ attr }}
                                </v-chip>
                              </div>
                            </div>
                            <div v-if="choice.selectedSecondary" class="mb-3">
                              <div class="text-medium-emphasis mb-1">附加属性</div>
                              <v-chip color="teal" label size="small" variant="flat">
                                {{ choice.selectedSecondary }}
                              </v-chip>
                            </div>
                            <div v-if="choice.selectedSkill" class="mb-3">
                              <div class="text-medium-emphasis mb-1">技能属性</div>
                              <v-chip color="blue" label size="small" variant="flat">
                                {{ choice.selectedSkill }}
                              </v-chip>
                            </div>
                          </div>
                        </v-col>
                        <v-divider class="hidden-sm-and-down" vertical />
                        <v-divider class="hidden-md-and-up my-4" />
                        <v-col cols="12" md="7">
                          <div class="pl-1">
                            <div class="mb-3">
                              <div class="text-medium-emphasis mb-1">满足的需求</div>
                              <div class="d-flex flex-wrap ga-2">
                                <div v-for="index in choice.matchedSelectedIndices" :key="index">
                                  <v-tooltip activator="parent" location="bottom">
                                    {{ getRequirementTooltip(index) }}
                                  </v-tooltip>
                                  <v-card class="pa-2" variant="tonal">
                                    <div class="text-center font-weight-bold text-caption">
                                      #{{ index + 1 }}
                                      {{ getEssenceStatDescription(requiredEssenceStats[index]!) }}
                                    </div>
                                  </v-card>
                                </div>
                              </div>
                            </div>
                            <div>
                              <div class="text-medium-emphasis mb-1">匹配的武器</div>
                              <div class="d-flex flex-wrap ga-2">
                                <div
                                  v-for="weaponId in sortedWeaponIds(choice.matchedWeaponIds)"
                                  :key="weaponId"
                                  class="weapon-item-small"
                                  :class="{
                                    'weapon-matched': isRequiredWeapon(weaponId),
                                    'weapon-obtained': isWeaponObtained(weaponId),
                                  }"
                                >
                                  <!-- 武器悬浮面板：显示武器的三条基质属性 -->
                                  <v-tooltip location="top" open-delay="0">
                                    <template #activator="{ props }">
                                      <div v-bind="props" class="h-100">
                                        <custom-stat-icon
                                          v-if="isCustomStatId(weaponId)"
                                          :name="getCustomStatName(weaponId, customStats)"
                                          :skill-stat-id="
                                            getCustomStatSkillId(weaponId, customStats)
                                          "
                                          small
                                        />
                                        <item-icon v-else :item-id="weaponId" show-item-name />
                                      </div>
                                    </template>
                                    <span>{{ getWeaponTooltipText(weaponId) }}</span>
                                  </v-tooltip>
                                  <v-chip
                                    v-if="isWeaponObtained(weaponId)"
                                    class="obtained-badge"
                                    color="success"
                                    size="x-small"
                                    variant="flat"
                                  >
                                    已获得
                                  </v-chip>
                                </div>
                              </div>
                            </div>
                          </div>
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>
                </div>
                <v-alert v-else border="start" type="info" variant="tonal">
                  <template v-if="noFarmingLocationSelected">
                    未勾选任何刷取地点，请在右侧「需求设定」中至少勾选一个。
                  </template>
                  <template v-else>
                    请在右侧添加需求的基质属性，系统会自动计算最优刷取方案。
                  </template>
                </v-alert>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-col>

      <!-- 右侧：需求设定 -->
      <v-col cols="12" lg="6">
        <v-expansion-panels model-value="需求设定">
          <v-expansion-panel value="需求设定">
            <v-expansion-panel-title>
              <v-icon class="mr-2">mdi-cog</v-icon>
              需求设定
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!-- 不使用预刻券开关 -->
              <div class="d-flex align-center mb-4">
                <v-switch
                  v-model="noPrecraftMode"
                  color="primary"
                  density="compact"
                  hide-details
                  label="不使用预刻券"
                />
                <v-tooltip text="直接显示所有刷取地点及其可刷取的武器，无需选择特定武器">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" class="ml-1" color="medium-emphasis" size="small"
                      >mdi-information-outline</v-icon
                    >
                  </template>
                </v-tooltip>
              </div>

              <p class="mb-4 text-medium-emphasis">
                <template v-if="noPrecraftMode">
                  开启「不使用预刻券」模式后，左侧将显示所有刷取地点及其可刷取的武器。点击武器可将包含该武器的地点置顶。
                </template>
                <template v-else>
                  选择你需要的基质属性组合，系统会自动找到最佳的能量淤积点刷取方案。
                  你可以从武器预设中选择，也可以自定义属性组合。
                </template>
              </p>

              <!-- 刷取地点筛选 -->
              <div class="mb-4">
                <div class="d-flex align-center mb-1">
                  <span class="text-body-2 text-medium-emphasis">刷取地点：</span>
                  <v-tooltip text="仅显示勾选的能量淤积点，取消勾选的地点不会出现在左侧方案中">
                    <template #activator="{ props }">
                      <v-icon v-bind="props" class="ml-1" color="medium-emphasis" size="small"
                        >mdi-information-outline</v-icon
                      >
                    </template>
                  </v-tooltip>
                </div>
                <v-chip-group v-model="selectedFarmingLocations" column multiple>
                  <v-chip
                    v-for="location in alluviumLocationOptions"
                    :key="location.battleId"
                    color="primary"
                    filter
                    size="small"
                    :value="location.battleId"
                    variant="outlined"
                  >
                    {{ getDisplayName(location.battleName) }}
                  </v-chip>
                </v-chip-group>
              </div>

              <template v-if="!noPrecraftMode">
                <!-- Selected requirements -->
                <v-card
                  v-for="(stat, index) in requiredEssenceStats"
                  :key="stat.id"
                  class="pa-2 my-2 stat-card"
                  elevation="1"
                  variant="outlined"
                >
                  <v-row align="center" dense>
                    <v-col cols="12" md="3">
                      <div class="d-flex align-center">
                        <v-avatar class="mr-2" color="primary" size="small" variant="tonal">
                          <span class="text-caption font-weight-bold">{{ index + 1 }}</span>
                        </v-avatar>
                        <span
                          class="text-caption text-medium-emphasis text-truncate"
                          :title="getEssenceStatDescription(stat)"
                        >
                          {{ getEssenceStatDescription(stat) }}
                        </span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="2">
                      <v-select
                        v-if="stat.isCustom"
                        v-model="stat.attribute"
                        class="compact-select"
                        density="compact"
                        hide-details
                        :items="allAttributeStats.map((s) => ({ title: s, value: s }))"
                        label="基础"
                        variant="outlined"
                      />
                      <v-chip
                        v-else
                        class="text-truncate"
                        color="primary"
                        size="small"
                        style="max-width: 100%"
                        :title="getStatDisplayName(stat.attribute)"
                        variant="flat"
                      >
                        {{ getStatDisplayName(stat.attribute) }}
                      </v-chip>
                    </v-col>
                    <v-col cols="12" md="3">
                      <v-select
                        v-if="stat.isCustom"
                        v-model="stat.secondary"
                        class="compact-select"
                        density="compact"
                        hide-details
                        :items="allSecondaryStats.map((s) => ({ title: s, value: s }))"
                        label="附加"
                        variant="outlined"
                      />
                      <v-chip
                        v-else
                        class="text-truncate"
                        color="teal"
                        size="small"
                        style="max-width: 100%"
                        :title="getStatDisplayName(stat.secondary)"
                        variant="flat"
                      >
                        {{ getStatDisplayName(stat.secondary) }}
                      </v-chip>
                    </v-col>
                    <v-col cols="12" md="2">
                      <v-select
                        v-if="stat.isCustom"
                        v-model="stat.skill"
                        class="compact-select"
                        density="compact"
                        hide-details
                        :items="allSkillStats.map((s) => ({ title: s, value: s }))"
                        label="技能"
                        variant="outlined"
                      />
                      <v-chip
                        v-else
                        class="text-truncate"
                        color="blue"
                        size="small"
                        style="max-width: 100%"
                        :title="getStatDisplayName(stat.skill)"
                        variant="flat"
                      >
                        {{ getStatDisplayName(stat.skill) }}
                      </v-chip>
                    </v-col>
                    <v-col cols="12" md="2">
                      <div class="d-flex align-center justify-end ga-1">
                        <div class="d-flex flex-column ga-0">
                          <v-btn
                            density="compact"
                            :disabled="index === 0"
                            icon="mdi-chevron-up"
                            size="x-small"
                            style="height: 18px; min-width: 24px"
                            variant="text"
                            @click="moveStatUp(index)"
                          />
                          <v-btn
                            density="compact"
                            :disabled="index === requiredEssenceStats.length - 1"
                            icon="mdi-chevron-down"
                            size="x-small"
                            style="height: 18px; min-width: 24px"
                            variant="text"
                            @click="moveStatDown(index)"
                          />
                        </div>
                        <v-btn
                          color="error"
                          density="compact"
                          icon="mdi-delete"
                          size="x-small"
                          style="height: 24px; min-width: 24px"
                          variant="text"
                          @click="removeStat(index)"
                        />
                      </div>
                    </v-col>
                  </v-row>
                </v-card>

                <v-card
                  v-if="requiredEssenceStats.length === 0"
                  class="pa-2 my-2 d-flex align-center justify-center"
                  elevation="1"
                  variant="outlined"
                >
                  <div class="text-center">
                    <v-icon class="mr-2" color="medium-emphasis" size="small"
                      >mdi-plus-circle-outline</v-icon
                    >
                    <span class="text-medium-emphasis text-caption"
                      >尚未添加任何需求，点击下方按钮开始</span
                    >
                  </div>
                </v-card>

                <!-- Add buttons -->
                <div class="mt-4 mb-4">
                  <v-btn
                    class="mr-2"
                    color="primary"
                    prepend-icon="mdi-plus"
                    variant="flat"
                    @click="addCustomStat"
                  >
                    自定义属性
                  </v-btn>
                </div>
              </template>

              <!-- Weapon presets -->
              <v-divider class="my-4" />
              <h3 class="mb-3 d-flex align-center">
                <v-icon class="mr-2" size="small">mdi-sword</v-icon>
                从武器预设添加
              </h3>

              <!-- 星级过滤开关 -->
              <div class="d-flex align-center gap-2 mb-3">
                <span class="text-body-2 text-medium-emphasis">显示星级：</span>
                <v-chip-group v-model="selectedRarities" column multiple>
                  <v-chip color="primary" filter size="small" value="3" variant="outlined">
                    3★
                  </v-chip>
                  <v-chip color="primary" filter size="small" value="4" variant="outlined">
                    4★
                  </v-chip>
                  <v-chip color="primary" filter size="small" value="5" variant="outlined">
                    5★
                  </v-chip>
                  <v-chip color="primary" filter size="small" value="6" variant="outlined">
                    6★
                  </v-chip>
                  <v-chip color="primary" filter size="small" value="custom" variant="outlined">
                    自定义
                  </v-chip>
                </v-chip-group>
              </div>

              <v-text-field
                v-model="weaponSearch"
                class="mb-4"
                density="compact"
                hide-details
                label="搜索武器名称..."
                prepend-inner-icon="mdi-magnify"
                variant="outlined"
              />
              <!-- 自定义基质区段 -->
              <template
                v-if="selectedRarities.includes('custom') && customMatrixEntries.length > 0"
              >
                <div class="d-flex align-center mb-2 mt-4">
                  <span class="essence-icon-stack me-2">
                    <img v-if="essenceBgSrc" alt="" :src="essenceBgSrc" />
                    <img v-if="defaultIconSrc" alt="" :src="defaultIconSrc" />
                  </span>
                  <h4>自定义基质</h4>
                </div>
                <div class="weapon-grid">
                  <div
                    v-for="entry in customMatrixEntries"
                    :key="entry.syntheticId"
                    class="weapon-item"
                    :class="{
                      'weapon-selected': noPrecraftMode
                        ? selectedWeaponForLocation === entry.syntheticId
                        : isWeaponSelected(entry.syntheticId),
                      'weapon-obtained': isWeaponObtained(entry.syntheticId),
                      'weapon-matched': isWeaponMatchedInPlans(entry.syntheticId),
                    }"
                    @click="handleCustomStatClick(entry)"
                  >
                    <v-tooltip location="top" open-delay="0">
                      <template #activator="{ props }">
                        <div v-bind="props" class="weapon-item-content">
                          <custom-stat-icon
                            :name="entry.displayName"
                            :skill-stat-id="entry.skillStatId"
                          />
                        </div>
                      </template>
                      <span>{{ getCustomStatTooltip(entry.index) }}</span>
                    </v-tooltip>
                    <div
                      v-if="
                        noPrecraftMode
                          ? selectedWeaponForLocation === entry.syntheticId
                          : isWeaponSelected(entry.syntheticId)
                      "
                      class="weapon-selected-overlay"
                    >
                      <v-icon color="white" size="small">mdi-check-circle</v-icon>
                    </div>
                    <v-chip
                      v-if="isWeaponObtained(entry.syntheticId)"
                      class="obtained-badge"
                      color="success"
                      size="x-small"
                      variant="flat"
                    >
                      已获得
                    </v-chip>
                  </div>
                </div>
              </template>
              <template v-for="wType in weaponTypes" :key="wType.id">
                <div class="d-flex align-center mb-2 mt-4">
                  <img :alt="wType.name" class="group-icon me-2" :src="wType.iconUrl" />
                  <h4>{{ wType.name }}</h4>
                </div>
                <div class="weapon-grid">
                  <div
                    v-for="weaponId in filteredWeaponIds(wType.weaponIds)"
                    :key="weaponId"
                    class="weapon-item"
                    :class="{
                      'weapon-selected': noPrecraftMode
                        ? selectedWeaponForLocation === weaponId
                        : isWeaponSelected(weaponId),
                      'weapon-obtained': isWeaponObtained(weaponId),
                      'weapon-matched': isWeaponMatchedInPlans(weaponId),
                    }"
                    @click="handleWeaponClick(weaponId)"
                  >
                    <v-tooltip location="top" open-delay="0">
                      <template #activator="{ props }">
                        <div v-bind="props" class="weapon-item-content">
                          <item-icon :item-id="weaponId" show-item-name />
                        </div>
                      </template>
                      <span>{{ getWeaponStatNames(weaponId) }}</span>
                    </v-tooltip>
                    <div
                      v-if="
                        noPrecraftMode
                          ? selectedWeaponForLocation === weaponId
                          : isWeaponSelected(weaponId)
                      "
                      class="weapon-selected-overlay"
                    >
                      <v-icon color="white" size="small">mdi-check-circle</v-icon>
                    </div>
                    <v-chip
                      v-if="isWeaponObtained(weaponId)"
                      class="obtained-badge"
                      color="success"
                      size="x-small"
                      variant="flat"
                    >
                      已获得
                    </v-chip>
                  </div>
                </div>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-col>
    </v-row>

    <!-- 回到顶部按钮 -->
    <back-to-top />
  </v-container>
</template>

<script lang="ts" setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import BackToTop from '@/components/BackToTop.vue'
import CustomStatIcon from '@/components/CustomStatIcon.vue'
import ItemIcon from '@/components/ItemIcon.vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { type BattleChoice, getDisplayName, useMatrixPlanner } from '@/composables/useMatrixPlanner'
import { useProfiles } from '@/composables/useProfiles'
import { useRarityFilters } from '@/composables/useRarityFilters'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  findCustomStat,
  getCustomStatName,
  getCustomStatSkillId,
  isCustomStatId,
  toCustomStatId,
} from '@/utils/gameData/weapon'

const route = useRoute()
const { weaponTypes, weaponsMap, essencesMap, matrixIcons } = useStaticData()
const { treasureMatrix, activeProfile, updateMatrixPlannerFarmingLocations } = useProfiles()
const { selectedRarities } = useRarityFilters()
const { customStats, customMatrixEntries, fetchCustomStats } = useCustomStats()

// 底板图片路径
const essenceBgSrc = computed(() => matrixIcons.value.essenceBg)
// 默认基质图标路径（叠加在底板上）
const defaultIconSrc = computed(() => matrixIcons.value.defaultIcon)
// 页面渲染中会频繁判断"是否已有基质"，用 Set 避免对 treasureMatrix 反复线性扫描。
const obtainedWeaponIds = computed(
  () => new Set(treasureMatrix.value.map((entry) => entry.weapon_id)),
)

const {
  requiredEssenceStats,
  allAttributeStats,
  allSecondaryStats,
  allSkillStats,
  energyAlluviums,
  addStatFromWeapon,
  addStatFromCustomPreset,
  addCustomStat,
  removeStat,
  moveStatUp,
  moveStatDown,
  getEssenceStatDescription,
  getStatDisplayName,
  allChoices,
  clearAllStats,
} = useMatrixPlanner(obtainedWeaponIds)

/**
 * 获取武器的三条基质属性名称，用于悬浮面板显示
 */
function getWeaponStatNames(weaponId: string): string {
  const weapon = weaponsMap.value.get(weaponId)
  if (!weapon) return ''

  const stats: string[] = []
  if (weapon.attributeStatId) {
    const essence = essencesMap.value.get(weapon.attributeStatId)
    if (essence) stats.push(essence.name)
  }
  if (weapon.secondaryStatId) {
    const essence = essencesMap.value.get(weapon.secondaryStatId)
    if (essence) stats.push(essence.name)
  }
  if (weapon.skillStatId) {
    const essence = essencesMap.value.get(weapon.skillStatId)
    if (essence) stats.push(essence.name)
  }
  return stats.join('、')
}

/**
 * 获取自定义基质的属性名称，用于悬浮面板显示
 */
function getCustomStatTooltip(index: number): string {
  const stat = customStats.value[index]
  if (!stat) return ''

  const stats: string[] = []
  if (stat.attribute) {
    stats.push(getStatDisplayName(stat.attribute))
  }
  if (stat.secondary) {
    stats.push(getStatDisplayName(stat.secondary))
  }
  if (stat.skill) {
    stats.push(getStatDisplayName(stat.skill))
  }
  return stats.join('、')
}

// --- 自定义基质相关 ---
// customStats / customMatrixEntries / fetchCustomStats 统一走 useCustomStats 的
// 模块级单例，避免各页面各存一份副本后互相不同步。

/** 处理自定义基质条目点击，添加/移除需求词条 */
function handleCustomStatClick(entry: { syntheticId: string; index: number }) {
  if (noPrecraftMode.value) {
    // 不使用预刻券模式：选中/取消选中以筛选地点
    if (selectedWeaponForLocation.value === entry.syntheticId) {
      selectedWeaponForLocation.value = null
    } else {
      selectedWeaponForLocation.value = entry.syntheticId
    }
    return
  }
  const stat = customStats.value[entry.index]
  if (!stat) return
  const attribute = getStatDisplayName(stat.attribute)
  const secondary = getStatDisplayName(stat.secondary)
  const skill = getStatDisplayName(stat.skill)
  if (!attribute || !secondary || !skill) return
  addStatFromCustomPreset(entry.syntheticId, attribute, secondary, skill)
}

onMounted(() => {
  void fetchCustomStats()
})

/** 不使用预刻券模式：显示所有刷取地点 */
const noPrecraftMode = ref(false)

/** 不使用预刻券模式下选中的武器ID，用于置顶包含该武器的地点 */
const selectedWeaponForLocation = ref<string | null>(null)

// --- 刷取地点筛选 ---

/** 所有可选的刷取地点（能量淤积点） */
const alluviumLocationOptions = computed(() =>
  Object.values(energyAlluviums.value).map((alluvium) => ({
    battleId: alluvium.battleId,
    battleName: alluvium.battleName,
  })),
)

/** 已落盘的刷取地点筛选配置（battleId -> 是否勾选） */
const savedFarmingLocations = computed(
  () => activeProfile.value.matrix_planner_farming_locations ?? {},
)

/** 当前勾选的刷取地点 battleId 列表，默认全部勾选 */
const selectedFarmingLocations = ref<string[]>([])

/** 刷取地点数据是否已就绪；就绪前不做过滤，避免静态数据到达前误清空方案 */
const farmingLocationFilterReady = ref(false)

/** 是否因未勾选任何刷取地点而导致方案列表为空 */
const noFarmingLocationSelected = computed(
  () => farmingLocationFilterReady.value && selectedFarmingLocations.value.length === 0,
)

// 静态数据或已保存配置变化时同步勾选状态（配置中缺失的键默认视为勾选）
watch(
  [alluviumLocationOptions, savedFarmingLocations],
  ([options, saved]) => {
    if (options.length === 0) return
    const next = options
      .filter((option) => saved[option.battleId] ?? true)
      .map((option) => option.battleId)
    const current = selectedFarmingLocations.value.toSorted().join(',')
    if (next.toSorted().join(',') !== current) {
      selectedFarmingLocations.value = next
    }
    farmingLocationFilterReady.value = true
  },
  { immediate: true },
)

// 勾选状态变化时落盘保存；由加载同步引起的变化不回写，避免冗余写盘
watch(
  selectedFarmingLocations,
  async (newValue, oldValue) => {
    if (!farmingLocationFilterReady.value) return
    const oldSorted = oldValue.toSorted().join(',')
    const newSorted = newValue.toSorted().join(',')
    if (oldSorted === newSorted) return

    const synced = alluviumLocationOptions.value
      .filter((option) => savedFarmingLocations.value[option.battleId] ?? true)
      .map((option) => option.battleId)
    if (synced.toSorted().join(',') === newSorted) return

    const locations: Record<string, boolean> = {}
    for (const option of alluviumLocationOptions.value) {
      locations[option.battleId] = newValue.includes(option.battleId)
    }
    try {
      await updateMatrixPlannerFarmingLocations(locations)
    } catch {
      // 错误已由 useProfiles 的 lastError 处理
    }
  },
  { deep: true },
)

// 需求武器集合被按钮状态、排序和方案统计共用，集中计算可保持口径一致。
const selectedRequiredWeaponIds = computed(
  () =>
    new Set(
      requiredEssenceStats.value
        .filter((stat) => !stat.isCustom && stat.weaponId)
        .map((stat) => stat.weaponId!),
    ),
)

/**
 * 生成所有刷取地点的列表（不使用预刻券模式）
 */
interface LocationChoice {
  battleId: string
  battleName: string
  matchedWeaponIds: string[]
  unobtainedCount: number
}

const allLocationChoices = computed<LocationChoice[]>(() => {
  const locations: LocationChoice[] = []

  // 遍历所有能量淤积点
  for (const [_battleName, alluvium] of Object.entries(energyAlluviums.value)) {
    // 获取该地点能刷取的所有武器
    const matchedWeaponIds: string[] = []

    for (const [weaponId, weapon] of weaponsMap.value.entries()) {
      // 检查武器的属性是否匹配该地点
      // 基础属性总是匹配（所有地点都能刷基础属性）
      // 检查附加属性和技能属性
      const secondaryMatch = alluvium.secondaryStats.includes(
        getStatDisplayName(weapon.secondaryStatId),
      )
      const skillMatch = alluvium.skillStats.includes(getStatDisplayName(weapon.skillStatId))

      if (secondaryMatch && skillMatch) {
        matchedWeaponIds.push(weaponId)
      }
    }

    // 检查自定义基质是否匹配该地点
    for (const stat of customStats.value) {
      if (!stat.secondary || !stat.skill) continue
      const secondary = getStatDisplayName(stat.secondary)
      const skill = getStatDisplayName(stat.skill)
      if (alluvium.secondaryStats.includes(secondary) && alluvium.skillStats.includes(skill)) {
        matchedWeaponIds.push(toCustomStatId(stat))
      }
    }

    // 计算未获得的武器数量
    const unobtainedCount = matchedWeaponIds.filter((id) => !isWeaponObtained(id)).length

    locations.push({
      battleId: alluvium.battleId,
      battleName: alluvium.battleName,
      matchedWeaponIds,
      unobtainedCount,
    })
  }

  return locations
})

/**
 * 不使用预刻券模式下显示的地点列表
 */
const displayedLocationChoices = computed<LocationChoice[]>(() => {
  let locations = [...allLocationChoices.value]

  // 按勾选的刷取地点过滤
  if (farmingLocationFilterReady.value) {
    const enabled = new Set(selectedFarmingLocations.value)
    locations = locations.filter((choice) => enabled.has(choice.battleId))
  }

  // 如果选中了武器，将包含该武器的地点置顶
  if (selectedWeaponForLocation.value) {
    locations = locations.toSorted((a, b) => {
      const aHasWeapon = a.matchedWeaponIds.includes(selectedWeaponForLocation.value!)
      const bHasWeapon = b.matchedWeaponIds.includes(selectedWeaponForLocation.value!)

      if (aHasWeapon && !bHasWeapon) return -1
      if (!aHasWeapon && bHasWeapon) return 1

      // 都包含或都不包含时，按未获得数量排序
      return b.unobtainedCount - a.unobtainedCount
    })
  } else {
    // 没有选中武器时，按未获得数量排序
    locations = locations.toSorted((a, b) => b.unobtainedCount - a.unobtainedCount)
  }

  return locations
})

/**
 * 使用预刻券模式下显示的方案列表
 *
 * 先在全部有效方案上按勾选地点过滤，再取前 5 个，避免先截断后过滤
 * 导致勾选地点中的有效方案被挤出列表。
 */
const displayedBattleChoices = computed<BattleChoice[]>(() => {
  let choices = allChoices.value

  // 按勾选的刷取地点过滤
  if (farmingLocationFilterReady.value) {
    const enabled = new Set(selectedFarmingLocations.value)
    choices = choices.filter((choice) => enabled.has(choice.battleId))
  }

  return choices.slice(0, 5)
})

// 武器图标渲染时会逐个判断是否命中当前方案，预先汇总命中集合减少模板函数开销。
const matchedWeaponIdsInDisplayedPlans = computed(() => {
  if (noPrecraftMode.value) return new Set<string>()
  return new Set(displayedBattleChoices.value.flatMap((choice) => choice.matchedWeaponIds))
})

// 方案更新时在方案一上播放高亮脉冲
watch([displayedLocationChoices, displayedBattleChoices], (_, oldVals) => {
  if (!oldVals || (oldVals[0].length === 0 && oldVals[1].length === 0)) return
  nextTick(() => {
    const el = document.querySelector<HTMLElement>('.choice-card')
    if (!el) return
    el.classList.remove('card-pulse')
    void el.offsetWidth // 强制回流，重启动画
    el.classList.add('card-pulse')
  })
})

const weaponSearch = ref('')

/**
 * 判断武器是否已在宝藏基质配置中
 */
function isWeaponObtained(weaponId: string): boolean {
  return obtainedWeaponIds.value.has(weaponId)
}

function filteredWeaponIds(weaponIds: string[]): string[] {
  let filtered = weaponIds

  // 过滤稀有度
  filtered = filtered.filter((id) => {
    const weapon = weaponsMap.value.get(id)
    if (!weapon) return false
    return selectedRarities.value.includes(String(weapon.rarity))
  })

  // 如果有搜索条件，再过滤
  if (weaponSearch.value.trim()) {
    const search = weaponSearch.value.trim().toLowerCase()
    filtered = filtered.filter((id) => {
      const weapon = weaponsMap.value.get(id)
      return weapon && weapon.name.toLowerCase().includes(search)
    })
  }

  // 按稀有度降序排序（6★ -> 3★）
  return filtered.toSorted((a, b) => {
    const wa = weaponsMap.value.get(a)
    const wb = weaponsMap.value.get(b)
    if (wa && wb) return wb.rarity - wa.rarity
    return 0
  })
}

function isWeaponSelected(weaponId: string): boolean {
  return selectedRequiredWeaponIds.value.has(weaponId)
}

/**
 * 处理武器点击事件
 */
function handleWeaponClick(weaponId: string) {
  if (noPrecraftMode.value) {
    // 不使用预刻券模式：选中武器以置顶包含该武器的地点
    if (selectedWeaponForLocation.value === weaponId) {
      // 再次点击取消选中
      selectedWeaponForLocation.value = null
    } else {
      selectedWeaponForLocation.value = weaponId
    }
  } else {
    // 使用预刻券模式：添加到需求列表
    addStatFromWeapon(weaponId)
  }
}

function getRequirementTooltip(index: number): string {
  const stat = requiredEssenceStats.value[index]
  if (!stat) return ''
  const parts: string[] = []
  if (stat.attribute) parts.push(getStatDisplayName(stat.attribute))
  if (stat.secondary) parts.push(getStatDisplayName(stat.secondary))
  if (stat.skill) parts.push(getStatDisplayName(stat.skill))
  return parts.join('、') || '未设置'
}

/**
 * 获取武器的悬浮面板文本，支持普通武器和自定义基质
 * 普通武器从 weaponsMap 中获取三条基质属性名称
 * 自定义基质从 customStats 配置中获取属性名称
 */
function getWeaponTooltipText(weaponId: string): string {
  const found = findCustomStat(weaponId, customStats.value)
  if (found) return getCustomStatTooltip(found.index)
  return getWeaponStatNames(weaponId)
}

function sortedWeaponIds(weaponIds: string[]): string[] {
  return weaponIds.toSorted((a, b) => {
    const aObtained = isWeaponObtained(a)
    const bObtained = isWeaponObtained(b)

    // 未获得的排在前面
    if (!aObtained && bObtained) return -1
    if (aObtained && !bObtained) return 1

    const wa = weaponsMap.value.get(a)
    const wb = weaponsMap.value.get(b)
    if (wa && wb) return wb.rarity - wa.rarity
    return 0
  })
}

/**
 * 按照已获得/未获得排序武器ID（未获得的排在前面）
 */
function sortedWeaponIdsByObtained(weaponIds: string[]): string[] {
  return weaponIds.toSorted((a, b) => {
    const aObtained = isWeaponObtained(a)
    const bObtained = isWeaponObtained(b)

    // 未获得的排在前面
    if (!aObtained && bObtained) return -1
    if (aObtained && !bObtained) return 1

    // 同样状态下按稀有度排序
    const wa = weaponsMap.value.get(a)
    const wb = weaponsMap.value.get(b)
    if (wa && wb) return wb.rarity - wa.rarity
    return 0
  })
}

/**
 * 判断某个武器是否是用户选择的需求武器
 */
function isRequiredWeapon(weaponId: string): boolean {
  return selectedRequiredWeaponIds.value.has(weaponId)
}

/**
 * 判断武器是否在左侧方案中被匹配（用于显示橙黄脉冲）
 * 仅在使用预刻券模式下有效
 */
function isWeaponMatchedInPlans(weaponId: string): boolean {
  return matchedWeaponIdsInDisplayedPlans.value.has(weaponId)
}

/**
 * 获取已选择的武器总数
 */
function getSelectedWeaponCount(): number {
  return selectedRequiredWeaponIds.value.size
}

/**
 * 获取方案匹配的已选择武器数量
 */
function getSelectedWeaponMatchCount(choice: BattleChoice): number {
  return choice.matchedWeaponIds.filter((id: string) => selectedRequiredWeaponIds.value.has(id))
    .length
}

/**
 * 根据 URL 参数选中武器并加入需求列表。
 *
 * 内置武器直接按 weaponId 添加；自定义基质需要先从配置中解析
 * 出属性组合（fetchCustomStats 是异步的，可能尚未就绪），
 * 再按合成 ID 添加需求。
 */
async function selectWeaponFromQuery(weaponParam: string) {
  if (isCustomStatId(weaponParam)) {
    if (customStats.value.length === 0) {
      await fetchCustomStats()
    }
    const found = findCustomStat(weaponParam, customStats.value)
    if (!found) return
    const stat = found.stat
    if (!stat.attribute || !stat.secondary || !stat.skill) return
    addStatFromCustomPreset(
      weaponParam,
      getStatDisplayName(stat.attribute),
      getStatDisplayName(stat.secondary),
      getStatDisplayName(stat.skill),
    )
    return
  }
  addStatFromWeapon(weaponParam)
}

/**
 * 在页面加载时处理 URL 参数。
 */
onMounted(() => {
  const shouldClear = route.query.clear === 'true'
  const noPrecraft = route.query.noPrecraft === 'true'

  if (shouldClear) {
    // 从宝藏基质跳转过来，清空之前的选择
    clearAllStats()
  }

  const weaponParam = route.query.weapon
  if (typeof weaponParam === 'string' && weaponParam) {
    void selectWeaponFromQuery(weaponParam)
  }

  if (noPrecraft) {
    // 从宝藏基质跳转过来，开启不使用预刻券模式
    noPrecraftMode.value = true
    // 滚动到页面顶部
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
})

/**
 * 监听 URL 参数变化。
 */
watch(
  () => route.query,
  (query) => {
    const shouldClear = query.clear === 'true'
    const noPrecraft = query.noPrecraft === 'true'

    if (shouldClear) {
      clearAllStats()
    }

    const weaponParam = query.weapon
    if (typeof weaponParam === 'string' && weaponParam) {
      void selectWeaponFromQuery(weaponParam)
    }

    if (noPrecraft) {
      noPrecraftMode.value = true
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  },
)

/**
 * 监听模式切换，同步选中的武器状态
 */
watch(noPrecraftMode, (newMode, oldMode) => {
  if (newMode === false && oldMode === true) {
    // 从不使用预刻券模式切换到使用预刻券模式
    // 清除原有的需求列表
    clearAllStats()

    // 如果有选中的武器，添加到需求列表
    if (selectedWeaponForLocation.value) {
      const weaponId = selectedWeaponForLocation.value
      addStatFromWeapon(weaponId)
      // 清除 selectedWeaponForLocation（因为现在使用 requiredEssenceStats）
      selectedWeaponForLocation.value = null
    }
  } else if (newMode === true && oldMode === false) {
    // 从使用预刻券模式切换到不使用预刻券模式
    // 如果需求列表中有武器，选中第一个
    const firstWeapon = requiredEssenceStats.value.find((s) => !s.isCustom && s.weaponId)
    if (firstWeapon && firstWeapon.weaponId) {
      selectedWeaponForLocation.value = firstWeapon.weaponId
    }
  }
})
</script>

<style scoped lang="scss">
$weapon-icon-size: clamp(2.5rem, 12vw, 4.5rem);

.matrix-planner-page {
  .choice-card {
    transition:
      transform 0.2s ease,
      box-shadow 0.2s ease;
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
    }
    &--top {
      border-width: 2px;
    }
  }

  .stat-card {
    transition: background-color 0.15s ease;
    &:hover {
      background-color: rgba(var(--v-theme-primary), 0.04);
    }
  }

  .compact-select {
    :deep(.v-field) {
      min-height: 32px !important;
      font-size: 0.75rem;
    }
    :deep(.v-field__input) {
      min-height: 32px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
    }
    :deep(.v-label) {
      font-size: 0.7rem;
    }
    :deep(.v-field__append-inner) {
      display: none !important;
    }
    :deep(.v-select__selection) {
      flex-direction: column !important;
    }
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
  position: relative;
  transition:
    transform 0.15s,
    opacity 0.15s,
    filter 0.15s,
    box-shadow 0.3s ease;
  border-radius: 6px;
  &:hover {
    transform: scale(1.1);
  }

  .weapon-item-content {
    width: 100%;
    height: 100%;
  }

  // 匹配武器的橙黄脉冲效果
  &.weapon-matched {
    animation: matched-glow 2s ease-in-out infinite;
    box-shadow: 0 0 15px rgba(255, 165, 0, 0.8);
  }

  // 已获得武器的样式
  &.weapon-obtained {
    opacity: 0.6;
    filter: grayscale(0.3);

    // 确保子元素也应用样式
    :deep(.item-icon-img) {
      opacity: 0.6;
      filter: grayscale(0.3);
    }
  }

  .obtained-badge {
    position: absolute;
    top: -4px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.65rem;
    padding: 0 4px;
    height: 16px;
    min-width: auto;
    z-index: 10;
  }
}

.weapon-item-small {
  width: 4rem !important;
  height: 4rem !important;
  display: inline-block;
  flex-shrink: 0;
  cursor: pointer;
  position: relative;
  transition:
    transform 0.15s,
    opacity 0.15s,
    filter 0.15s,
    box-shadow 0.3s ease;
  border-radius: 6px;
  &:hover {
    transform: scale(1.05);
  }

  // 匹配武器的橙黄脉冲效果
  &.weapon-matched {
    animation: matched-glow 2s ease-in-out infinite;
    box-shadow: 0 0 15px rgba(255, 165, 0, 0.8);
  }

  // 已获得武器的样式
  &.weapon-obtained {
    opacity: 0.6;
    filter: grayscale(0.3);

    // 确保子元素也应用样式
    :deep(.item-icon-img) {
      opacity: 0.6;
      filter: grayscale(0.3);
    }
  }

  .obtained-badge {
    position: absolute;
    top: -4px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.65rem;
    padding: 0 4px;
    height: 16px;
    min-width: auto;
    z-index: 10;
  }
}

@keyframes matched-glow {
  0%,
  100% {
    box-shadow: 0 0 15px rgba(255, 0, 0, 0.8);
  }
  50% {
    box-shadow: 0 0 20px rgba(255, 165, 0, 0.9);
  }
}

.weapon-selected-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  border-radius: 6px;
  pointer-events: none;
  z-index: 2;
}

// 方案更新时的高亮脉冲
.card-pulse {
  animation: card-update-pulse 0.6s ease;
}

@keyframes card-update-pulse {
  0%,
  100% {
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }
  50% {
    box-shadow:
      0 0 0 3px rgba(var(--v-theme-primary), 0.35),
      0 4px 16px rgba(var(--v-theme-primary), 0.15);
  }
}
</style>
