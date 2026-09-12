<template>
  <v-container>
    <v-expansion-panels color="primary-darken-1" :model-value="[0, 1, 2, 3, 4]" multiple>
      <!-- Panel 0: 武器基质预设 -->
      <v-expansion-panel :value="0">
        <v-expansion-panel-title>武器基质预设</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>将以下武器所对应的基质视为宝藏</h2>
          <h3>按稀有度快捷选择</h3>
          <div class="d-flex flex-row flex-wrap gc-4">
            <v-checkbox
              v-for="rarity in [6, 5, 4, 3]"
              :key="rarity"
              :color="rarityColors[rarity]"
              density="compact"
              hide-details
              :indeterminate="isRarityPartiallySelected(rarity)"
              :model-value="isRarityAllSelected(rarity)"
              @click="raritySelectAll(rarity, !isRarityAllSelected(rarity))"
            >
              <template #label>
                <span :style="{ color: rarityColors[rarity] }">{{ rarity }}★</span>
              </template>
            </v-checkbox>
          </div>
          <v-divider class="my-4" />
          <template v-for="weaponType in sortedWeaponTypes" :key="weaponType.id">
            <h3>
              <v-checkbox
                density="compact"
                hide-details
                :indeterminate="isTypePartiallySelected(weaponType.id)"
                :model-value="isTypeAllSelected(weaponType.id)"
                @click="typeSelectAll(weaponType.id, !isTypeAllSelected(weaponType.id))"
              >
                <template #prepend>
                  <img
                    :alt="weaponType.name"
                    class="group-icon me-2"
                    :src="weaponType.iconUrl"
                    :style="{
                      filter: theme.current.value.dark ? 'none' : 'invert(1)',
                    }"
                  />
                  <h3 class="ma-0">{{ weaponType.name }}</h3>
                </template>
              </v-checkbox>
            </h3>
            <div class="weapon-grid">
              <div
                v-for="weaponId in weaponType.weaponIds"
                :key="weaponId"
                class="d-flex flex-column align-center"
                :class="{
                  'weapon-disabled': !selectedWeaponIds.includes(weaponId),
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
                  <v-badge
                    v-if="weaponEssenceCounts[weaponId]"
                    color="primary"
                    :content="weaponEssenceCounts[weaponId]"
                    location="top end"
                  >
                    <item-icon :item-id="weaponId" show-item-name />
                  </v-badge>
                  <item-icon v-else :item-id="weaponId" show-item-name />
                </div>
                <v-tooltip activator="parent" location="bottom">
                  {{ getWeaponStatsDescription(weaponId) }}
                </v-tooltip>
              </div>
            </div>
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Panel 1: 宝藏基质判定规则 -->
      <v-expansion-panel :value="1">
        <v-expansion-panel-title>宝藏基质判定规则</v-expansion-panel-title>
        <v-expansion-panel-text>
          <!-- 1-A: 高等级属性判定 -->
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
              <v-radio-group
                v-model="highLevelTreasureMatchMode"
                color="primary"
                density="compact"
                hide-details
                label="满足方式"
              >
                <v-radio value="only">
                  <template #label>
                    <span>仅：只检查</span>
                    <v-chip
                      class="mx-1"
                      :color="highLevelTreasureOnlyCheckAttribute ? 'primary' : 'grey'"
                      size="small"
                      :variant="highLevelTreasureOnlyCheckAttribute ? 'flat' : 'outlined'"
                      @click.stop="
                        highLevelTreasureOnlyCheckAttribute = !highLevelTreasureOnlyCheckAttribute
                      "
                      >基础</v-chip
                    >
                    <v-chip
                      class="mx-1"
                      :color="highLevelTreasureOnlyCheckSecondary ? 'primary' : 'grey'"
                      size="small"
                      :variant="highLevelTreasureOnlyCheckSecondary ? 'flat' : 'outlined'"
                      @click.stop="
                        highLevelTreasureOnlyCheckSecondary = !highLevelTreasureOnlyCheckSecondary
                      "
                      >附加</v-chip
                    >
                    <v-chip
                      class="mx-1"
                      :color="highLevelTreasureOnlyCheckSkill ? 'primary' : 'grey'"
                      size="small"
                      :variant="highLevelTreasureOnlyCheckSkill ? 'flat' : 'outlined'"
                      @click.stop="
                        highLevelTreasureOnlyCheckSkill = !highLevelTreasureOnlyCheckSkill
                      "
                      >技能</v-chip
                    >
                    <span>项</span>
                  </template>
                </v-radio>
                <v-radio label="和：三项全部 ≥ 设定值" value="all" />
                <v-radio label="或：任一项 ≥ 设定值(推荐)" value="any" />
                <v-radio value="sum">
                  <template #label>
                    <span class="me-2">三项相加 ≥</span>
                    <v-text-field
                      v-model.number="highLevelTreasureSumThreshold"
                      density="compact"
                      :disabled="!highLevelTreasureEnabled || highLevelTreasureMatchMode !== 'sum'"
                      hide-details
                      :max="15"
                      :min="3"
                      style="max-width: 90px"
                      type="number"
                      variant="outlined"
                      @click.stop
                    />
                  </template>
                </v-radio>
              </v-radio-group>
            </v-col>
            <v-col cols="12" md="8">
              <v-slider
                v-model="highLevelTreasureAttributeThreshold"
                color="primary"
                :disabled="!highLevelTreasureEnabled"
                label="基础属性"
                :max="6"
                :min="1"
                show-ticks="always"
                :step="1"
                thumb-label
                tick-size="4"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
              <v-slider
                v-model="highLevelTreasureSecondaryThreshold"
                color="primary"
                :disabled="!highLevelTreasureEnabled"
                label="附加属性"
                :max="6"
                :min="1"
                show-ticks="always"
                :step="1"
                thumb-label
                tick-size="4"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
              <v-slider
                v-model="highLevelTreasureSkillThreshold"
                color="primary"
                :disabled="!highLevelTreasureEnabled"
                label="技能属性"
                :max="3"
                :min="1"
                show-ticks="always"
                :step="1"
                thumb-label
                tick-size="4"
                :ticks="{ 1: '+1', 2: '+2', 3: '+3' }"
              >
                <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
              </v-slider>
            </v-col>
          </v-row>

          <v-divider class="my-4" />

          <!-- 1-B: 额外属性匹配 -->
          <div class="d-flex align-center flex-wrap ga-2">
            <h2>自定义基质 | 额外将以下属性的基质视为宝藏</h2>
            <v-spacer />
            <v-btn
              color="primary"
              prepend-icon="mdi-auto-fix"
              size="small"
              variant="tonal"
              @click="prepareFillAllCombinations"
            >
              一键补齐全部组合
              <v-tooltip activator="parent" location="bottom" max-width="360">
                按「基础 × 附加 × 技能」生成全部
                {{ totalCombinationCount }}
                种属性组合，自动跳过内置武器已覆盖的组合与列表中已有的组合。
              </v-tooltip>
            </v-btn>
            <v-btn
              v-if="treasureEssenceStats.length > 0"
              color="error"
              prepend-icon="mdi-delete-sweep"
              size="small"
              variant="tonal"
              @click="clearAllDialog = true"
            >
              清空全部
            </v-btn>
          </div>
          <v-row v-if="customStatPageCount > 1" align="center" class="mt-0">
            <v-col class="d-flex align-center flex-wrap ga-4 justify-center" cols="12">
              <v-pagination
                v-model="customStatPage"
                density="comfortable"
                :length="customStatPageCount"
                rounded="circle"
                :total-visible="7"
              />
              <span class="text-caption text-medium-emphasis">
                共 {{ treasureEssenceStats.length }} 条，每页 {{ CUSTOM_STAT_PAGE_SIZE }} 条
              </span>
            </v-col>
          </v-row>
          <v-row
            v-for="{ stat: essenceStat, index } in pagedCustomStats"
            :key="essenceStat.id"
            align="center"
          >
            <v-col cols="12" md="3" sm="6">
              <v-text-field
                v-model="essenceStat.name"
                density="comfortable"
                hide-details
                label="自定义名称"
                placeholder="可选，用于武器总览显示"
                prepend-inner-icon="mdi-diamond-stone"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" md="3" sm="6">
              <v-select
                v-model="essenceStat.attribute"
                clearable
                density="comfortable"
                hide-details
                :items="
                  allAttributeStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                label="基础属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" md="3" sm="6">
              <v-select
                v-model="essenceStat.secondary"
                clearable
                density="comfortable"
                hide-details
                :items="
                  allSecondaryStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                label="附加属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12" md="3" sm="6">
              <v-select
                v-model="essenceStat.skill"
                clearable
                density="comfortable"
                hide-details
                :items="
                  allSkillStats.map((gemTermId) => ({
                    title: getGemTagName(gemTermId),
                    value: gemTermId,
                  }))
                "
                label="技能属性"
                variant="outlined"
              />
            </v-col>
            <v-col cols="12">
              <div class="d-flex ga-1">
                <v-btn
                  color="primary"
                  icon="mdi-plus"
                  variant="text"
                  @click="treasureEssenceStats.splice(index, 0, newCustomStat())"
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
              </div>
            </v-col>
          </v-row>
          <v-row v-if="treasureEssenceStats.length === 0" class="my-4">
            <v-col cols="12">
              <v-btn color="primary" prepend-icon="mdi-plus" @click="appendCustomStat">
                添加自定义宝藏基质
              </v-btn>
            </v-col>
          </v-row>
          <v-row v-else>
            <v-col cols="12" md="9" sm="6" />
            <v-col cols="12" md="3" sm="6">
              <v-btn color="primary" icon="mdi-plus" variant="text" @click="appendCustomStat" />
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Panel 2: 扫描行为设置 -->
      <v-expansion-panel :value="2">
        <v-expansion-panel-title>扫描行为设置</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>遇到非无瑕基质(紫色及以下)时，该如何操作？</h2>
          <v-radio-group v-model="nonFiveStarBehavior" color="primary" density="comfortable" inline>
            <v-radio label="当作无瑕基质并继续操作" value="process" />
            <v-radio label="跳过它并继续操作" value="skip" />
            <v-radio label="结束本次扫描" value="stop" />
            <v-radio label="仅高等级判定（只按高等级词条，不匹配武器）" value="high_level_only" />
          </v-radio-group>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            "仅高等级判定"会使用最上方"启用高等级基质属性词条判定"的设置，启用"与无瑕基质区分设置"后可单独设置。
          </v-alert>

          <!-- 非无瑕基质高等级判定设置 -->
          <v-expand-transition>
            <div v-if="nonFiveStarBehavior === 'high_level_only'">
              <v-divider class="my-4" />
              <h2>非无瑕基质(紫色及以下)高等级属性词条判定设置</h2>
              <v-switch
                v-model="nonFiveStarSeparateHighLevelSettings"
                color="primary"
                density="comfortable"
                hide-details
                label="与无瑕基质区分设置（为非无瑕基质(紫色及以下)启用独立的高等级判定阈值）"
              />
              <v-alert border="start" class="mb-4" type="info" variant="tonal">
                启用后，非无瑕基质(紫色及以下)将使用独立的高等级判定阈值；否则使用最上方"启用高等级基质属性词条判定"的设置。
              </v-alert>
              <v-expand-transition>
                <div v-if="nonFiveStarSeparateHighLevelSettings">
                  <v-row align="center" class="my-4">
                    <v-col cols="12" md="4">
                      <v-radio-group
                        v-model="nonFiveStarHighLevelMatchMode"
                        color="primary"
                        density="compact"
                        hide-details
                        label="满足方式"
                      >
                        <v-radio value="only">
                          <template #label>
                            <span>仅：只检查</span>
                            <v-chip
                              class="mx-1"
                              :color="nonFiveStarHighLevelOnlyCheckAttribute ? 'primary' : 'grey'"
                              size="small"
                              :variant="
                                nonFiveStarHighLevelOnlyCheckAttribute ? 'flat' : 'outlined'
                              "
                              @click.stop="
                                nonFiveStarHighLevelOnlyCheckAttribute =
                                  !nonFiveStarHighLevelOnlyCheckAttribute
                              "
                              >基础</v-chip
                            >
                            <v-chip
                              class="mx-1"
                              :color="nonFiveStarHighLevelOnlyCheckSecondary ? 'primary' : 'grey'"
                              size="small"
                              :variant="
                                nonFiveStarHighLevelOnlyCheckSecondary ? 'flat' : 'outlined'
                              "
                              @click.stop="
                                nonFiveStarHighLevelOnlyCheckSecondary =
                                  !nonFiveStarHighLevelOnlyCheckSecondary
                              "
                              >附加</v-chip
                            >
                            <v-chip
                              class="mx-1"
                              :color="nonFiveStarHighLevelOnlyCheckSkill ? 'primary' : 'grey'"
                              size="small"
                              :variant="nonFiveStarHighLevelOnlyCheckSkill ? 'flat' : 'outlined'"
                              @click.stop="
                                nonFiveStarHighLevelOnlyCheckSkill =
                                  !nonFiveStarHighLevelOnlyCheckSkill
                              "
                              >技能</v-chip
                            >
                            <span>项</span>
                          </template>
                        </v-radio>
                        <v-radio label="和：三项全部 ≥ 设定值" value="all" />
                        <v-radio label="或：任一项 ≥ 设定值(推荐)" value="any" />
                        <v-radio value="sum">
                          <template #label>
                            <span class="me-2">三项相加 ≥</span>
                            <v-text-field
                              v-model.number="nonFiveStarHighLevelSumThreshold"
                              density="compact"
                              :disabled="nonFiveStarHighLevelMatchMode !== 'sum'"
                              hide-details
                              :max="15"
                              :min="3"
                              style="max-width: 90px"
                              type="number"
                              variant="outlined"
                              @click.stop
                            />
                          </template>
                        </v-radio>
                      </v-radio-group>
                    </v-col>
                    <v-col cols="12" md="8">
                      <v-slider
                        v-model="nonFiveStarHighLevelAttributeThreshold"
                        color="primary"
                        label="基础属性"
                        :max="6"
                        :min="1"
                        show-ticks="always"
                        :step="1"
                        thumb-label
                        tick-size="4"
                        :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
                      >
                        <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
                      </v-slider>
                      <v-slider
                        v-model="nonFiveStarHighLevelSecondaryThreshold"
                        color="primary"
                        label="附加属性"
                        :max="6"
                        :min="1"
                        show-ticks="always"
                        :step="1"
                        thumb-label
                        tick-size="4"
                        :ticks="{ 1: '+1', 2: '+2', 3: '+3', 4: '+4', 5: '+5', 6: '+6' }"
                      >
                        <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
                      </v-slider>
                      <v-slider
                        v-model="nonFiveStarHighLevelSkillThreshold"
                        color="primary"
                        label="技能属性"
                        :max="3"
                        :min="1"
                        show-ticks="always"
                        :step="1"
                        thumb-label
                        tick-size="4"
                        :ticks="{ 1: '+1', 2: '+2', 3: '+3' }"
                      >
                        <template #thumb-label="{ modelValue }">+{{ modelValue }}</template>
                      </v-slider>
                    </v-col>
                  </v-row>
                </div>
              </v-expand-transition>
            </div>
          </v-expand-transition>

          <v-divider class="my-4" />

          <h2>同类型宝藏基质达到指定数量后，该如何处理？</h2>
          <v-row align="center">
            <v-col cols="12" md="6">
              <v-switch
                v-model="sameTypeTreasureLimitEnabled"
                color="primary"
                density="comfortable"
                hide-details
                label="启用同类型宝藏基质数量上限"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model.number="sameTypeTreasureLimit"
                density="comfortable"
                :disabled="!sameTypeTreasureLimitEnabled"
                hide-details
                label="每类最多保留数量"
                :min="1"
                type="number"
                variant="outlined"
              />
            </v-col>
          </v-row>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            启用后，同一组基础、附加、技能的宝藏基质总保有量（含"宝藏基质"页面已保存的）达到上限后，后续同类型基质会视为"养成材料"并执行"养成材料"操作。关闭后，扫描到的宝藏基质仍会按武器分配（每把武器
            1 枚）记录到"宝藏基质"页面，多余的保留但不落盘。
          </v-alert>

          <!-- 新增：分组模式 -->
          <v-row align="center" class="mt-2">
            <v-col cols="12">
              <v-radio-group
                v-model="sameTypeGroupMode"
                color="primary"
                density="comfortable"
                :disabled="!sameTypeTreasureLimitEnabled"
                inline
                label="同类型划分方式"
              >
                <v-radio label="按武器划分（每把武器独立计数）" value="by_weapon" />
                <v-radio label="按基质划分（词条名称完全一致即为同类型）" value="by_stat" />
              </v-radio-group>
            </v-col>
          </v-row>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            "按武器划分"时建议保留数为 1
            ；"按基质划分"时的数量若超过了武器数，多余基质不保存到本地。
          </v-alert>

          <!-- 新增：非降级原则过滤（仅按武器划分时可用） -->
          <v-row align="center" class="mt-2">
            <v-col cols="12">
              <v-switch
                v-model="sameTypeNonDowngradeFilter"
                color="primary"
                density="comfortable"
                hide-details
                label="非降级原则过滤（过滤无法升级武器已有基质的矩阵）"
              />
              <v-alert border="start" class="mt-2" type="info" variant="tonal">
                启用后，每个词条都 ≥
                旧等级才会被保留。开启数量上限时，无法升级任何匹配武器的将视为养成材料；关闭数量上限时则保留但不落盘。此选项在"留大弃小"规则前生效。
              </v-alert>
            </v-col>
          </v-row>

          <!-- 新增：留大弃小 -->
          <v-row align="center" class="mt-2">
            <v-col cols="12">
              <v-switch
                v-model="sameTypeKeepBest"
                color="primary"
                density="comfortable"
                hide-details
                label="留大弃小（同类型中保留等级更高的基质）"
              />
              <v-alert border="start" class="mt-2" type="info" variant="tonal">
                启用后，如果新基质的词条等级更高，则替换旧的并同步到"宝藏基质"页面。开启数量上限时更差的视为养成材料，关闭数量上限时更差的保留但不落盘。扫描开始前会读取"宝藏基质"页面为基准。
              </v-alert>
              <v-radio-group
                v-model="sameTypeKeepBestMode"
                class="mt-2"
                color="primary"
                density="compact"
                :disabled="!sameTypeKeepBest"
                hide-details
                label="等级比较方式"
              >
                <v-radio label="依次比对（A → B → C）" value="sequential" />
                <v-radio label="和值比对（A + B + C）" value="sum" />
                <v-radio label="冷却脂消耗（按升级累计需要消耗的冷却脂排序）" value="grease" />
                <v-radio label="概率和值（按升级难度加权）" value="weighted_sum" />
              </v-radio-group>
            </v-col>
          </v-row>

          <v-divider class="my-4" />

          <h2>扫描前跳过已处理过的基质</h2>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            启用后，每页开始扫描前会先识别卡片左下角的状态角标，被识别的基质直接跳过（不点击、不识别），
            从而节省扫描时间。识别不确定的卡片仍按原流程点击后判定，不会漏扫。
          </v-alert>
          <v-switch
            v-model="skipLockedEssence"
            color="primary"
            density="comfortable"
            hide-details
            label="跳过已锁定的基质"
          />
          <v-alert border="start" class="mt-2 mb-4" type="info" variant="tonal">
            已锁定的基质是你决定保留的，扫描时可以安全跳过。
          </v-alert>
          <v-switch
            v-model="skipDeprecatedEssence"
            color="primary"
            density="comfortable"
            hide-details
            label="跳过已弃用的基质"
          />
          <v-alert border="start" class="mt-2 mb-4" type="info" variant="tonal">
            已弃用的基质是你标记为养成材料的，扫描时可以安全跳过。
          </v-alert>

          <h2>扫描时自动翻页</h2>
          <v-switch
            v-model="autoPageFlip"
            color="primary"
            density="comfortable"
            hide-details
            label="启用自动翻页扫描"
          />
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            启用后，扫描完当前页会自动拖动翻页继续扫描，直到滚动条到达底部。
          </v-alert>
          <v-expand-transition>
            <div v-if="autoPageFlip" class="mt-2">
              <v-switch
                v-model="fixGridRowOffsetAfterPageFlip"
                color="primary"
                density="comfortable"
                hide-details
                label="修复翻页后网格行偏移"
              />
              <v-alert border="start" class="mt-2" type="info" variant="tonal">
                启用后，翻页结束时会根据基质间的间隙暗带匹配，微调页面。
              </v-alert>
              <v-switch
                v-model="fixPageFlipOverscroll"
                class="mt-2"
                color="primary"
                density="comfortable"
                hide-details
                label="修正翻页滚动过量（实验性质）"
              />
              <v-alert border="start" class="mt-2" type="warning" variant="tonal">
                默认关闭。启用后，若翻页后第一行被判定为已扫描过的重复基质，会向上调整 3/4
                行并重扫第一行。
              </v-alert>
            </div>
          </v-expand-transition>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Panel 3: 基质操作规则 -->
      <v-expansion-panel :value="3">
        <v-expansion-panel-title>基质操作规则</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>遇到宝藏基质或者养成材料时，该如何操作？</h2>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            "宝藏基质"和"养成材料"仅为分类简称，不是宝藏的基质都视为养成材料。
          </v-alert>
          <v-row>
            <v-col cols="12" md="6">
              <h3>对于<span class="text-success">宝藏基质</span>，我们</h3>
              <v-radio-group v-model="treasureAction" color="primary" density="comfortable">
                <v-radio label="不去动它" value="keep" />
                <v-radio label="把它锁上" value="lock" />
                <v-radio disabled label="把它标记为弃用" value="deprecate" />
                <v-radio label="如果锁着，则解锁" value="unlock"></v-radio>
                <v-radio label="如果已标记为弃用，则取消弃用" value="undeprecate" />
                <v-radio label="解锁且取消弃用" value="unlock_and_undeprecate"></v-radio>
                <v-radio disabled label="如果没有上锁，则弃用" value="deprecate_if_not_locked" />
                <v-radio label="如果没有弃用，则上锁" value="lock_if_not_deprecated" />
                <v-radio disabled label="如果缺少词条，则弃用" value="deprecate_if_missing_stats" />
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
                <v-radio label="如果缺少词条，则弃用" value="deprecate_if_missing_stats" />
              </v-radio-group>
            </v-col>
          </v-row>

          <v-divider class="my-4" />

          <h2>对于<span class="text-warning">冗余基质</span>，我们</h2>
          <p class="text-body-2 text-medium-emphasis mb-2">
            <strong>冗余基质：</strong
            >本次扫描中，同一把武器在后面扫到了相同/更好等级，先扫到的那一枚为「冗余基质」。<br />
            <strong>启用条件：</strong
            >右侧开启「冗余清理（实验性）」，且分组为「按武器划分」并「开启数量上限」，否则不产生任何记录与操作。<br />
          </p>
          <v-row align="center">
            <v-col cols="12" md="6">
              <v-radio-group v-model="redundantAction" color="primary" density="comfortable">
                <v-radio label="不去动它" value="keep" />
                <v-radio label="把它锁上" value="lock" />
                <v-radio label="把它标记为弃用" value="deprecate" />
                <v-radio label="如果锁着，则解锁" value="unlock" />
                <v-radio label="如果已标记为弃用，则取消弃用" value="undeprecate" />
                <v-radio label="解锁且取消弃用" value="unlock_and_undeprecate" />
                <v-radio label="如果没有上锁，则弃用" value="deprecate_if_not_locked" />
                <v-radio label="如果没有弃用，则上锁" value="lock_if_not_deprecated" />
                <v-radio label="如果缺少词条，则弃用" value="deprecate_if_missing_stats" />
              </v-radio-group>
            </v-col>
            <v-col cols="12" md="6">
              <v-switch
                v-model="redundantCleanupEnabled"
                color="primary"
                density="comfortable"
                hide-details
                label="冗余清理（实验性）"
              />
              <v-alert border="start" class="mt-2 mb-4" type="info" variant="tonal">
                启用后，将在扫描结束后回到顶部，逐页清理本次扫描中的冗余基质。
              </v-alert>
              <v-radio-group
                v-model="redundantCleanupTrigger"
                color="primary"
                density="comfortable"
                :disabled="!redundantCleanupEnabled"
                label="清理时机"
              >
                <v-radio label="仅在扫描到尾页时启用" value="scan_complete" />
                <v-radio label="所有情况下均启用（含手动停止扫描）" value="always" />
              </v-radio-group>
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Panel 4: 通用与更新设置 -->
      <v-expansion-panel :value="4">
        <v-expansion-panel-title>通用与更新设置</v-expansion-panel-title>
        <v-expansion-panel-text>
          <h2>界面设置</h2>
          <v-row class="my-4">
            <v-col cols="12" md="6">
              <v-switch
                v-model="statusPollingEnabled"
                color="primary"
                density="comfortable"
                hide-details
                label="启用轮询状态更新"
                @update:model-value="onStatusPollingToggle"
              />
            </v-col>
          </v-row>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            启用后，前端会轮询更新扫描状态和基质数量。禁用可减少网络请求以避免日志膨胀。
            <!-- [TODO] uvicorn 日志改等级? 之后默认启用 -->
          </v-alert>

          <v-divider class="my-4" />

          <h2>更新设置</h2>
          <v-row class="my-4">
            <v-col cols="12" md="6">
              <v-select
                v-model="updateFlow"
                density="comfortable"
                hide-details
                :items="flowOptions"
                label="更新流程"
                variant="outlined"
              >
                <template #append-inner>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-icon v-bind="props" size="small">mdi-information-outline</v-icon>
                    </template>
                    <span>{{ selectedFlowName }}</span>
                  </v-tooltip>
                </template>
              </v-select>
            </v-col>
            <v-col v-if="updateFlow === 'github'" cols="12" md="6">
              <v-select
                v-model="updateGithubMirror"
                density="comfortable"
                hide-details
                :items="mirrorOptions"
                label="GitHub 下载镜像"
                variant="outlined"
              >
                <template #append-inner>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-icon v-bind="props" size="small">mdi-information-outline</v-icon>
                    </template>
                    <span>{{ selectedMirrorName }}</span>
                  </v-tooltip>
                </template>
              </v-select>
            </v-col>
            <v-col cols="12" md="6">
              <div class="d-flex align-center">
                <v-text-field
                  v-model="updateProxyPort"
                  class="flex-grow-1"
                  density="comfortable"
                  :disabled="!updateProxyEnabled"
                  hide-details
                  label="代理端口"
                  :max="65535"
                  :min="1"
                  placeholder="7890"
                  type="number"
                  variant="outlined"
                />
                <v-switch
                  v-model="updateProxyEnabled"
                  class="ms-4 flex-shrink-0"
                  color="primary"
                  density="comfortable"
                  hide-details
                  label="使用代理"
                />
              </div>
            </v-col>
            <v-col v-if="updateFlow === 'cn_mirrorchyan'" cols="12" md="4">
              <v-text-field
                v-model="updateMirrorChyanResId"
                density="comfortable"
                hide-details
                label="Mirror 酱资源 ID"
                placeholder="联系 Mirror 酱获取"
                variant="outlined"
              />
            </v-col>
            <v-col v-if="updateFlow === 'cn_mirrorchyan'" cols="12" md="4">
              <v-text-field
                v-model="updateMirrorChyanCdk"
                density="comfortable"
                hide-details
                label="Mirror 酱 CDK"
                placeholder="不填写则仅检查版本"
                type="password"
                variant="outlined"
              />
            </v-col>
            <v-col v-if="updateFlow === 'cn_mirrorchyan'" cols="12" md="4">
              <v-text-field
                v-model="updateMirrorChyanUserAgent"
                density="comfortable"
                hide-details
                label="Mirror 酱来源标识"
                placeholder="EER_APP"
                variant="outlined"
              />
            </v-col>
          </v-row>
          <v-alert border="start" class="mb-4" type="info" variant="tonal">
            在网络通畅时，请尽量使用"GitHub Release"中"GitHub 官方"选项，以降低一图流的cdn流量压力。
          </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
    <v-card class="mt-4" variant="outlined">
      <v-card-text class="text-center text-caption text-medium-emphasis">
        配置版本: v{{ configVersion }}
      </v-card-text>
    </v-card>

    <!-- 一键补齐全部属性组合的确认弹窗 -->
    <v-dialog v-model="fillAllDialog" max-width="520">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-auto-fix</v-icon>
          一键补齐全部属性组合
        </v-card-title>
        <v-card-text>
          <p class="mb-2">
            基础 {{ allAttributeStats.length }} × 附加 {{ allSecondaryStats.length }} × 技能
            {{ allSkillStats.length }} 共 {{ totalCombinationCount }} 种组合，其中
            {{ totalCombinationCount - pendingFullMatrix.length }}
            种已被内置武器或现有条目覆盖。
          </p>
          <p class="mb-4">
            本次将新增 <strong>{{ pendingFullMatrix.length }}</strong> 条自定义基质，名称由「基础 2
            字 + 附加 2 字 + 技能 1 字」拼成 5 个字，例如 {{ pendingFullMatrix[0]?.name }}。
          </p>
          <v-alert border="start" density="compact" type="warning" variant="tonal">
            条目数量较多会明显拖慢设置页与宝藏基质页的渲染，请确认后再继续。
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="fillAllDialog = false">取消</v-btn>
          <v-btn color="primary" variant="flat" @click="confirmFillAllCombinations">确认添加</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 清空全部自定义基质的确认弹窗 -->
    <v-dialog v-model="clearAllDialog" max-width="520">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-delete-sweep</v-icon>
          清空全部自定义基质
        </v-card-title>
        <v-card-text>
          <p class="mb-4">
            将删除全部 <strong>{{ treasureEssenceStats.length }}</strong> 条自定义基质配置。
          </p>
          <v-alert border="start" density="compact" type="warning" variant="tonal">
            此操作不可撤销。与逐条删除一样，宝藏基质页中对应的已记录条目会一并移除。
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="clearAllDialog = false">取消</v-btn>
          <v-btn color="error" variant="flat" @click="confirmClearAllCustomStats">确认清空</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import ItemIcon from '@/components/ItemIcon.vue'
