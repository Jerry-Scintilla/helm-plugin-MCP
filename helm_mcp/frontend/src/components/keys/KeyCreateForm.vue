<script setup lang="ts">
import { ref } from 'vue'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'

const emit = defineEmits<{ (e: 'key-created', apiKey: string): void }>()

const { apiFetch } = useApiFetch()
const { showToast } = useToast()

const keyName = ref('')
const createdKey = ref('')
const copyLabel = ref('复制')

async function createKey() {
  const name = keyName.value.trim()
  if (!name) {
    showToast('请输入密钥备注名')
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
      copyLabel.value = '复制'
      emit('key-created', data.api_key)
    } else {
      showToast('创建失败：' + (data.detail ?? JSON.stringify(data)), 'error')
    }
  } catch (err) {
    showToast('请求失败：' + (err instanceof Error ? err.message : String(err)), 'error')
  }
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(createdKey.value)
    copyLabel.value = '已复制 ✓'
    showToast('已复制到剪贴板', 'success')
  } catch {
    showToast('复制失败，请手动选择文字复制', 'error')
  }
}
</script>

<template>
  <div class="card">
    <h3>创建新 MCP 密钥</h3>
    <div class="row">
      <input
        v-model="keyName"
        type="text"
        placeholder="密钥备注名，如 claude-desktop"
        maxlength="128"
        @keyup.enter="createKey"
      />
      <button class="btn" @click="createKey">创建密钥</button>
    </div>

    <template v-if="createdKey">
      <p class="text-warn mt">⚠️ 完整密钥只显示一次，请立即复制并妥善保存：</p>
      <div class="key-reveal">{{ createdKey }}</div>
      <button class="btn secondary sm mt" @click="copyKey">{{ copyLabel }}</button>
    </template>
  </div>
</template>
