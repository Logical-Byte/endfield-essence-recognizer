<template>
  <v-dialog v-model="open" max-width="900" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-map-marker-plus</v-icon>
        自定义淤积点
      </v-card-title>

      <v-card-text>
        <v-alert border="start" class="mb-4" density="compact" type="info" variant="tonal">
          自定义淤积点保存在 custom_alluviums.json，全账号通用；保存后立即参与「最优刷取方案」计算，
          并在刷取地点筛选中与内置淤积点分开显示。
        </v-alert>

        <!-- 已有条目 -->
        <div class="d-flex align-center mb-2">
          <span class="text-subtitle-2 text-medium-emphasis">
            已保存（{{ customAlluviums.length }}）
          </span>
          <v-spacer />
          <v-btn
            color="deep-purple"
            prepend-icon="mdi-plus"
            size="small"
            variant="tonal"
            @click="startCreate"
          >
            新建
          </v-btn>
        </div>

        <div v-if="customAlluviums.length === 0" class="text-body-2 text-medium-emphasis mb-4">
          还没有自定义淤积点。游戏新增淤积点后，可以在这里先补上。
        </div>
        <v-list v-else class="mb-2" density="compact">
          <v-list-item v-for="item in customAlluviums" :key="item.id" :subtitle="summarize(item)">
            <template #prepend>
              <v-icon color="deep-purple">mdi-map-marker</v-icon>
            </template>
            <v-list-item-title>{{ displayName(item) }}</v-list-item-title>
            <template #append>
              <v-btn
                aria-label="编辑自定义淤积点"
                icon="mdi-pencil"
                size="small"
                variant="text"
                @click="startEdit(item)"
              />
              <v-btn
                aria-label="删除自定义淤积点"
                color="error"
                icon="mdi-delete"
                size="small"
                variant="text"
                @click="promptDelete(item)"
              />
            </template>
          </v-list-item>
        </v-list>

        <v-divider class="my-4" />

        <!-- 设定表单 -->
        <template v-if="draft">
          <div class="text-subtitle-2 mb-3">
            {{ draft.id ? '编辑淤积点' : '新建淤积点' }}
          </div>
          <v-text-field
            v-model="draft.name"
            class="mb-4"
            density="compact"
            hide-details
            label="淤积点名称"
            maxlength="40"
            placeholder="例如：重度能量淤积点·新区域"
            variant="outlined"
          />

          <div class="mb-4">
            <div class="d-flex align-center mb-1">
              <span class="text-body-2 text-medium-emphasis">基础属性（至少 3 项）</span>
              <v-spacer />
              <v-btn
                size="x-small"
                variant="text"
                @click="toggleGroup('attributeStats', allAttributeStats)"
              >
                {{ isGroupAllSelected('attributeStats', allAttributeStats) ? '清空' : '全选' }}
              </v-btn>
            </div>
            <v-chip-group v-model="draft.attributeStats" column multiple>
              <v-chip
                v-for="statId in allAttributeStats"
                :key="statId"
                color="primary"
                filter
                size="small"
                :value="statId"
                variant="outlined"
              >
                {{ getGemTagName(statId) }}
              </v-chip>
            </v-chip-group>
          </div>

          <div class="mb-4">
            <div class="d-flex align-center mb-1">
              <span class="text-body-2 text-medium-emphasis">附加属性（至少 1 项）</span>
              <v-spacer />
              <v-btn
                size="x-small"
                variant="text"
                @click="toggleGroup('secondaryStats', allSecondaryStats)"
              >
                {{ isGroupAllSelected('secondaryStats', allSecondaryStats) ? '清空' : '全选' }}
              </v-btn>
            </div>
            <v-chip-group v-model="draft.secondaryStats" column multiple>
              <v-chip
                v-for="statId in allSecondaryStats"
                :key="statId"
                color="teal"
                filter
                size="small"
                :value="statId"
                variant="outlined"
              >
                {{ getGemTagName(statId) }}
              </v-chip>
            </v-chip-group>
          </div>

          <div>
            <div class="d-flex align-center mb-1">
              <span class="text-body-2 text-medium-emphasis">技能属性（至少 1 项）</span>
              <v-spacer />
              <v-btn
                size="x-small"
                variant="text"
                @click="toggleGroup('skillStats', allSkillStats)"
              >
                {{ isGroupAllSelected('skillStats', allSkillStats) ? '清空' : '全选' }}
              </v-btn>
            </div>
            <v-chip-group v-model="draft.skillStats" column multiple>
              <v-chip
                v-for="statId in allSkillStats"
                :key="statId"
                color="blue"
                filter
                size="small"
                :value="statId"
                variant="outlined"
              >
                {{ getGemTagName(statId) }}
              </v-chip>
            </v-chip-group>
          </div>

          <div v-if="validationHint" class="text-caption text-error mt-2">
            {{ validationHint }}
          </div>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-btn v-if="draft" :disabled="saving" variant="text" @click="draft = null">取消</v-btn>
        <v-spacer />
        <v-btn :disabled="saving" variant="text" @click="open = false">关闭</v-btn>
        <v-btn
          v-if="draft"
          color="primary"
          :disabled="!canSave || saving"
          :loading="saving"
          prepend-icon="mdi-content-save"
          variant="flat"
          @click="save"
        >
          保存
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认：自定义地点会直接参与方案计算，删错会让方案少一份可选位置 -->
  <v-dialog v-model="deleteConfirm" max-width="460">
    <v-card>
      <v-card-title class="text-error">删除自定义淤积点</v-card-title>
      <v-card-text>
        确定要删除自定义淤积点「{{
          pendingDeleteName
        }}」吗？删除后它不再出现在刷取地点与最优方案中，此操作不可撤销。
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="deleteConfirm = false">取消</v-btn>
        <v-btn color="error" @click="confirmDelete">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import type { CustomAlluvium } from '@/utils/gameData/alluvium'