import { setScanningStatusPolling, useScanningStatus } from '@/composables/useScanningStatus'
import { useToast } from '@/composables/useToast'
import { useUpdateMirrors } from '@/composables/useUpdateMirrors'
import { useStaticData } from '@/utils/gameData/staticData'
import {
  buildFullCustomStatMatrix,
  buildStatKey,
  createCustomStatId,
  type CustomStat,
  getGemTagName,
  getStatsForWeapon,
} from '@/utils/gameData/weapon'

const theme = useTheme()
const { weaponTypes, weaponsMap, rarityColors, essencesMap } = useStaticData()
const { isScanning, pollingEnabled } = useScanningStatus()
const { mirrorOptions, flowOptions } = useUpdateMirrors()
const statusPollingEnabled = ref(pollingEnabled)
const configVersion = ref(0)

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

// 自定义基质类型统一使用 CustomStat（含稳定 id），不再在本页另立一份定义

/** 新建一个自定义基质，创建时即分配稳定 ID */
function newCustomStat(): CustomStat {
  return {
    id: createCustomStatId(),
    name: '',
    attribute: null,
    secondary: null,
    skill: null,
  }
}

type TreasureMatchMode = 'only' | 'all' | 'any' | 'sum'

const selectedWeaponIds = ref<string[]>([])
const treasureEssenceStats = ref<CustomStat[]>([])
const treasureAction = ref('lock')
const trashAction = ref('unlock')
const nonFiveStarBehavior = ref('process')
const autoPageFlip = ref(true)
const fixGridRowOffsetAfterPageFlip = ref(true)
const fixPageFlipOverscroll = ref(false)
const skipLockedEssence = ref(false)
const skipDeprecatedEssence = ref(false)
const highLevelTreasureEnabled = ref(false)
const highLevelTreasureAttributeThreshold = ref(3)
const highLevelTreasureSecondaryThreshold = ref(3)
const highLevelTreasureSkillThreshold = ref(3)
const highLevelTreasureMatchMode = ref<TreasureMatchMode>('any')
const highLevelTreasureSumThreshold = ref(6)
const highLevelTreasureOnlyCheckAttribute = ref(true)
const highLevelTreasureOnlyCheckSecondary = ref(true)
const highLevelTreasureOnlyCheckSkill = ref(true)
const nonFiveStarSeparateHighLevelSettings = ref(false)
const nonFiveStarHighLevelAttributeThreshold = ref(3)
const nonFiveStarHighLevelSecondaryThreshold = ref(3)
const nonFiveStarHighLevelSkillThreshold = ref(3)
const nonFiveStarHighLevelMatchMode = ref<TreasureMatchMode>('any')
const nonFiveStarHighLevelSumThreshold = ref(6)
const nonFiveStarHighLevelOnlyCheckAttribute = ref(true)
const nonFiveStarHighLevelOnlyCheckSecondary = ref(true)
const nonFiveStarHighLevelOnlyCheckSkill = ref(true)
const sameTypeTreasureLimitEnabled = ref(false)
const sameTypeTreasureLimit = ref(1)
const sameTypeGroupMode = ref<'by_stat' | 'by_weapon'>('by_stat')
const sameTypeKeepBest = ref(true)
const sameTypeKeepBestMode = ref<'sequential' | 'sum' | 'weighted_sum'>('sequential')
const sameTypeNonDowngradeFilter = ref(true)
const redundantCleanupEnabled = ref(false)
const redundantCleanupTrigger = ref<'scan_complete' | 'always'>('scan_complete')
const redundantAction = ref('deprecate')
const updateFlow = ref('github')
const updateGithubMirror = ref('github')
const updateProxyEnabled = ref(false)
const updateProxyPort = ref('7890')
const updateMirrorChyanResId = ref('')
const updateMirrorChyanCdk = ref('')
const updateMirrorChyanUserAgent = ref('EER_APP')
const weaponEssenceCounts = ref<Record<string, number>>({})

