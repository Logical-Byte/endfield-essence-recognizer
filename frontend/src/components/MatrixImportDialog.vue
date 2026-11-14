<template>
  <v-dialog v-model="open" max-width="860" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-file-import-outline</v-icon>
        导入宝藏基质
      </v-card-title>

      <v-card-text>
        <!-- 选文件：隐藏原生控件，用按钮代点，避免各主题下的默认外观 -->
        <div class="d-flex flex-wrap align-center ga-3 mb-3">
          <input
            ref="fileInputRef"
            accept=".csv,.json"
            class="d-none"
            type="file"
            @change="onFileChange"
          />
          <v-btn prepend-icon="mdi-file-search-outline" variant="tonal" @click="pickFile">
            选择 CSV / JSON 文件
          </v-btn>
          <span v-if="fileName" class="text-body-2 text-medium-emphasis">{{ fileName }}</span>
        </div>

        <v-alert v-if="parseError" border="start" type="error" variant="tonal">
          {{ parseError }}
        </v-alert>

        <v-alert v-if="emptyNotice" border="start" type="warning" variant="tonal">
          文件里没有可导入的条目（全部被跳过或本来就为空）。
          <template v-if="mode === 'replace' && plan && plan.removed.length > 0">
            当前是替换模式，仍然可以用它清空该账号的 {{ plan.removed.length }} 条配置。
          </template>
        </v-alert>

        <template v-if="plan">
          <!-- 目标账号：不替用户决定，显式选；导入过程中冻结，避免中途改目标 -->
          <div class="text-body-2 text-medium-emphasis mb-1">导入到哪个账号？</div>
          <v-select
            v-model="target"
            class="mb-2"
            density="compact"
            :disabled="importing"
            :items="targetOptions"
            variant="outlined"
          />
          <v-text-field
            v-if="target === NEW_PROFILE"
            v-model="newProfileName"
            class="mb-2"
            density="compact"
            :disabled="importing"
            hide-details="auto"
            label="新账号名称（最长 32 字符）"
            variant="outlined"
          />

          <div class="text-body-2 text-medium-emphasis mb-1">导入方式</div>
          <v-radio-group
            v-model="mode"
            class="mb-2"
            density="compact"
            :disabled="importing"
            hide-details
          >
            <v-radio value="merge">
              <template #label> 合并：按武器覆盖，<strong>文件外的条目保留</strong> </template>
            </v-radio>
            <v-radio value="replace">
              <template #label>
                替换：整表以文件为准，<strong class="text-error">文件外的条目会被删除</strong>
              </template>
            </v-radio>
          </v-radio-group>

          <v-alert border="start" class="mt-3" type="info" variant="tonal">
            将写入 {{ plan.added.length + plan.updated.length }} 条（新增 {{ plan.added.length }} /
            更新 {{ plan.updated.length }}）
            <template v-if="mode === 'replace'">
              · <span class="text-error">将删除 {{ plan.removed.length }} 条</span>
            </template>
            <template v-if="plan.skipped.length > 0">
              · 跳过 {{ plan.skipped.length }} 条（{{ skipSummary }}）
            </template>
          </v-alert>

          <!-- 必须包在 v-expansion-panels 里，单独用 panel 不会展开 -->
          <v-expansion-panels v-if="plan.skipped.length > 0" class="mt-1" variant="accordion">
            <v-expansion-panel>
              <v-expansion-panel-title class="text-body-2">
                查看跳过的 {{ plan.skipped.length }} 条
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-for="item in visibleSkips" :key="`${item.lineNumber}-${item.weaponId}`">
                  第 {{ item.lineNumber }} 行 {{ item.weaponId || '（空武器ID）' }}：{{
                    SKIP_LABELS[item.reason]
                  }}
                </div>
                <div v-if="plan.skipped.length > visibleSkips.length" class="text-medium-emphasis">
                  仅显示前 {{ visibleSkips.length }} 条…
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">取消</v-btn>
        <v-btn
          color="primary"
          :disabled="!canImport"
          :loading="importing"
          variant="flat"
          @click="requestConfirm"
        >
          导入
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 二次确认：说清楚写哪个账号、什么方式、会删多少 -->
  <v-dialog v-model="showConfirm" max-width="520">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" color="warning">mdi-alert-outline</v-icon>
        确认导入
      </v-card-title>
      <v-card-text>
        将向账号「{{ targetProfileName }}」写入
        {{ (plan?.added.length ?? 0) + (plan?.updated.length ?? 0) }} 条宝藏基质配置（{{
          mode === 'merge' ? '合并' : '替换'
        }}）。
        <template v-if="mode === 'replace' && (plan?.removed.length ?? 0) > 0">
          <br />
          <strong class="text-error">
            替换会删除该账号现有的 {{ plan?.removed.length }} 条不在文件中的条目。
          </strong>
        </template>
        <br />
        导入前会把该账号当前配置自动备份到导出目录，出问题可用备份文件按「替换」导回。
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showConfirm = false">取消</v-btn>
        <v-btn color="primary" variant="flat" @click="confirmImport">确认导入</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 导入完成后由用户决定要不要切过去，不替他决定 -->
  <v-dialog v-model="showSwitchPrompt" max-width="460" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" color="success">mdi-check-circle-outline</v-icon>
        导入完成
      </v-card-title>
      <v-card-text>
        已导入到账号「{{ importedTarget }}」。
        <br />
        是否切换到该账号查看？
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showSwitchPrompt = false">留在这里</v-btn>
        <v-btn color="primary" variant="flat" @click="switchToImported">切换过去</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import type { TreasureMatrixEntry } from '@/composables/useProfiles'