import { computed, ref, watch } from 'vue'
import { useCustomAlluviums } from '@/composables/useCustomAlluviums'
import { useToast } from '@/composables/useToast'
import { fallbackCustomAlluviumName } from '@/utils/gameData/alluvium'
import { useStaticData } from '@/utils/gameData/staticData'
import { getGemTagName } from '@/utils/gameData/weapon'

/** 弹窗开关（v-model） */
const open = defineModel<boolean>({ default: false })

const { essencesMap } = useStaticData()
const { customAlluviums, fetchCustomAlluviums, saveCustomAlluvium, deleteCustomAlluvium } =
  useCustomAlluviums()

/** 编辑中的表单；null 表示未在编辑 */
interface CustomAlluviumDraft {
  /** 空串表示新建，后端会分配稳定 ID */
  id: string
  name: string
  attributeStats: string[]
  secondaryStats: string[]
  skillStats: string[]
}

const draft = ref<CustomAlluviumDraft | null>(null)
const saving = ref(false)
const deleteConfirm = ref(false)
const pendingDelete = ref<CustomAlluvium | null>(null)

/** 可多选的三组属性字段名 */
type StatField = 'attributeStats' | 'secondaryStats' | 'skillStats'

/** 可勾选的基础属性词条（取自静态数据，游戏更新后自动跟随） */
const allAttributeStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((essence) => essence.type === 'ATTRIBUTE')
    .map((essence) => essence.id),
)
/** 可勾选的附加属性词条 */
const allSecondaryStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((essence) => essence.type === 'SECONDARY')
    .map((essence) => essence.id),
)
/** 可勾选的技能属性词条 */
const allSkillStats = computed(() =>
  Array.from(essencesMap.value.values())
    .filter((essence) => essence.type === 'SKILL')
    .map((essence) => essence.id),
)

const pendingDeleteName = computed(() =>
  pendingDelete.value ? displayName(pendingDelete.value) : '',
)