/** 自定义基质列表每页条目数：一次性渲染上百行下拉框会让设置页长时间无响应 */
const CUSTOM_STAT_PAGE_SIZE = 10
const customStatPage = ref(1)

/** 一键补齐的候选条目，用户在弹窗中确认后才写入列表 */
const pendingFullMatrix = ref<CustomStat[]>([])
const fillAllDialog = ref(false)
const clearAllDialog = ref(false)

const customStatPageCount = computed(() =>
  Math.max(1, Math.ceil(treasureEssenceStats.value.length / CUSTOM_STAT_PAGE_SIZE)),
)

/**
 * 当前页的自定义基质，附带其在完整列表中的下标。
 *
 * 增删改与上下移动都直接作用于 `treasureEssenceStats`，所以这里必须把全局下标
 * 一并带出去，否则翻到第二页后所有操作都会打到列表开头的条目上。
 */
const pagedCustomStats = computed(() => {
  const start = (customStatPage.value - 1) * CUSTOM_STAT_PAGE_SIZE
  return treasureEssenceStats.value
    .slice(start, start + CUSTOM_STAT_PAGE_SIZE)
    .map((stat, offset) => ({ stat, index: start + offset }))
})

/** 基础 × 附加 × 技能 的理论组合总数 */
const totalCombinationCount = computed(
  () =>
    allAttributeStats.value.length * allSecondaryStats.value.length * allSkillStats.value.length,
)

