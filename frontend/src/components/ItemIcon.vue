<template>
  <div
    class="w-100 h-100 position-relative overflow-hidden rounded border-md border-b-0 elevation-2 bg-surface repeating-gradient"
  >
    <img :alt="itemName" :src="getItemIconUrl(props.itemId)" class="item-icon-img w-100 h-100" />
    <div class="item-gradient-overlay" />
    <div class="item-tier-bar" />
    <div ref="itemNameContainerRef" class="item-name-container">
      <span v-if="props.showItemName" ref="itemNameRef" class="item-name">
        {{ itemName }}
      </span>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { useLanguage } from '@/composables/useLanguage'
import { updateText } from '@/utils/autoFontSizing'
import { isLoaded } from '@/utils/gameData/gameData'
import { getItemIconUrl, getItemName, getItemTierColor } from '@/utils/gameData/item'
import { computed, useTemplateRef, watch } from 'vue'

const { currentLanguage } = useLanguage()

interface Props {
  itemId: string
  itemName?: string
  showItemName?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showItemName: false,
})

const itemNameContainerRef = useTemplateRef<HTMLDivElement>('itemNameContainerRef')
const itemNameRef = useTemplateRef<HTMLDivElement>('itemNameRef')

const itemName = computed(() => {
  if (props.itemName !== undefined) {
    return props.itemName
  } else {
    return getItemName(props.itemId)
  }
})

watch([props, itemNameRef, isLoaded, currentLanguage], () => {
  if (itemNameRef.value) {
    updateText(itemNameRef.value, (itemNameContainerRef.value?.clientWidth || 96) * 0.95, 10, 16)
  }
})
</script>

<style lang="scss" scoped>
.item-icon-img {
  object-fit: cover;
}

.item-gradient-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(
    to bottom,
    transparent 0%,
    transparent 70%,
    v-bind('getItemTierColor(props.itemId).alpha(0.3).string()') 100%
  );
}

.item-tier-bar {
  position: absolute;
  bottom: 0;
  width: 100%;
  height: 4%;
  background-color: v-bind('getItemTierColor(props.itemId).string()');
}

.item-name-container {
  position: absolute;
  bottom: 4%;
  width: 100%;
  pointer-events: none;
  text-align: center;
  line-height: 1;
}

.item-name {
  display: inline-block;
  font-weight: 500;
  font-size: 1rem;
  text-shadow: 0 0 4px rgb(var(--v-theme-surface));
  -webkit-text-stroke: 2px rgb(var(--v-theme-surface));
  paint-order: stroke fill;
}
</style>
