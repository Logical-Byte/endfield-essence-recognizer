<template>
  <!-- 自定义基质重合检测弹窗 -->
  <v-dialog v-model="overlapDialog" max-width="760" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" color="warning">mdi-alert-circle-outline</v-icon>
        自定义基质重合检测
      </v-card-title>
      <v-card-text>
        <v-alert class="mb-4" type="info" variant="tonal">
          以下自定义基质与内置武器词条重复，可选择移除或切换。
        </v-alert>
        <div
          v-for="(item, idx) in overlapItems"
          :key="item.customStatId"
          class="d-flex align-center mb-3 pa-3 border rounded flex-wrap"
          style="gap: 8px"
        >
          <v-tooltip location="top" open-delay="0" transition="none">
            <template #activator="{ props: tooltipProps }">
              <div
                v-bind="tooltipProps"
                class="overlap-icon-wrapper"
                :class="{ 'weapon-not-owned': !isWeaponOwned(item.customWeaponId) }"
              >
                <custom-stat-icon
                  hide-name
                  :name="item.customName"
                  :skill-stat-id="
                    findCustomStat(item.customWeaponId, customStats)?.stat.skill ?? null
                  "
                  small
                />
              </div>
            </template>
            <span>{{ getOverlapTooltipText(item.customWeaponId) }}</span>
          </v-tooltip>
          <span class="font-weight-bold">{{ item.customName }}</span>
          <v-icon :color="compareColor(idx)" size="small">
            {{ compareIcon(idx) }}
          </v-icon>
          <v-tooltip location="top" open-delay="0" transition="none">
            <template #activator="{ props: tooltipProps }">
              <div
                v-bind="tooltipProps"
                class="overlap-icon-wrapper"
                :class="{ 'weapon-not-owned': !isWeaponOwned(item.switchTargetId) }"
              >
                <item-icon class="weapon-icon-overlap" :item-id="item.switchTargetId" />
              </div>
            </template>
            <span>{{ getOverlapTooltipText(item.switchTargetId) }}</span>
          </v-tooltip>

          <!-- 单个匹配直接显示名称；多个匹配时让用户选择切换目标 -->
          <span v-if="item.matchedWeaponIds.length === 1" class="font-weight-bold">
            {{ item.matchedWeaponNames[0] }}
          </span>
          <v-select
            v-else
            v-model="item.switchTargetId"
            density="compact"
            hide-details
            :items="targetOptions(item)"
            :label="`共有${item.matchedWeaponIds.length}把同词条武器`"
            style="max-width: 260px"
            variant="outlined"
            @update:model-value="onTargetChanged"
          />

          <v-spacer />
          <v-chip-group v-model="item.action" mandatory>
            <v-tooltip location="top" open-delay="0" transition="none">
              <template #activator="{ props: tooltipProps }">
                <v-chip
                  v-bind="tooltipProps"
                  color="error"
                  filter
                  size="small"
                  value="delete"
                  variant="outlined"
                  >移除</v-chip
                >
              </template>
              <span>删除该自定义基质，不再作为宝藏判定条件</span>
            </v-tooltip>
            <v-tooltip location="top" open-delay="0" transition="none">
              <template #activator="{ props: tooltipProps }">
                <v-chip
                  v-bind="tooltipProps"
                  color="primary"
                  filter
                  size="small"
                  value="switch"
                  variant="outlined"
                  >切换</v-chip
                >
              </template>
              <span>删除自定义基质，并将其等级与优先级转移给内置武器</span>
            </v-tooltip>
            <v-chip filter size="small" value="ignore" variant="outlined">本次忽略</v-chip>
            <v-tooltip location="top" open-delay="0" transition="none">
              <template #activator="{ props: tooltipProps }">
                <v-chip
                  v-bind="tooltipProps"
                  filter
                  size="small"
                  value="suppress"
                  variant="outlined"
                  >不再提示</v-chip
                >
              </template>
              <span>
                仅关闭进入宝藏基质页面时的自动重合检测弹窗。<br />
                手动点击「武器总览 → 检查自定义基质重合」仍会显示该条目
              </span>
            </v-tooltip>
          </v-chip-group>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-tooltip
          :disabled="overlapCompareReady"
          location="top"
          text="等级比较结果尚未就绪，请稍候或手动选择"
          transition="none"
        >
          <template #activator="{ props: tooltipProps }">
            <span v-bind="tooltipProps">
              <v-btn
                color="secondary"
                :disabled="!overlapCompareReady"
                variant="outlined"
                @click="autoSelectOverlap"
              >
                一键选择
              </v-btn>
            </span>
          </template>
        </v-tooltip>
        <v-spacer />
        <v-btn :disabled="submitting" @click="overlapDialog = false">取消</v-btn>
        <v-btn color="primary" :loading="submitting" @click="confirmOverlapActions">确认</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts" setup>
