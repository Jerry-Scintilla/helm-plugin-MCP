<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useHelmSDK } from './composables/useHelmSDK'
import TabBar, { type TabName } from './components/layout/TabBar.vue'
import ToastNotice from './components/layout/ToastNotice.vue'
import PanelKeys from './components/keys/PanelKeys.vue'
import PanelTools from './components/tools/PanelTools.vue'
import PanelLogs from './components/logs/PanelLogs.vue'

const { init } = useHelmSDK()
const activeTab = ref<TabName>('keys')

onMounted(() => {
  init()
})
</script>

<template>
  <h1>🤖 MCP 接入管理</h1>

  <TabBar v-model="activeTab" />

  <!-- v-show keeps all panels mounted to avoid reloading data on tab switch -->
  <PanelKeys  v-show="activeTab === 'keys'" />
  <PanelTools v-show="activeTab === 'tools'" />
  <PanelLogs  v-show="activeTab === 'logs'" />

  <ToastNotice />
</template>
