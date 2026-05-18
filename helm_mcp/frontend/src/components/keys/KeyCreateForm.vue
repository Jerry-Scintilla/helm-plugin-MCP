<script setup lang="ts">
import { ref } from 'vue'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'
import { useI18n } from '../../composables/useI18n'

const emit = defineEmits<{ (e: 'key-created', apiKey: string): void }>()

const { apiFetch } = useApiFetch()
const { showToast } = useToast()
const { t } = useI18n()

const keyName = ref('')
const createdKey = ref('')
const copyLabel = ref(t('keys.create.copy'))

async function createKey() {
  const name = keyName.value.trim()
  if (!name) {
    showToast(t('keys.toast.empty'))
    return
  }

  try {
    const data = await apiFetch<{ api_key?: string; detail?: string }>('/keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })

    if (data.api_key) {
      createdKey.value = data.api_key
      keyName.value = ''
      copyLabel.value = t('keys.create.copy')
      emit('key-created', data.api_key)
    } else {
      showToast(t('keys.toast.createFailed', { msg: data.detail ?? JSON.stringify(data) }), 'error')
    }
  } catch (err) {
    showToast(t('keys.toast.requestFailed', { msg: err instanceof Error ? err.message : String(err) }), 'error')
  }
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(createdKey.value)
    copyLabel.value = t('keys.create.copied')
    showToast(t('keys.toast.copied'), 'success')
  } catch {
    showToast(t('keys.toast.copyFailed'), 'error')
  }
}
</script>

<template>
  <div class="card">
    <h3>{{ t('keys.create.title') }}</h3>
    <div class="row">
      <input
        v-model="keyName"
        type="text"
        :placeholder="t('keys.create.placeholder')"
        maxlength="128"
        @keyup.enter="createKey"
      />
      <button class="btn" @click="createKey">{{ t('keys.create.btn') }}</button>
    </div>

    <template v-if="createdKey">
      <p class="text-warn mt">{{ t('keys.create.warning') }}</p>
      <div class="key-reveal">{{ createdKey }}</div>
      <button class="btn secondary sm mt" @click="copyKey">{{ copyLabel }}</button>
    </template>
  </div>
</template>