import type { ImportMode, ImportSkipReason, ParsedImport } from '@/utils/matrixImportTable'
import { computed, ref, watch } from 'vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useProfiles } from '@/composables/useProfiles'
import { useToast } from '@/composables/useToast'
import { useStaticData } from '@/utils/gameData/staticData'
import { fallbackCustomStatName, toCustomStatId } from '@/utils/gameData/weapon'
import {
  buildImportPlan,
  canApplyPlan,
  entriesToBackupJson,
  parseImportText,
} from '@/utils/matrixImportTable'

const open = defineModel<boolean>({ default: false })

const toast = useToast()
const {
  collection,
  profileNames,
  activeProfileName,
  createProfile,
  deleteProfile,
  switchProfile,
  updateTreasureMatrix,
} = useProfiles()
const { customStats } = useCustomStats()
const { weaponsMap } = useStaticData()

/** 目标账号下拉里代表「新建账号」的哨兵值 */
const NEW_PROFILE = '__new__'
/** 跳过明细最多展示这么多条，避免几百条时把弹窗撑爆 */
const MAX_VISIBLE_SKIPS = 20
/** 导入文件体积上限：几百条基质也就几十 KB，超限基本是选错文件 */
const MAX_IMPORT_BYTES = 8 * 1024 * 1024

const SKIP_LABELS: Record<ImportSkipReason, string> = {
  invalid_row: '缺少武器ID或等级',
  invalid_level: '等级越界',
  not_owned: '文件中标记为未获得',
  unknown_weapon: '未知武器ID',
  missing_custom: '本机没有这条自定义基质',
}

const fileInputRef = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const parsed = ref<ParsedImport | null>(null)
const parseError = ref('')
/** 文件能解析但没有可导入的行：不是错误，替换模式下仍然可以提交 */
const emptyNotice = ref(false)
const target = ref<string>(activeProfileName.value)
const newProfileName = ref('')
const mode = ref<ImportMode>('merge')
const showConfirm = ref(false)
const showSwitchPrompt = ref(false)
const importing = ref(false)
const importedTarget = ref('')
/** 每次选文件递增；读取完成后只接受最新一次选择的结果 */
let fileReadToken = 0

/** 内置武器：weapon_id → 当前静态数据里的显示名 */
const builtinNames = computed(() => {
  const map = new Map<string, string>()
  for (const [weaponId, weapon] of weaponsMap.value) {
    map.set(weaponId, weapon.name)
  }
  return map
})

/** 本机存在的自定义基质：custom:xxx → 显示名 */
const customNames = computed(() => {
  const map = new Map<string, string>()
  for (const [index, stat] of customStats.value.entries()) {
    map.set(toCustomStatId(stat), stat.name || fallbackCustomStatName(index))
  }
  return map
})

const targetOptions = computed(() => {
  const options = [
    { title: `当前账号（${activeProfileName.value}）`, value: activeProfileName.value },
  ]
  for (const name of profileNames.value) {
    if (name !== activeProfileName.value) options.push({ title: name, value: name })
  }
  options.push({ title: '新建账号…', value: NEW_PROFILE })
  return options
})

/** 目标账号名；新建时取输入框里去掉首尾空白的名字 */
const targetProfileName = computed(() =>
  target.value === NEW_PROFILE ? newProfileName.value.trim() : target.value,
)

/** 目标账号现有的条目；新建账号按空表处理 */
const existingEntries = computed<TreasureMatrixEntry[]>(() => {
  if (target.value === NEW_PROFILE) return []
  return collection.value.profiles[target.value]?.treasure_matrix ?? []
})

/**
 * 目标账号的独立优先级偏好。
 *
 * 它覆盖「没配基质但手设过优先级」的武器，是矩阵条目 priority 的权威来源；
 * 传给规划器后，导入才不会把这类偏好按 0 写回。
 */
const targetPriorities = computed<Record<string, number>>(() => {
  if (target.value === NEW_PROFILE) return {}
  return collection.value.profiles[target.value]?.weapon_priorities ?? {}
})

const plan = computed(() => {
  const result = parsed.value
  if (!result) return null
  return buildImportPlan({
    rows: result.rows,
    skipped: result.skipped,
    existing: existingEntries.value,
    builtinNames: builtinNames.value,
    customNames: customNames.value,
    weaponPriorities: targetPriorities.value,
    mode: mode.value,
  })
})

