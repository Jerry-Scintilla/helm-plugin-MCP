<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useHelmSDK } from '../../composables/useHelmSDK'
import { useApiFetch } from '../../composables/useApiFetch'
import { useI18n } from '../../composables/useI18n'
import { useToast } from '../../composables/useToast'
import HelmSelect from '../ui/HelmSelect.vue'

interface MCPServer {
  id: number
  slug: string
  name: string
  description: string | null
  max_tools: number
  is_enabled: boolean
  sort_order: number
  tool_count: number
}
interface Assignments {
  assigned: Record<string, string[]>  // slug -> tool names
  unassigned: string[]
}

const { ready } = useHelmSDK()
const { apiFetch } = useApiFetch()
const { t } = useI18n()
const { showToast } = useToast()

const servers = ref<MCPServer[]>([])
const assignments = ref<Assignments>({ assigned: {}, unassigned: [] })
const loading = ref(true)
const errorMsg = ref('')

const newSlug = ref('')
const newName = ref('')
const newDesc = ref('')
const pendingDeleteId = ref<number | null>(null)

// Options for the per-tool target dropdown: every server + an "unassigned" entry.
const moveOptions = computed(() => [
  ...servers.value.map(s => ({ value: String(s.id), label: s.slug })),
  { value: '', label: t('servers.optionUnassigned') },
])

function detailOrNull(x: unknown): string | null {
  if (x && typeof x === 'object' && 'detail' in x) {
    const d = (x as { detail: unknown }).detail
    return typeof d === 'string' ? d : JSON.stringify(d)
  }
  return null
}

async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [s, a] = await Promise.all([
      apiFetch<MCPServer[] | { detail: string }>('/servers'),
      apiFetch<Assignments | { detail: string }>('/assignments'),
    ])
    const sErr = detailOrNull(s)
    const aErr = detailOrNull(a)
    if (sErr || aErr) {
      errorMsg.value = sErr ?? aErr ?? ''
      return
    }
    servers.value = Array.isArray(s) ? (s as MCPServer[]) : []
    assignments.value = (a as Assignments) ?? { assigned: {}, unassigned: [] }
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

watch(ready, (isReady) => { if (isReady) loadAll() }, { immediate: true })

async function onCreate() {
  if (!newSlug.value.trim() || !newName.value.trim()) {
    showToast('slug / name required', 'error')
    return
  }
  try {
    const res = await apiFetch<{ detail?: string }>('/servers', {
      method: 'POST',
      body: JSON.stringify({
        slug: newSlug.value.trim(),
        name: newName.value.trim(),
        description: newDesc.value.trim() || null,
      }),
    })
    const err = detailOrNull(res)
    if (err) {
      showToast(t('servers.createFailed', { msg: err }), 'error')
      return
    }
    newSlug.value = ''
    newName.value = ''
    newDesc.value = ''
    await loadAll()
  } catch (err) {
    showToast(t('servers.createFailed', { msg: err instanceof Error ? err.message : String(err) }), 'error')
  }
}