// 删除条目使总页数变少时，把当前页拉回有效范围，避免停在一页空白上
watch(customStatPageCount, (count) => {
  if (customStatPage.value > count) {
    customStatPage.value = count
  }
})

/**
 * 计算「一键补齐」会新增哪些条目并弹窗确认。
 *
 * 内置武器已覆盖的组合和列表中已有的组合都算作已占用，因此重复点击不会产生重复条目。
 */
function prepareFillAllCombinations() {
  const occupiedKeys = new Set<string>()
  for (const weapon of weaponsMap.value.values()) {
    occupiedKeys.add(
      buildStatKey(weapon.attributeStatId, weapon.secondaryStatId, weapon.skillStatId),
    )
  }
  for (const stat of treasureEssenceStats.value) {
    occupiedKeys.add(buildStatKey(stat.attribute, stat.secondary, stat.skill))
  }

  const generated = buildFullCustomStatMatrix(
    allAttributeStats.value,
    allSecondaryStats.value,
    allSkillStats.value,
    occupiedKeys,
  )
  if (generated.length === 0) {
    useToast().info('全部属性组合都已被内置武器或现有条目覆盖，无需补齐')
    return
  }

  pendingFullMatrix.value = generated
  fillAllDialog.value = true
}

/** 确认后把候选条目追加到列表末尾 */
function confirmFillAllCombinations() {
  fillAllDialog.value = false
  treasureEssenceStats.value = [...treasureEssenceStats.value, ...pendingFullMatrix.value]
  useToast().success(`已添加 ${pendingFullMatrix.value.length} 条自定义基质`)
}