const visibleSkips = computed(() => plan.value?.skipped.slice(0, MAX_VISIBLE_SKIPS) ?? [])

/** 按原因汇总，放在概览里一行说完 */
const skipSummary = computed(() => {
  const counts = new Map<ImportSkipReason, number>()
  for (const item of plan.value?.skipped ?? []) {
    counts.set(item.reason, (counts.get(item.reason) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([reason, count]) => `${SKIP_LABELS[reason]} ${count}`)
    .join('、')
})

const canImport = computed(() => {
  const currentPlan = plan.value
  if (!currentPlan || importing.value) return false
  if (targetProfileName.value === '') return false
  return canApplyPlan(currentPlan, mode.value)
})

function pickFile() {
  fileInputRef.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // 同一个文件连续选两次不会触发 change，读完清空 value 才能重复导入同一份
  input.value = ''
  if (!file) return

  // 连选两个文件时以最后一次为准：读到一半被后来者顶掉的结果必须丢弃
  const token = ++fileReadToken
  fileName.value = file.name
  parseError.value = ''
  emptyNotice.value = false
  try {
    if (file.size > MAX_IMPORT_BYTES) {
      throw new Error(
        `文件超过 ${Math.round(MAX_IMPORT_BYTES / 1024 / 1024)} MB，请先裁剪到只保留需要导入的行`,
      )
    }
    const text = await file.text()
    if (token !== fileReadToken) return
    const result = parseImportText(text)
    parsed.value = result
    emptyNotice.value = result.rows.length === 0
  } catch (error) {
    if (token !== fileReadToken) return
    parsed.value = null
    parseError.value = error instanceof Error ? error.message : String(error)
  }
}

/** 先把目标账号当前配置写成快照；失败则中止导入，不拿没有退路的操作冒险 */
async function backupCurrentMatrix(name: string, entries: readonly TreasureMatrixEntry[]) {
  const content = entriesToBackupJson(name, entries, new Date().toISOString())
  const res = await fetch('/api/export/treasure_matrix/table', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      format: 'json',
      content,
      file_stem: `${name}_导入前备份`,
      open_folder: false,
    }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  const data = await res.json()
  if (!data.success) throw new Error(data.message)
  return data.file_name as string
}

function requestConfirm() {
  if (!canImport.value) return
  if (target.value === NEW_PROFILE && targetProfileName.value in collection.value.profiles) {
    toast.error(`账号「${targetProfileName.value}」已存在，请改选已有的同名账号`)
    return
  }
  showConfirm.value = true
}

async function confirmImport() {
  const currentPlan = plan.value
  if (!currentPlan) return

  showConfirm.value = false
  importing.value = true
  // 目标与模式在等待备份期间可能被改动（备份请求在途时控件还没禁用），
  // 整个导入必须用同一份快照，否则会建错账号或漏建账号。
  const name = targetProfileName.value
  const creatingNewProfile = target.value === NEW_PROFILE
  const entries = currentPlan.entries
  const written = currentPlan.added.length + currentPlan.updated.length
  let backupFileName = ''
  let profileCreated = false
  try {
    if (existingEntries.value.length > 0) {
      try {
        backupFileName = await backupCurrentMatrix(name, existingEntries.value)
      } catch (error) {
        toast.reportError('备份当前配置失败，已取消导入', error)
        return
      }
    }

    if (creatingNewProfile) {
      await createProfile(name)
      profileCreated = true
    }
    await updateTreasureMatrix(entries, name)

    importedTarget.value = name
    toast.success(
      backupFileName
        ? `已导入 ${written} 条到「${name}」，原配置备份为 ${backupFileName}`
        : `已导入 ${written} 条到「${name}」`,
    )
    open.value = false
    // 目标是当前账号就不用问；导入到别的账号则交给用户决定要不要切过去
    if (name !== activeProfileName.value) showSwitchPrompt.value = true
  } catch (error) {
    // 账号已经建出来但矩阵没写进去时撤掉它：否则会留下空账号，
    // 用户重试还会撞上「账号已存在」
    if (profileCreated) {
      try {
        await deleteProfile(name)
      } catch {
        // 回滚失败不改变主错误：原始失败信息仍是用户最需要看到的
      }
    }
    toast.reportError('导入宝藏基质失败', error)
  } finally {
    importing.value = false
  }
}

async function switchToImported() {
  showSwitchPrompt.value = false
  await switchProfile(importedTarget.value)
}

watch(open, (opened) => {
  if (!opened) return
  // 每次打开都从干净状态开始，避免上一次的文件与目标账号残留
  fileName.value = ''
  parsed.value = null
  parseError.value = ''
  emptyNotice.value = false
  target.value = activeProfileName.value
  newProfileName.value = ''
  mode.value = 'merge'
})
</script>