/** 列表里的显示名：没填名称时用兜底名 */
function displayName(item: CustomAlluvium): string {
  const index = customAlluviums.value.findIndex((entry) => entry.id === item.id)
  return item.name || fallbackCustomAlluviumName(Math.max(index, 0))
}

/** 列表里的属性摘要，方便一眼看出各地点能刷什么 */
function summarize(item: CustomAlluvium): string {
  const attributeCount = item.attribute_stats?.length ?? 0
  const attributePart = attributeCount === 0 ? '不限制' : `${attributeCount} 项`
  return `基础 ${attributePart} · 附加 ${item.secondary_stats?.length ?? 0} 项 · 技能 ${
    item.skill_stats?.length ?? 0
  } 项`
}

/** 分组是否已全选 */
function isGroupAllSelected(field: StatField, items: readonly string[]): boolean {
  if (!draft.value) return false
  const selected = draft.value[field]
  if (items.length === 0) return false
  return items.every((item) => selected.includes(item))
}

/** 分组全选 / 清空切换 */
function toggleGroup(field: StatField, items: readonly string[]) {
  if (!draft.value) return
  draft.value[field] = isGroupAllSelected(field, items) ? [] : [...items]
}

/** 表单校验提示：空串表示可以保存 */
const validationHint = computed(() => {
  if (!draft.value) return ''
  if (!draft.value.name.trim()) return '请填写淤积点名称'
  if (draft.value.attributeStats.length < 3) return '基础属性至少勾选 3 项'
  if (draft.value.secondaryStats.length === 0) return '至少勾选 1 项附加属性'
  if (draft.value.skillStats.length === 0) return '至少勾选 1 项技能属性'
  return ''
})

const canSave = computed(() => draft.value !== null && validationHint.value === '')

/** 新建：默认全选，用户只需取消该地点刷不出的词条 */
function startCreate() {
  draft.value = {
    id: '',
    name: '',
    attributeStats: [...allAttributeStats.value],
    secondaryStats: [...allSecondaryStats.value],
    skillStats: [...allSkillStats.value],
  }
}

/** 编辑：把已保存条目回填到表单 */
function startEdit(item: CustomAlluvium) {
  draft.value = {
    id: item.id,
    name: item.name ?? '',
    attributeStats: [...(item.attribute_stats ?? [])],
    secondaryStats: [...(item.secondary_stats ?? [])],
    skillStats: [...(item.skill_stats ?? [])],
  }
}

async function save() {
  if (!draft.value || !canSave.value) return
  const payload: CustomAlluvium = {
    id: draft.value.id,
    name: draft.value.name.trim(),
    attribute_stats: draft.value.attributeStats,
    secondary_stats: draft.value.secondaryStats,
    skill_stats: draft.value.skillStats,
  }
  saving.value = true
  try {
    await saveCustomAlluvium(payload)
    useToast().success(`已保存自定义淤积点「${payload.name}」`)
    draft.value = null
  } catch {
    // 错误提示已由 useCustomAlluviums 弹出，表单保留原值供用户重试
  } finally {
    saving.value = false
  }
}

function promptDelete(item: CustomAlluvium) {
  pendingDelete.value = item
  deleteConfirm.value = true
}

async function confirmDelete() {
  const target = pendingDelete.value
  deleteConfirm.value = false
  if (!target) return
  const targetName = displayName(target)
  try {
    await deleteCustomAlluvium(target.id)
    if (draft.value?.id === target.id) {
      draft.value = null
    }
    useToast().success(`已删除自定义淤积点「${targetName}」`)
  } catch {
    // 错误提示已由 useCustomAlluviums 弹出
  } finally {
    pendingDelete.value = null
  }
}

// 每次打开都重新拉一次：文件可能被手工编辑过，界面不能停在旧快照上
watch(open, (isOpen) => {
  if (!isOpen) return
  draft.value = null
  void fetchCustomAlluviums()
})
</script>
