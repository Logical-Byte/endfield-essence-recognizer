<template>
  <div class="custom-entry-icon" :class="{ 'custom-entry-icon-small': small }">
    <!-- 底板图片：静态数据未就绪时不渲染，避免 src="" 触发无效请求／破图 -->
    <img v-if="essenceBgSrc" alt="" class="essence-bg-img" :src="essenceBgSrc" />
    <!-- 技能属性图标（叠加在底板上） -->
    <img v-if="skillIconSrc" :alt="skillAltText" class="skill-icon-img" :src="skillIconSrc" />
    <div class="custom-entry-gradient" />
    <div class="custom-entry-tier-bar" />
    <div v-if="!hideName" ref="nameContainerRef" class="custom-entry-name-bar">
      <span ref="nameRef" class="custom-entry-name-text">{{ name }}</span>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed, useTemplateRef, watch } from 'vue'
import { updateText } from '@/utils/autoFontSizing'
import { useStaticData } from '@/utils/gameData/staticData'
import { getGemTagName } from '@/utils/gameData/weapon'

interface Props {
  name: string
  small?: boolean
  hideName?: boolean
  /** 技能属性ID，用于显示对应的技能图标 */
  skillStatId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  small: false,
  hideName: false,
  skillStatId: null,
})

const { matrixIcons } = useStaticData()

const nameContainerRef = useTemplateRef<HTMLDivElement>('nameContainerRef')
const nameRef = useTemplateRef<HTMLSpanElement>('nameRef')

watch([() => props.name, nameRef], () => {
  if (nameRef.value) {
    updateText(nameRef.value, (nameContainerRef.value?.clientWidth || 96) * 0.95, 6, 14)
  }
})

// 底板图片路径
const essenceBgSrc = computed(() => matrixIcons.value.essenceBg)

// 技能属性图标路径；属性缺失或未匹配时兜底显示默认基质图标
const skillIconSrc = computed(() => {
  if (!props.skillStatId) return matrixIcons.value.defaultIcon || null
  return matrixIcons.value.skills[props.skillStatId] || matrixIcons.value.defaultIcon || null
})

// 技能图标 alt 文本：用词条的中文名，英文缩写对读屏软件没有意义
const skillAltText = computed(() => {
  if (!props.skillStatId) return ''
  return getGemTagName(props.skillStatId)
})
</script>

<style lang="scss" scoped>
.custom-entry-icon {
  width: 100%;
  height: 100%;
  position: relative;
  /* 隔离内部 z-index，避免 tier-bar/名称条压过外部兄弟覆盖元素（如武器稀有度徽章） */
  isolation: isolate;
  overflow: hidden;
  border-radius: 6px;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border: 2px solid rgba(255, 113, 0, 0.5);
  border-bottom: none;
  background: linear-gradient(135deg, #ffd7b8, #ffffff);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  min-height: 56px;
}

.essence-bg-img {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
}

.skill-icon-img {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 1;
  transform: translate(5%, -5%);
}

.custom-entry-gradient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(
    to bottom,
    transparent 0%,
    transparent 70%,
    rgba(255, 113, 0, 0.3) 100%
  );
  z-index: 2;
}

.custom-entry-tier-bar {
  position: absolute;
  bottom: 0;
  width: 100%;
  height: 4%;
  background-color: #ff7100;
  z-index: 3;
}

.custom-entry-name-bar {
  position: absolute;
  bottom: 4%;
  width: 100%;
  pointer-events: none;
  text-align: center;
  line-height: 1;
  z-index: 4;
}

.custom-entry-name-text {
  display: inline-block;
  font-weight: 500;
  font-size: 0.65rem;
  text-shadow: 0 0 4px rgb(var(--v-theme-surface));
  -webkit-text-stroke: 1px rgb(var(--v-theme-surface));
  paint-order: stroke fill;
}

.custom-entry-icon-small {
  min-width: 2rem;
  min-height: 2rem;

  .custom-entry-tier-bar {
    height: 6%;
  }

  .custom-entry-name-bar {
    bottom: 6%;
  }
}
</style>