async function onToggleEnable(s: MCPServer) {
  try {
    await apiFetch(`/servers/${s.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_enabled: !s.is_enabled }),
    })
    await loadAll()
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

async function onDelete(s: MCPServer) {
  if (pendingDeleteId.value !== s.id) {
    pendingDeleteId.value = s.id
    showToast(t('servers.confirmDelete', { slug: s.slug }), 'error')
    setTimeout(() => { if (pendingDeleteId.value === s.id) pendingDeleteId.value = null }, 5000)
    return
  }
  pendingDeleteId.value = null
  try {
    await apiFetch(`/servers/${s.id}`, { method: 'DELETE' })
    await loadAll()
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

async function onMove(toolName: string, targetIdRaw: string) {
  const targetId = targetIdRaw === '' ? null : Number(targetIdRaw)
  try {
    const res = await apiFetch<Assignments | { detail: string }>('/assignments/move', {
      method: 'POST',
      body: JSON.stringify({ tool_name: toolName, target_server_id: targetId }),
    })
    const err = detailOrNull(res)
    if (err) {
      showToast(t('servers.saveFailed', { msg: err }), 'error')
      await loadAll()
      return
    }
    assignments.value = res as Assignments
    const srv = await apiFetch<MCPServer[] | { detail: string }>('/servers')
    if (Array.isArray(srv)) servers.value = srv
    showToast(t('servers.saved'), 'success')
  } catch (err) {
    showToast(t('servers.saveFailed', { msg: err instanceof Error ? err.message : String(err) }), 'error')
    await loadAll()
  }
}

</script>

<template>
  <div>
    <p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:12px">
      {{ t('servers.hint') }}
    </p>

    <div v-if="loading" class="empty">{{ t('servers.loading') }}</div>
    <div v-else-if="errorMsg" class="error-msg">
      {{ t('servers.loadFailed', { msg: errorMsg }) }}
    </div>

    <template v-else>
      <!-- ── Create new server ──────────────────────────────────── -->
      <div class="card">
        <h3>{{ t('servers.create') }}</h3>
        <div class="server-create-row">
          <input v-model="newSlug" type="text" :placeholder="t('servers.placeholderSlug')" />
          <input v-model="newName" type="text" :placeholder="t('servers.placeholderName')" />
          <input v-model="newDesc" type="text" :placeholder="t('servers.placeholderDesc')" style="flex:2" />
          <button class="btn" @click="onCreate">{{ t('servers.create') }}</button>
        </div>
      </div>

      <!-- ── Server list ────────────────────────────────────────── -->
      <div class="card">
        <h3>{{ t('servers.listTitle') }}</h3>
        <div v-if="servers.length === 0" class="empty">{{ t('servers.empty') }}</div>
        <table v-else style="width:100%;border-collapse:collapse;margin-top:8px">
          <tbody>
            <tr v-for="s in servers" :key="s.id" style="border-top:1px solid var(--border)">
              <td style="padding:8px 6px">
                <strong>{{ s.name }}</strong>
                <code style="margin-left:6px;font-size:0.85rem;color:var(--text-muted)">{{ s.slug }}</code>
                <div v-if="s.description" style="color:var(--text-muted);font-size:0.85rem">{{ s.description }}</div>
              </td>
              <td style="padding:8px 6px;white-space:nowrap">
                {{ t('servers.capacity', { used: s.tool_count, max: s.max_tools }) }}
              </td>
              <td style="padding:8px 6px;white-space:nowrap">
                <span :style="{ color: s.is_enabled ? '#4a6a50' : '#a06060' }">
                  {{ s.is_enabled ? t('servers.enabled') : t('servers.disabled') }}
                </span>
              </td>
              <td style="padding:8px 6px;white-space:nowrap">
                <button class="btn secondary sm" @click="onToggleEnable(s)" style="margin-right:6px">
                  {{ s.is_enabled ? t('servers.btnDisable') : t('servers.btnEnable') }}
                </button>
                <button
                  class="btn sm"
                  :class="pendingDeleteId === s.id ? 'danger' : 'secondary'"
                  @click="onDelete(s)">
                  {{ pendingDeleteId === s.id ? '✓ ' + t('servers.btnDelete') : t('servers.btnDelete') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Tool assignments ───────────────────────────────────── -->
      <div class="card">
        <h3>{{ t('servers.assignTitle') }}</h3>

        <div v-for="s in servers" :key="`asg-${s.id}`" style="margin-top:14px">
          <h4 style="margin:6px 0">
            {{ t('servers.serverColumn', { name: s.name, slug: s.slug }) }}
            <span style="color:var(--text-muted);font-weight:normal">
              ({{ t('servers.capacity', { used: assignments.assigned[s.slug]?.length || 0, max: s.max_tools }) }})
            </span>
          </h4>
          <div v-if="!assignments.assigned[s.slug] || assignments.assigned[s.slug].length === 0"
               class="empty" style="margin:4px 0">—</div>
          <div v-for="tool in (assignments.assigned[s.slug] || [])" :key="`${s.slug}-${tool}`"
               style="display:flex;align-items:center;gap:8px;padding:4px 0">
            <code style="flex:1">{{ tool }}</code>
            <span style="color:var(--text-muted);font-size:0.85rem">{{ t('servers.moveTo') }}</span>
            <HelmSelect
              :model-value="String(s.id)"
              :options="moveOptions"
              min-width="160px"
              @update:model-value="(v: string) => onMove(tool, v)"
            />
          </div>
        </div>

        <h4 style="margin:14px 0 6px">{{ t('servers.unassignedColumn') }}</h4>
        <div v-if="assignments.unassigned.length === 0" class="empty">—</div>
        <div v-for="tool in assignments.unassigned" :key="`u-${tool}`"
             style="display:flex;align-items:center;gap:8px;padding:4px 0">
          <code style="flex:1">{{ tool }}</code>
          <span style="color:var(--text-muted);font-size:0.85rem">{{ t('servers.moveTo') }}</span>
          <HelmSelect
            model-value=""
            :options="moveOptions"
            min-width="160px"
            @update:model-value="(v: string) => onMove(tool, v)"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.server-create-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 8px;
}
.server-create-row input[type=text] {
  flex: 1;
  width: auto;
  min-width: 160px;
}
.server-create-row .btn {
  flex: 0 0 auto;
}
</style>
