<template>
  <v-menu>
    <template #activator="{ props }">
      <v-btn prepend-icon="mdi-account-switch" variant="text" v-bind="props">
        {{ activeProfileName }}
        <v-icon end>mdi-chevron-down</v-icon>
      </v-btn>
    </template>
    <v-list density="compact">
      <v-list-subheader>切换账号</v-list-subheader>
      <v-list-item
        v-for="name in profileNames"
        :key="name"
        :active="name === activeProfileName"
        @click="onSwitch(name)"
      >
        <template #prepend>
          <v-icon :icon="name === activeProfileName ? 'mdi-account-check' : 'mdi-account'" />
        </template>
        <v-list-item-title>{{ name }}</v-list-item-title>
        <template #append>
          <div class="d-flex ga-1">
            <v-tooltip location="bottom" text="重命名账号">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-pencil"
                  size="x-small"
                  variant="text"
                  @click.stop="startRename(name)"
                />
              </template>
            </v-tooltip>
            <v-tooltip
              location="bottom"
              :text="name === defaultProfileName ? '默认账号不可删除' : '删除账号'"
            >
              <template #activator="{ props }">
                <span v-bind="props">
                  <v-btn
                    :color="name === defaultProfileName ? undefined : 'error'"
                    :disabled="name === defaultProfileName"
                    icon="mdi-delete"
                    size="x-small"
                    variant="text"
                    @click.stop="startDelete(name)"
                  />
                </span>
              </template>
            </v-tooltip>
            <v-tooltip location="bottom" text="清空数据">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  color="error"
                  icon="mdi-delete-outline"
                  size="x-small"
                  variant="outlined"
                  @click.stop="startClearData(name)"
                />
              </template>
            </v-tooltip>
          </div>
        </template>
      </v-list-item>
      <v-divider />
      <v-list-item @click="showNewProfileDialog = true">
        <template #prepend>
          <v-icon icon="mdi-plus" />
        </template>
        <v-list-item-title>新建账号</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>

  <!-- 新建账号对话框 -->
  <v-dialog v-model="showNewProfileDialog" max-width="400">
    <v-card>
      <v-card-title>新建账号</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="newProfileName"
          label="账号名称"
          :rules="[(v) => !!v.trim() || '名称不能为空']"
          variant="outlined"
          @keyup.enter="onCreate"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showNewProfileDialog = false">取消</v-btn>
        <v-btn color="primary" :disabled="!newProfileName.trim()" @click="onCreate"> 创建 </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 重命名对话框 -->
  <v-dialog v-model="showRenameDialog" max-width="400">
    <v-card>
      <v-card-title>重命名账号</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="renameNewName"
          label="新名称"
          :rules="[(v) => !!v.trim() || '名称不能为空']"
          variant="outlined"
          @keyup.enter="onRename"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showRenameDialog = false">取消</v-btn>
        <v-btn color="primary" :disabled="!renameNewName.trim()" @click="onRename"> 确认 </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认对话框 -->
  <v-dialog v-model="showDeleteConfirm" max-width="400">
    <v-card>
      <v-card-title class="text-error">确认删除</v-card-title>
      <v-card-text>
        确定要删除账号「{{ deleteTargetName }}」吗？此操作不可撤销。
        <template v-if="deleteIsActive">
          <br />该账号正在使用中，删除后将自动切换回默认账号「{{ defaultProfileName }}」。
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showDeleteConfirm = false">取消</v-btn>
        <v-btn color="error" @click="onDelete">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 清空数据确认对话框 -->
  <v-dialog v-model="showClearDataConfirm" max-width="440">
    <v-card>
      <v-card-title class="text-error">确认清空数据</v-card-title>
      <v-card-text>
        确定要清空账号「{{
          clearDataTargetName
        }}」的数据吗？账号会保留，但该账号下所有已扫描的宝藏基质与优先级设置都会被清空，此操作不可撤销。
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showClearDataConfirm = false">取消</v-btn>
        <v-btn color="error" @click="onClearData">清空数据</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import { onMounted, ref } from 'vue'
import { useProfiles } from '@/composables/useProfiles'
import { useToast } from '@/composables/useToast'