/** 在列表末尾追加一条空白自定义基质，并翻到它所在的页 */
function appendCustomStat() {
  treasureEssenceStats.value.push(newCustomStat())
  customStatPage.value = customStatPageCount.value
}

/** 确认后清空全部自定义基质，并回到第一页 */
function confirmClearAllCustomStats() {
  const clearedCount = treasureEssenceStats.value.length
  clearAllDialog.value = false
  treasureEssenceStats.value = []
  customStatPage.value = 1
  useToast().success(`已清空 ${clearedCount} 条自定义基质`)
}

const notSelectedWeaponIds = computed(() => {
  return Array.from(weaponsMap.value.keys()).filter(
    (weaponId) => !selectedWeaponIds.value.includes(weaponId),
  )
})

// 武器组内按稀有度降序排序（6★ -> 3★）
const sortedWeaponTypes = computed(() =>
  weaponTypes.value.map((weaponType) => ({
    ...weaponType,
    weaponIds: weaponType.weaponIds.toSorted((a, b) => {
      const wa = weaponsMap.value.get(a)
      const wb = weaponsMap.value.get(b)
      if (wa && wb) return wb.rarity - wa.rarity
      return 0
    }),
  })),
)

const selectedMirrorName = computed(() => {
  const mirror = mirrorOptions.value.find((m) => m.value === updateGithubMirror.value)
  return mirror ? mirror.title : 'GitHub 官方'
})

