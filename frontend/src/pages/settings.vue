<template>
  <v-container>
    <v-expansion-panels color="primary-darken-1" :model-value="[0, 1, 2]" multiple>
      <v-expansion-panel :value="0">
        <v-expansion-panel-title>武器基质预设</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>将以下武器所对应的基质视为宝藏</h2>
          <h3>按稀有度快捷选择</h3>
          <div class="d-flex flex-row flex-wrap gc-4">
            <v-checkbox
              v-for="rarity in [3, 4, 5, 6]"
              :key="rarity"
              :color="`#${rarityColorTable[rarity]?.color}`"
              density="compact"
              hide-details
              :indeterminate="isRarityPartiallySelected(rarity)"
              :model-value="isRarityAllSelected(rarity)"
              @click="raritySelectAll(rarity, !isRarityAllSelected(rarity))"
            >
              <template #label>
                <span :style="{ color: `#${rarityColorTable[rarity]?.color}` }">{{ rarity }}★</span>
              </template>
            </v-checkbox>
          </div>
          <v-divider class="my-4" />
          <template
            v-for="{ groupId, groupName, iconId } in wikiGroupTable['wiki_type_weapon']?.list ?? []"
            :key="groupId"
          >
            <h3>
              <v-checkbox
                density="compact"
                hide-details
                :indeterminate="isTypePartiallySelected(groupId)"
                :model-value="isTypeAllSelected(groupId)"
                @click="typeSelectAll(groupId, !isTypeAllSelected(groupId))"
              >
                <template #prepend>
                  <img
                    :src="getGroupIconUrl(iconId)"
                    :alt="getTranslation(groupName)"
                    class="group-icon me-2"
                    :style="{
                      filter: theme.current.value.dark ? 'none' : 'invert(1)',
                    }"
                  />
                  <h3 class="ma-0">{{ getTranslation(groupName) }}</h3>
                </template>
              </v-checkbox>
            </h3>
            <div class="weapon-grid">
              <div
                v-for="{ wikiEntryId, weaponId } in wikiEntryTable[groupId]!.list.map(
                  (wikiEntryId) => ({
                    wikiEntryId,
                    weaponId: wikiEntryDataTable[wikiEntryId]!.refItemId,
                  }),
                )"
                :key="wikiEntryId"
                class="d-flex flex-column align-center"
                :class="{
                  'opacity-50': !selectedWeaponIds.includes(weaponId),
                }"
              >
                <div
                  class="weapon-item"
                  @click="
                    selectedWeaponIds.includes(weaponId)
                      ? selectedWeaponIds.splice(selectedWeaponIds.indexOf(weaponId), 1)
                      : selectedWeaponIds.push(weaponId)
                  "
                >
                  <item-icon :item-id="weaponId" show-item-name />
                </div>
                <v-checkbox-btn
                  v-model="selectedWeaponIds"
                  color="primary"
                  density="comfortable"
                  :value="weaponId"
                />
                <v-tooltip location="bottom" activator="parent">
                  {{ getWeaponStatsDescription(weaponId) }}
                </v-tooltip>
              </div>
            </div>
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel :value="1">
        <v-expansion-panel-title>自定义宝藏基质</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>如果基质的某个词条初始属性较高，也将其视为宝藏</h2>
          <v-row align="center" class="my-4">
            <v-col cols="12" md="4">
              <v-switch
                v-model="highLevelTreasureEnabled"
                color="primary"
                density="comfortable"
                hide-details
                label="启用高等级基质属性词条判定"
              />
            </v-col>
            <v-col cols="12" md="8">
              <v-slider
                v-model="highLevelTreasureAttributeThreshold"
                :disabled="!highLevelTreasureEnabled"
                :min="1"
                :max="6"
                :step="1"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
                label="基础属性"
                show-ticks="always"
                tick-size="4"
                color="primary"
                thumb-label
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
              <v-slider
                v-model="highLevelTreasureSecondaryThreshold"
                :disabled="!highLevelTreasureEnabled"
                :min="1"
                :max="6"
                :step="1"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
                label="附加属性"
                show-ticks="always"
                tick-size="4"
                color="primary"
                thumb-label
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
              <v-slider
                v-model="highLevelTreasureSkillThreshold"
                :disabled="!highLevelTreasureEnabled"
                :min="1"
                :max="3"
                :step="1"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3' }"
                label="技能属性"
                show-ticks="always"
                tick-size="4"
                color="primary"
                thumb-label
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
              <v-alert
                v-if="highLevelTreasureEnabled"
                border="start"
                class="mt-2"
                type="info"
                variant="tonal"
              >
                当前效果：如果基质的基础属性等级 ≥{{
                  highLevelTreasureAttributeThreshold
                }}，或者附加属性等级 ≥{{ highLevelTreasureSecondaryThreshold }}，或者技能属性等级
                ≥{{ highLevelTreasureSkillThreshold }}，则也将其视为宝藏。
              </v-alert>
            </v-col>
          </v-row>
          <v-divider class="my-4" />
          <h2>额外将以下属性的基质视为宝藏</h2>
          <v-alert v-if="false" border="start" class="my-4" type="info" variant="tonal">
            请点击右侧（或者下方）的加号按钮添加新的基质属性行，点击删除按钮删除对应行。上下箭头按钮可调整行顺序。
          </v-alert>
          <v-row v-for="(essenceStat, index) in treasureEssenceStats" :key="index" align="center">
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="essenceStat.attribute"
                :items="
                  allAttributeStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                density="comfortable"
                hide-details
                label="基础属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="essenceStat.secondary"
                :items="
                  allSecondaryStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                density="comfortable"
                hide-details
                label="附加属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="essenceStat.skill"
                :items="
                  allSkillStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                density="comfortable"
                hide-details
                label="技能属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-btn
                color="primary"
                icon="mdi-plus"
                variant="text"
                @click="
                  treasureEssenceStats.splice(index, 0, {
                    attribute: null,
                    secondary: null,
                    skill: null,
                  })
                "
              />
              <v-btn
                color="error"
                icon="mdi-delete"
                variant="text"
                @click="treasureEssenceStats.splice(index, 1)"
              />
              <v-btn
                :disabled="index === 0"
                icon="mdi-chevron-up"
                variant="text"
                @click="
                  () => {
                    const stat = treasureEssenceStats.splice(index, 1)[0]!
                    treasureEssenceStats.splice(index - 1, 0, stat)
                  }
                "
              />
              <v-btn
                :disabled="index === treasureEssenceStats.length - 1"
                icon="mdi-chevron-down"
                variant="text"
                @click="
                  () => {
                    const stat = treasureEssenceStats.splice(index, 1)[0]!
                    treasureEssenceStats.splice(index + 1, 0, stat)
                  }
                "
              />
            </v-col>
          </v-row>
          <v-row v-if="treasureEssenceStats.length === 0" class="my-4">
            <v-col cols="12" sm="6" md="9">
              <v-btn
                color="primary"
                prepend-icon="mdi-plus"
                @click="
                  treasureEssenceStats.push({ attribute: null, secondary: null, skill: null })
                "
              >
                添加自定义宝藏基质
              </v-btn>
            </v-col>
          </v-row>
          <v-row v-else>
            <v-col cols="12" sm="6" md="9" />
            <v-col cols="12" sm="6" md="3">
              <v-btn
                color="primary"
                icon="mdi-plus"
                variant="text"
                @click="
                  treasureEssenceStats.push({ attribute: null, secondary: null, skill: null })
                "
              />
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel :value="2">
        <v-expansion-panel-title>操作设置</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>遇到宝藏基质或者养成材料时，该如何操作？</h2>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            “宝藏基质”和“养成材料”仅为分类简称，不是宝藏的基质都视为养成材料。
          </v-alert>
          <v-row>
            <v-col cols="12" md="6">
              <h3>对于<span class="text-success">宝藏基质</span>，我们</h3>
              <v-radio-group v-model="treasureAction" color="primary" density="comfortable">
                <v-radio label="不去动它" value="keep" />
                <v-radio label="把它锁上" value="lock" />
                <v-radio label="把它标记为弃用" value="deprecate" disabled />
                <v-radio label="如果锁着，则解锁" value="unlock"></v-radio>
                <v-radio label="如果已标记为弃用，则取消弃用" value="undeprecate" />
                <v-radio label="解锁且取消弃用" value="unlock_and_undeprecate"></v-radio>
                <v-radio label="如果没有上锁，则弃用" value="deprecate_if_not_locked" disabled />
                <v-radio label="如果没有弃用，则上锁" value="lock_if_not_deprecated" />
              </v-radio-group>
            </v-col>
            <v-col cols="12" md="6">
              <h3>对于<span class="text-error">养成材料</span>，我们</h3>
              <v-radio-group v-model="trashAction" color="primary" density="comfortable">
                <v-radio label="不去动它" value="keep" />
                <v-radio label="把它锁上" value="lock" />
                <v-radio label="把它标记为弃用" value="deprecate" />
                <v-radio label="如果锁着，则解锁" value="unlock" />
                <v-radio label="如果已标记为弃用，则取消弃用" value="undeprecate" />
                <v-radio label="解锁且取消弃用" value="unlock_and_undeprecate" />
                <v-radio label="如果没有上锁，则弃用" value="deprecate_if_not_locked" />
                <v-radio label="如果没有弃用，则上锁" value="lock_if_not_deprecated" />
              </v-radio-group>
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script lang="ts" setup>
import ItemIcon from '@/components/ItemIcon.vue'
import {
  gemTable,
  getTranslation,
  rarityColorTable,
  weaponBasicTable,
  wikiEntryDataTable,
  wikiEntryTable,
  wikiGroupTable,
} from '@/utils/gameData/gameData'
import { statsForWeapon } from '@/utils/gameData/weapon'
import { computed, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'

const theme = useTheme()

const allAttributeStats = computed(() =>
  Object.values(gemTable.value)
    .filter((gem) => gem.termType === 0)
    .map((gem) => gem.gemTermId),
)
const allSecondaryStats = computed(() =>
  Object.values(gemTable.value)
    .filter((gem) => gem.termType === 1)
    .map((gem) => gem.gemTermId),
)
const allSkillStats = computed(() =>
  Object.values(gemTable.value)
    .filter((gem) => gem.termType === 2)
    .map((gem) => gem.gemTermId),
)

function getGemTagName(gemTermId: string): string {
  const gem = gemTable.value[gemTermId]
  if (gem === undefined) {
    return gemTermId
  }
  return getTranslation(gem.tagName) || gemTermId
}

function getGroupIconUrl(iconId: string): string {
  return `https://cos.yituliu.cn/endfield/sprites_selective/wiki/groupicon/${iconId}.png`
}

interface EssenceStat {
  attribute: string | null
  secondary: string | null
  skill: string | null
}

const selectedWeaponIds = ref<string[]>([])
const treasureEssenceStats = ref<EssenceStat[]>([])
const treasureAction = ref('lock')
const trashAction = ref('unlock')
const highLevelTreasureEnabled = ref(false)
const highLevelTreasureAttributeThreshold = ref(3)
const highLevelTreasureSecondaryThreshold = ref(3)
const highLevelTreasureSkillThreshold = ref(3)

const notSelectedWeaponIds = computed(() => {
  return Object.keys(weaponBasicTable.value).filter(
    (weaponId) => !selectedWeaponIds.value.includes(weaponId),
  )
})

function getWeaponStatsDescription(weaponId: string): string {
  const stats = statsForWeapon.value.get(weaponId)
  if (!stats) {
    return '无基质属性'
  }
  const parts: string[] = []
  if (stats.attribute) {
    parts.push(getGemTagName(stats.attribute))
  }
  if (stats.secondary) {
    parts.push(getGemTagName(stats.secondary))
  }
  if (stats.skill) {
    parts.push(getGemTagName(stats.skill))
  }
  return parts.join('、')
}

function raritySelectAll(rarity: number, select: boolean) {
  const weaponIds = Object.values(weaponBasicTable.value)
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.weaponId)
  if (select) {
    selectedWeaponIds.value = [...new Set([...selectedWeaponIds.value, ...weaponIds])]
  } else {
    selectedWeaponIds.value = selectedWeaponIds.value.filter((id) => !weaponIds.includes(id))
  }
}

