<script setup lang="ts">
import { ref, computed, onBeforeUnmount, nextTick } from 'vue'

export interface HelmSelectOption {
  value: string
  label: string
}

const props = withDefaults(defineProps<{
  modelValue: string
  options: HelmSelectOption[]
  placeholder?: string
  ariaLabel?: string
  minWidth?: string
}>(), {
  placeholder: '',
  ariaLabel: '',
  minWidth: '',
})

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const menuEl = ref<HTMLElement | null>(null)
const highlightIdx = ref(-1)

const selectedLabel = computed(() => {
  const found = props.options.find(o => o.value === props.modelValue)
  return found?.label ?? props.placeholder
})

async function toggle() {
  open.value = !open.value
  if (open.value) {
    highlightIdx.value = props.options.findIndex(o => o.value === props.modelValue)
    await nextTick()
    menuEl.value
      ?.querySelector<HTMLElement>('.helm-option.selected')
      ?.scrollIntoView({ block: 'nearest' })
  }
}

function pick(v: string) {
  emit('update:modelValue', v)
  open.value = false
}

function onDocClick(e: MouseEvent) {
  if (!rootEl.value) return
  if (!rootEl.value.contains(e.target as Node)) open.value = false
}

function onKey(e: KeyboardEvent) {
  if (!open.value) return
  const n = props.options.length
  if (e.key === 'Escape') {
    open.value = false
    e.preventDefault()
  } else if (e.key === 'ArrowDown' && n > 0) {
    highlightIdx.value = (highlightIdx.value + 1 + n) % n
    e.preventDefault()
  } else if (e.key === 'ArrowUp' && n > 0) {
    highlightIdx.value = (highlightIdx.value - 1 + n) % n
    e.preventDefault()
  } else if (e.key === 'Enter') {
    if (highlightIdx.value >= 0 && highlightIdx.value < n) {
      pick(props.options[highlightIdx.value].value)
    }
    e.preventDefault()
  }
}

document.addEventListener('mousedown', onDocClick)
document.addEventListener('keydown', onKey)
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="helm-select" ref="rootEl" :class="{ open }" :style="minWidth ? { minWidth } : undefined">
    <button
      type="button"
      class="helm-select-trigger"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      @click.stop="toggle"
    >
      <span class="helm-select-value" :class="{ placeholder: !options.some(o => o.value === modelValue) }">
        {{ selectedLabel }}
      </span>
      <span class="helm-select-caret" aria-hidden="true">▾</span>
    </button>
    <ul
      v-if="open"
      class="helm-select-menu"
      ref="menuEl"
      role="listbox"
    >
      <li
        v-for="(o, i) in options"
        :key="o.value"
        class="helm-option"
        :class="{ active: i === highlightIdx, selected: o.value === modelValue }"
        role="option"
        :aria-selected="o.value === modelValue"
        @click="pick(o.value)"
        @mouseenter="highlightIdx = i"
      >
        {{ o.label }}
      </li>
      <li v-if="options.length === 0" class="helm-option empty">—</li>
    </ul>
  </div>
</template>