import type { OverlapItem } from '@/composables/useOverlapDetection'
import { ref } from 'vue'
import CustomStatIcon from '@/components/CustomStatIcon.vue'
import ItemIcon from '@/components/ItemIcon.vue'
import { useCustomStats } from '@/composables/useCustomStats'
import { useOverlapDetection } from '@/composables/useOverlapDetection'
import { useProfiles } from '@/composables/useProfiles'
import { useToast } from '@/composables/useToast'
import { useWeaponStats } from '@/composables/useWeaponStats'
import { findCustomStat } from '@/utils/gameData/weapon'

const {
  overlapItems,
  overlapDialog,
  overlapCompareReady,
  getOverlapCompareResult,
  autoSelectOverlap,
  fetchOverlapCompareResults,
  getOverlapTooltipText: getOverlapTooltipTextBase,
  confirmOverlapActions: confirmOverlapActionsBase,
} = useOverlapDetection()
const { customStats, fetchCustomStats } = useCustomStats()
const { matrixEntryByWeaponId, isWeaponOwned } = useWeaponStats()
const { treasureMatrix } = useProfiles()
const toast = useToast()

const submitting = ref(false)

/** 获取重合检测的工具提示文本 */
function getOverlapTooltipText(weaponId: string): string {
  return getOverlapTooltipTextBase(weaponId, {
    matrixEntryByWeaponId: matrixEntryByWeaponId.value,
    customStats: customStats.value,
  })
}

/** 多个同词条武器时的下拉选项 */
function targetOptions(item: OverlapItem) {
  return item.matchedWeaponIds.map((id, i) => ({
    title: item.matchedWeaponNames[i] ?? id,
    value: id,
  }))
}

function compareColor(index: number): string {
  const cmp = getOverlapCompareResult(index)
  if (cmp > 0) return 'success'
  if (cmp < 0) return 'error'
  return 'grey'
}

function compareIcon(index: number): string {
  const cmp = getOverlapCompareResult(index)
  if (cmp > 0) return 'mdi-arrow-right-bold'
  if (cmp < 0) return 'mdi-arrow-left-bold'
  return 'mdi-arrow-left-right'
}

/** 切换目标变更后重新比较等级：比较结果是针对具体目标武器的 */
async function onTargetChanged() {
  try {
    await fetchOverlapCompareResults({
      matrixEntryByWeaponId: matrixEntryByWeaponId.value,
      customStats: customStats.value,
    })
  } catch (error) {
    toast.reportError('更新等级比较结果失败', error)
  }
}

/** 确认重合操作 */
async function confirmOverlapActions() {
  submitting.value = true
  try {
    await confirmOverlapActionsBase({
      customStats: customStats.value,
      treasureMatrix: treasureMatrix.value,
      matrixEntryByWeaponId: matrixEntryByWeaponId.value,
    })
    overlapDialog.value = false
    await fetchCustomStats()
  } catch (error) {
    // 弹窗保持打开：部分提交失败时用户需要看到当前选择并可重试
    toast.reportError('确认重合操作失败', error)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.overlap-icon-wrapper {
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;

  &.weapon-not-owned {
    opacity: 0.4;
    filter: grayscale(0.8);
  }
}

.weapon-icon-overlap {
  width: 2rem !important;
  height: 2rem !important;
  flex-shrink: 0;
}
</style>