function isRarityAllSelected(rarity: number): boolean {
  const weaponIds = Object.values(weaponBasicTable.value)
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.weaponId)
  return weaponIds.every((id) => selectedWeaponIds.value.includes(id))
}

function isRarityPartiallySelected(rarity: number): boolean {
  const weaponIds = Object.values(weaponBasicTable.value)
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.weaponId)
  const selectedCount = weaponIds.filter((id) => selectedWeaponIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < weaponIds.length
}

function typeSelectAll(groupId: string, select: boolean) {
  const weaponIds =
    wikiEntryTable.value[groupId]?.list.map(
      (wikiEntryId) => wikiEntryDataTable.value[wikiEntryId]!.refItemId,
    ) ?? []
  if (select) {
    selectedWeaponIds.value = [...new Set([...selectedWeaponIds.value, ...weaponIds])]
  } else {
    selectedWeaponIds.value = selectedWeaponIds.value.filter((id) => !weaponIds.includes(id))
  }
}

function isTypeAllSelected(groupId: string): boolean {
  const weaponIds =
    wikiEntryTable.value[groupId]?.list.map(
      (wikiEntryId) => wikiEntryDataTable.value[wikiEntryId]!.refItemId,
    ) ?? []
  return weaponIds.every((id) => selectedWeaponIds.value.includes(id))
}