const selectedFlowName = computed(() => {
  const flow = flowOptions.value.find((m) => m.value === updateFlow.value)
  return flow ? flow.title : 'GitHub Release'
})

function getWeaponStatsDescription(weaponId: string): string {
  const stats = getStatsForWeapon(weaponId)
  if (!stats.attribute && !stats.secondary && !stats.skill) {
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
  const weaponIds = Array.from(weaponsMap.value.values())
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.id)
  if (select) {
    selectedWeaponIds.value = [...new Set([...selectedWeaponIds.value, ...weaponIds])]
  } else {
    selectedWeaponIds.value = selectedWeaponIds.value.filter((id) => !weaponIds.includes(id))
  }
}

function isRarityAllSelected(rarity: number): boolean {
  const weaponIds = Array.from(weaponsMap.value.values())
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.id)
  if (weaponIds.length === 0) return false
  return weaponIds.every((id) => selectedWeaponIds.value.includes(id))
}

function isRarityPartiallySelected(rarity: number): boolean {
  const weaponIds = Array.from(weaponsMap.value.values())
    .filter((weapon) => weapon.rarity === rarity)
    .map((weapon) => weapon.id)
  if (weaponIds.length === 0) return false
  const selectedCount = weaponIds.filter((id) => selectedWeaponIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < weaponIds.length
}

function typeSelectAll(groupId: string, select: boolean) {
  const weaponType = weaponTypes.value.find((t) => t.id === groupId)
  const weaponIds = weaponType?.weaponIds ?? []
  if (select) {
    selectedWeaponIds.value = [...new Set([...selectedWeaponIds.value, ...weaponIds])]
  } else {
    selectedWeaponIds.value = selectedWeaponIds.value.filter((id) => !weaponIds.includes(id))
  }
}

function isTypeAllSelected(groupId: string): boolean {
  const weaponType = weaponTypes.value.find((t) => t.id === groupId)
  const weaponIds = weaponType?.weaponIds ?? []
  if (weaponIds.length === 0) return false
  return weaponIds.every((id) => selectedWeaponIds.value.includes(id))
}

function isTypePartiallySelected(groupId: string): boolean {
  const weaponType = weaponTypes.value.find((t) => t.id === groupId)
  const weaponIds = weaponType?.weaponIds ?? []
  if (weaponIds.length === 0) return false
  const selectedCount = weaponIds.filter((id) => selectedWeaponIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < weaponIds.length
}

const config = computed(() => {
  const proxyUrl = updateProxyEnabled.value ? `http://127.0.0.1:${updateProxyPort.value}` : ''
  return {
    version: 10,
    trash_weapon_ids: notSelectedWeaponIds.value,
    treasure_essence_stats: treasureEssenceStats.value,
    treasure_essence_match_mode: 'all' as const,
    treasure_action: treasureAction.value,
    trash_action: trashAction.value,
    non_five_star_behavior: nonFiveStarBehavior.value,
    auto_page_flip: autoPageFlip.value,
    fix_grid_row_offset_after_page_flip: fixGridRowOffsetAfterPageFlip.value,
    fix_page_flip_overscroll: fixPageFlipOverscroll.value,
    skip_locked_essence: skipLockedEssence.value,
    skip_deprecated_essence: skipDeprecatedEssence.value,
    high_level_treasure_enabled: highLevelTreasureEnabled.value,
    high_level_treasure_attribute_threshold: highLevelTreasureAttributeThreshold.value,
    high_level_treasure_secondary_threshold: highLevelTreasureSecondaryThreshold.value,
    high_level_treasure_skill_threshold: highLevelTreasureSkillThreshold.value,
    high_level_treasure_match_mode: highLevelTreasureMatchMode.value,
    high_level_treasure_sum_threshold: Math.min(
      15,
      Math.max(3, Number(highLevelTreasureSumThreshold.value) || 6),
    ),
    high_level_treasure_only_check_attribute: highLevelTreasureOnlyCheckAttribute.value,
    high_level_treasure_only_check_secondary: highLevelTreasureOnlyCheckSecondary.value,
    high_level_treasure_only_check_skill: highLevelTreasureOnlyCheckSkill.value,
    non_five_star_separate_high_level_settings: nonFiveStarSeparateHighLevelSettings.value,
    non_five_star_high_level_attribute_threshold: nonFiveStarHighLevelAttributeThreshold.value,
    non_five_star_high_level_secondary_threshold: nonFiveStarHighLevelSecondaryThreshold.value,
    non_five_star_high_level_skill_threshold: nonFiveStarHighLevelSkillThreshold.value,
    non_five_star_high_level_match_mode: nonFiveStarHighLevelMatchMode.value,
    non_five_star_high_level_sum_threshold: Math.min(
      15,
      Math.max(3, Number(nonFiveStarHighLevelSumThreshold.value) || 6),
    ),
    non_five_star_high_level_only_check_attribute: nonFiveStarHighLevelOnlyCheckAttribute.value,
    non_five_star_high_level_only_check_secondary: nonFiveStarHighLevelOnlyCheckSecondary.value,
    non_five_star_high_level_only_check_skill: nonFiveStarHighLevelOnlyCheckSkill.value,
    same_type_treasure_limit_enabled: sameTypeTreasureLimitEnabled.value,
    same_type_treasure_limit: Math.max(1, Number(sameTypeTreasureLimit.value) || 1),
    same_type_group_mode: sameTypeGroupMode.value,
    same_type_keep_best: sameTypeKeepBest.value,
    same_type_keep_best_mode: sameTypeKeepBestMode.value,
    same_type_non_downgrade_filter: sameTypeNonDowngradeFilter.value,
    redundant_cleanup_enabled: redundantCleanupEnabled.value,
    redundant_cleanup_trigger: redundantCleanupTrigger.value,
    redundant_action: redundantAction.value,
    update_mirror: updateGithubMirror.value,
    update_flow: updateFlow.value,
    update_github_mirror: updateGithubMirror.value,
    update_proxy: proxyUrl,
    update_mirrorchyan_res_id: updateMirrorChyanResId.value,
    update_mirrorchyan_cdk: updateMirrorChyanCdk.value,
    update_mirrorchyan_user_agent: updateMirrorChyanUserAgent.value || 'EER_APP',
  }
})

async function getConfig() {
  const response = await fetch(`/api/config`)
  const result = await response.json()
  const {
    version,
    trash_weapon_ids,
    treasure_essence_stats,
    treasure_action,
    trash_action,
    non_five_star_behavior,
    auto_page_flip,
    fix_grid_row_offset_after_page_flip,
    fix_page_flip_overscroll,
    skip_locked_essence,
    skip_deprecated_essence,
    high_level_treasure_enabled,
    high_level_treasure_attribute_threshold,
    high_level_treasure_secondary_threshold,
    high_level_treasure_skill_threshold,
    high_level_treasure_match_mode,
    high_level_treasure_sum_threshold,
    high_level_treasure_only_check_attribute,
    high_level_treasure_only_check_secondary,
    high_level_treasure_only_check_skill,
    non_five_star_separate_high_level_settings,
    non_five_star_high_level_attribute_threshold,
    non_five_star_high_level_secondary_threshold,
    non_five_star_high_level_skill_threshold,
    non_five_star_high_level_match_mode,
    non_five_star_high_level_sum_threshold,
    non_five_star_high_level_only_check_attribute,
    non_five_star_high_level_only_check_secondary,
    non_five_star_high_level_only_check_skill,
    same_type_treasure_limit_enabled,
    same_type_treasure_limit,
    same_type_group_mode,
    same_type_keep_best,
    same_type_keep_best_mode,
    same_type_non_downgrade_filter,
    redundant_cleanup_enabled,
    redundant_cleanup_trigger,
    redundant_action,
    update_flow,
    update_github_mirror,
    update_mirror,
    update_proxy,
    update_mirrorchyan_res_id,
    update_mirrorchyan_cdk,
    update_mirrorchyan_user_agent,
  } = result
  configVersion.value = version
  treasureEssenceStats.value = treasure_essence_stats
  treasureAction.value = treasure_action
  trashAction.value = trash_action
  nonFiveStarBehavior.value = non_five_star_behavior || 'process'
  autoPageFlip.value = auto_page_flip !== undefined ? auto_page_flip : true
  fixGridRowOffsetAfterPageFlip.value = fix_grid_row_offset_after_page_flip !== false
  fixPageFlipOverscroll.value = fix_page_flip_overscroll === true
  skipLockedEssence.value = skip_locked_essence === true
  skipDeprecatedEssence.value = skip_deprecated_essence === true
  highLevelTreasureEnabled.value = high_level_treasure_enabled
  highLevelTreasureAttributeThreshold.value = high_level_treasure_attribute_threshold
  highLevelTreasureSecondaryThreshold.value = high_level_treasure_secondary_threshold
  highLevelTreasureSkillThreshold.value = high_level_treasure_skill_threshold
  highLevelTreasureMatchMode.value = high_level_treasure_match_mode || 'any'
  highLevelTreasureSumThreshold.value = high_level_treasure_sum_threshold || 6
  highLevelTreasureOnlyCheckAttribute.value = high_level_treasure_only_check_attribute !== false
  highLevelTreasureOnlyCheckSecondary.value = high_level_treasure_only_check_secondary !== false
  highLevelTreasureOnlyCheckSkill.value = high_level_treasure_only_check_skill !== false
  nonFiveStarSeparateHighLevelSettings.value = non_five_star_separate_high_level_settings || false
  nonFiveStarHighLevelAttributeThreshold.value = non_five_star_high_level_attribute_threshold || 3
  nonFiveStarHighLevelSecondaryThreshold.value = non_five_star_high_level_secondary_threshold || 3
  nonFiveStarHighLevelSkillThreshold.value = non_five_star_high_level_skill_threshold || 3
  nonFiveStarHighLevelMatchMode.value = non_five_star_high_level_match_mode || 'any'
  nonFiveStarHighLevelSumThreshold.value = non_five_star_high_level_sum_threshold || 6
  nonFiveStarHighLevelOnlyCheckAttribute.value =
    non_five_star_high_level_only_check_attribute !== false
  nonFiveStarHighLevelOnlyCheckSecondary.value =
    non_five_star_high_level_only_check_secondary !== false
  nonFiveStarHighLevelOnlyCheckSkill.value = non_five_star_high_level_only_check_skill !== false
  sameTypeTreasureLimitEnabled.value = same_type_treasure_limit_enabled || false
  sameTypeTreasureLimit.value = same_type_treasure_limit || 1
  sameTypeGroupMode.value = same_type_group_mode || 'by_stat'
  sameTypeKeepBest.value = same_type_keep_best !== false
  sameTypeKeepBestMode.value = same_type_keep_best_mode || 'sequential'
  sameTypeNonDowngradeFilter.value = same_type_non_downgrade_filter !== false
  redundantCleanupEnabled.value = redundant_cleanup_enabled === true
  redundantCleanupTrigger.value = redundant_cleanup_trigger || 'scan_complete'
  redundantAction.value = redundant_action || 'deprecate'
  updateFlow.value = normalizeUpdateFlow(update_flow, update_mirror)
  updateGithubMirror.value = update_github_mirror || getLegacyGithubMirror(update_mirror)
  updateMirrorChyanResId.value = update_mirrorchyan_res_id || ''
  updateMirrorChyanCdk.value = update_mirrorchyan_cdk || ''
  updateMirrorChyanUserAgent.value = update_mirrorchyan_user_agent || 'EER_APP'

  // 解析代理配置
  if (update_proxy) {
    updateProxyEnabled.value = true
    const match = update_proxy.match(/:(\d+)$/)
    updateProxyPort.value = match ? match[1] : '7890'
  } else {
    updateProxyEnabled.value = false
    updateProxyPort.value = '7890'
  }

  selectedWeaponIds.value = Array.from(weaponsMap.value.keys()).filter(
    (weaponId) => !trash_weapon_ids.includes(weaponId),
  )
}

/** 从旧 update_mirror 字段中提取 GitHub 下载镜像。 */
function getLegacyGithubMirror(value: string | undefined): string {
  if (!value || value === 'cn' || value === 'cn_yituliu' || value === 'mirrorchyan') return 'github'
  return value
}

/** 将旧配置字段转换为新的更新流程字段。 */
function normalizeUpdateFlow(value: string | undefined, legacyMirror: string | undefined): string {
  if (value === 'cn') return 'cn_yituliu'
  if (value === 'cn_yituliu' || value === 'cn_mirrorchyan' || value === 'github') return value
  if (legacyMirror === 'cn') return 'cn_yituliu'
  return 'github'
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

async function fetchWeaponEssenceCounts() {
  try {
    const response = await fetch(`/api/weapon_essence_counts`)
    const result = await response.json()
    weaponEssenceCounts.value = result.counts
  } catch (error) {
    console.error('Failed to fetch weapon essence counts:', error)
  }
}

function onStatusPollingToggle(enabled: boolean | null) {
  if (enabled === null) return
  setScanningStatusPolling(enabled)
  if (enabled) {
    startPolling()
  }
}

async function startPolling() {
  // 获取一次
  await fetchWeaponEssenceCounts()

  if (!statusPollingEnabled.value) {
    // 未启用轮询
    return
  }

  const poll = async () => {
    if (!statusPollingEnabled.value) {
      // 轮询被禁用，停止
      return
    }

    if (isScanning.value) {
      // 扫描中 快速轮询并更新
      await fetchWeaponEssenceCounts()
      setTimeout(poll, 1000)
    } else {
      // 待机 只检查状态不更新数据
      setTimeout(poll, 5000)
    }
  }

  poll()
}

onMounted(async () => {
  await getConfig()
  await startPolling()

  watch(config, postConfig, { deep: true })
})
</script>

<style scoped lang="scss">
$weapon-icon-size: 3.5rem;

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
  cursor: pointer;
  transition: transform 0.15s;

  &:hover {
    transform: scale(1.05);
  }
}

.weapon-disabled {
  opacity: 0.4;
  filter: grayscale(0.8);
  transition:
    opacity 0.15s,
    filter 0.15s;
}
</style>