const {
  activeProfileName,
  defaultProfileName,
  profileNames,
  fetchProfiles,
  switchProfile,
  renameProfile,
  deleteProfile,
  clearProfileData,
} = useProfiles()

// 账号名称最大长度
const PROFILE_NAME_MAX_LEN = 32
// 账号名称非法字符正则表达式
const PROFILE_NAME_INVALID_RE = /[/\\\0\n\r\t]/

const showNewProfileDialog = ref(false)
const showRenameDialog = ref(false)
const showDeleteConfirm = ref(false)
const showClearDataConfirm = ref(false)
const newProfileName = ref('')
const renameNewName = ref('')
const renameOldName = ref('')
const deleteTargetName = ref('')
const deleteIsActive = ref(false)
const clearDataTargetName = ref('')

const toast = useToast()

/**
 * 提示校验错误。
 *
 * 接口错误由 useProfiles 统一推送到全局提示，这里只负责本地校验的反馈，
 * 否则同一个失败会弹两次。
 */
function notifyError(message: string) {
  toast.error(message)
}

/**
 * 验证账号名称是否合法。
 * @param name 账号名称
 * @returns 错误信息，如果合法则返回 null
 */
function validateProfileName(name: string): string | null {
  const trimmed = name.trim()
  if (!trimmed) return '名称不能为空'
  if (trimmed.length > PROFILE_NAME_MAX_LEN) return `名称不能超过 ${PROFILE_NAME_MAX_LEN} 个字符`
  if (PROFILE_NAME_INVALID_RE.test(trimmed)) return '名称包含非法字符'
  return null
}

onMounted(() => {
  // 失败信息已由 useProfiles 推送到全局提示，这里只需吞掉 rejection
  void fetchProfiles().catch(() => {})
})

/**
 * 切换到指定账号。
 */
async function onSwitch(name: string) {
  try {
    await switchProfile(name)
  } catch {
    // 错误提示已由 useProfiles 统一推送
  }
}

/**
 * 创建新账号。
 */
async function onCreate() {
  const name = newProfileName.value.trim()
  const validationError = validateProfileName(name)
  if (validationError) {
    notifyError(validationError)
    return
  }
  try {
    await switchProfile(name)
    showNewProfileDialog.value = false
    newProfileName.value = ''
  } catch {
    // 错误提示已由 useProfiles 统一推送
  }
}

/**
 * 开始重命名账号。
 */
function startRename(name: string) {
  renameOldName.value = name
  renameNewName.value = name
  showRenameDialog.value = true
}

/**
 * 执行重命名操作。
 */
async function onRename() {
  const newName = renameNewName.value.trim()
  const validationError = validateProfileName(newName)
  if (validationError) {
    notifyError(validationError)
    return
  }
  // 名称未修改时直接关闭对话框，避免无意义的网络请求
  if (newName === renameOldName.value) {
    showRenameDialog.value = false
    return
  }
  try {
    await renameProfile(renameOldName.value, newName)
    showRenameDialog.value = false
  } catch {
    // 错误提示已由 useProfiles 统一推送
  }
}

/**
 * 开始删除账号。
 */
function startDelete(name: string) {
  // 默认账号的删除按钮已置灰禁用，此处防御性拦截
  if (name === defaultProfileName.value) return
  deleteTargetName.value = name
  deleteIsActive.value = name === activeProfileName.value
  showDeleteConfirm.value = true
}

/**
 * 执行删除操作。
 */
async function onDelete() {
  try {
    await deleteProfile(deleteTargetName.value)
    showDeleteConfirm.value = false
  } catch {
    // 错误提示已由 useProfiles 统一推送
  }
}

/**
 * 开始清空账号数据（账号保留，宝藏基质与优先级设置被清空）。
 */
function startClearData(name: string) {
  clearDataTargetName.value = name
  showClearDataConfirm.value = true
}

/**
 * 执行清空数据操作。
 */
async function onClearData() {
  try {
    await clearProfileData(clearDataTargetName.value)
    showClearDataConfirm.value = false
    toast.success(`已清空账号「${clearDataTargetName.value}」的数据`)
  } catch {
    // 错误提示已由 useProfiles 统一推送
  }
}
</script>