function isTypePartiallySelected(groupId: string): boolean {
  const weaponIds =
    wikiEntryTable.value[groupId]?.list.map(
      (wikiEntryId) => wikiEntryDataTable.value[wikiEntryId]!.refItemId,
    ) ?? []
  const selectedCount = weaponIds.filter((id) => selectedWeaponIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < weaponIds.length
}

const config = computed(() => {
  return {
    version: 2,
    trash_weapon_ids: notSelectedWeaponIds.value,
    treasure_essence_stats: treasureEssenceStats.value,
    treasure_action: treasureAction.value,
    trash_action: trashAction.value,
    high_level_treasure_enabled: highLevelTreasureEnabled.value,
    high_level_treasure_attribute_threshold: highLevelTreasureAttributeThreshold.value,
    high_level_treasure_secondary_threshold: highLevelTreasureSecondaryThreshold.value,
    high_level_treasure_skill_threshold: highLevelTreasureSkillThreshold.value,
  }
})

async function getConfig() {
  const response = await fetch(`/api/config`)
  const result = await response.json()
  const {
    trash_weapon_ids,
    treasure_essence_stats,
    treasure_action,
    trash_action,
    high_level_treasure_enabled,
    high_level_treasure_attribute_threshold,
    high_level_treasure_secondary_threshold,
    high_level_treasure_skill_threshold,
  } = result
  treasureEssenceStats.value = treasure_essence_stats
  treasureAction.value = treasure_action
  trashAction.value = trash_action
  highLevelTreasureEnabled.value = high_level_treasure_enabled
  highLevelTreasureAttributeThreshold.value = high_level_treasure_attribute_threshold
  highLevelTreasureSecondaryThreshold.value = high_level_treasure_secondary_threshold
  highLevelTreasureSkillThreshold.value = high_level_treasure_skill_threshold
  selectedWeaponIds.value = Object.keys(weaponBasicTable.value).filter(
    (weaponId) => !trash_weapon_ids.includes(weaponId),
  )
}

async function postConfig() {
  await fetch(`/api/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config.value),
  })
}

onMounted(async () => {
  await getConfig()
  watch(config, postConfig, { deep: true })
})
</script>

<style scoped lang="scss">
$weapon-icon-size: clamp(3rem, 16vw, 6rem);

.group-icon {
  width: 2rem;
  height: 2rem;
}

.customize-button {
  height: $weapon-icon-size !important;
  width: $weapon-icon-size !important;
}

.weapon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, $weapon-icon-size);
  gap: calc($weapon-icon-size / 10);
}

.weapon-item {
  width: $weapon-icon-size;
  height: $weapon-icon-size;
}
</style>
