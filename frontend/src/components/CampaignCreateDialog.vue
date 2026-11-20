<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="close">
    <section class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl" role="dialog" aria-modal="true" aria-labelledby="create-campaign-title">
      <div class="mb-5 flex items-center justify-between">
        <h2 id="create-campaign-title" class="text-xl font-semibold text-gray-900">Создать кампанию</h2>
        <button type="button" class="rounded px-2 py-1 text-gray-500 hover:bg-gray-100" aria-label="Закрыть" @click="close">✕</button>
      </div>

      <div v-if="loadingOptions" class="py-8 text-center text-gray-500">Загрузка справочников Keitaro…</div>
      <form v-else class="space-y-4" @submit.prevent="submit">
        <label class="block text-sm font-medium text-gray-700">
          Название кампании
          <input v-model.trim="form.name" required maxlength="120" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2" placeholder="Например, Весенняя кампания" />
        </label>

        <label class="block text-sm font-medium text-gray-700">
          Оффер
          <select v-model="form.offerId" required class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2">
            <option value="" disabled>Выберите оффер</option>
            <option v-for="offer in offers" :key="offer.offer_id" :value="String(offer.offer_id)">{{ offer.name }} (ID: {{ offer.offer_id }})</option>
          </select>
          <span v-if="offers.length === 0" class="mt-1 block text-xs text-amber-700">Keitaro не вернул доступные офферы.</span>
        </label>

        <div class="grid gap-4 sm:grid-cols-3">
          <label class="block text-sm font-medium text-gray-700">
            Домен
            <select v-model="form.domainId" class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2">
              <option value="">По умолчанию{{ references.defaults.domain_id ? ` (ID: ${references.defaults.domain_id})` : '' }}</option>
              <option v-for="item in references.domains" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option>
            </select>
          </label>
          <label class="block text-sm font-medium text-gray-700">
            Группа кампаний
            <select v-model="form.groupId" class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2">
              <option value="">По умолчанию{{ references.defaults.group_id ? ` (ID: ${references.defaults.group_id})` : '' }}</option>
              <option v-for="item in references.groups" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option>
            </select>
            <span class="mt-1 block text-xs font-normal text-gray-500">Группа — это папка/категория для организации кампаний в Keitaro.</span>
          </label>
          <label class="block text-sm font-medium text-gray-700">
            Источник
            <select v-model="form.trafficSourceId" class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2">
              <option value="">По умолчанию{{ references.defaults.traffic_source_id ? ` (ID: ${references.defaults.traffic_source_id})` : '' }}</option>
              <option v-for="item in references.traffic_sources" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option>
            </select>
          </label>
        </div>

        <fieldset>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <legend class="text-sm font-medium text-gray-700">Страны для принудительного редиректа на Google</legend>
            <span class="text-xs text-gray-500">Выбрано: {{ form.excludedCountries.length }} из {{ references.countries.length }}</span>
          </div>
          <p class="mt-1 text-xs text-gray-500">Оставьте список пустым, если дополнительный поток с редиректом не нужен. Поиск работает по названию и коду ISO.</p>
          <CountrySelector v-model="form.excludedCountries" :countries="references.countries" class="mt-2" />
        </fieldset>

        <section v-if="archiveConflict" class="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" role="alert">
          <h3 class="text-sm font-semibold">Название занято кампанией в архиве</h3>
          <p class="mt-1">
            Кампания «{{ archiveConflict.name }}» уже существует в архиве Keitaro: при удалении имя остаётся
            зарезервированным. Восстановите её со всеми потоками и офферами или создайте копию под другим названием.
          </p>

          <ul v-if="archiveConflict.archived_campaigns.length" class="mt-3 space-y-2">
            <li
              v-for="item in archiveConflict.archived_campaigns"
              :key="item.campaign_id"
              class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-white/70 px-3 py-2"
            >
              <span class="font-medium">#{{ item.campaign_id }} · {{ item.name }}</span>
              <button
                type="button"
                class="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
                :disabled="restoring"
                @click="restoreArchived(item)"
              >
                {{ restoring ? 'Восстанавливаем…' : 'Восстановить' }}
              </button>
            </li>
          </ul>
          <p v-else class="mt-2 text-xs">
            Список архивных кампаний недоступен — восстановите кампанию в интерфейсе Keitaro.
          </p>

          <button type="button" class="mt-3 rounded-md border border-amber-400 px-3 py-1 text-xs font-medium" @click="renameCopy">
            Создать под названием «{{ suggestedName }}»
          </button>
        </section>

        <p v-if="restoreError" class="rounded-md bg-red-50 p-3 text-sm text-red-700">{{ restoreError }}</p>
        <p v-if="error" class="rounded-md bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
        <div class="flex justify-end gap-3 border-t pt-4">
          <button type="button" class="rounded-md border px-4 py-2 text-sm" :disabled="submitting" @click="close">Отмена</button>
          <button type="submit" class="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50" :disabled="submitting || offers.length === 0">
            {{ submitting ? 'Создание…' : 'Создать' }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useCampaignStore } from '../stores/campaigns'
import CountrySelector from './CountrySelector.vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

interface Reference { id: number; name: string }
interface Country { code: string; name: string }

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (event: 'update:visible', value: boolean): void }>()
const store = useCampaignStore()
const loadingOptions = ref(false)
const submitting = ref(false)
const error = ref('')
const offers = ref<{ offer_id: number; name: string }[]>([])
const references = ref<{ domains: Reference[]; groups: Reference[]; traffic_sources: Reference[]; countries: Country[]; defaults: Record<string, number | null> }>({
  domains: [], groups: [], traffic_sources: [], countries: [], defaults: {}
})
const form = reactive({
  name: '',
  offerId: '',
  domainId: '',
  groupId: '',
  trafficSourceId: '',
  excludedCountries: ['PL', 'LT']
})

interface ArchivedCampaign { campaign_id: number; name: string }
interface ArchiveConflict { code: string; message: string; name: string; archived_campaigns: ArchivedCampaign[] }

const archiveConflict = ref<ArchiveConflict | null>(null)
const restoring = ref(false)
const restoreError = ref('')
const firstAvailableName = ref('')

const suggestedName = computed(() => firstAvailableName.value || `${form.name} (2)`)

const resetConflict = () => {
  archiveConflict.value = null
  restoreError.value = ''
  firstAvailableName.value = ''
}

// Keitaro держит имена архивных кампаний — предлагаем имя, которого нет ни среди активных, ни среди архивных.
const suggestFreeName = async (baseName: string) => {
  if (!store.references) await store.fetchReferences().catch(() => null)
  const active = new Set((store.campaigns || []).map((item: any) => String(item.name).trim().toLocaleLowerCase()))
  try {
    const { data } = await axios.get(`${API_BASE}/campaigns/deleted`)
    for (const item of data.items || data || []) active.add(String(item.name).trim().toLocaleLowerCase())
  } catch {
    // Архив может быть недоступен — тогда просто подбираем вариант по активным кампаниям.
  }
  for (let index = 2; index < 100; index += 1) {
    const candidate = `${baseName} (${index})`
    if (!active.has(candidate.trim().toLocaleLowerCase())) return candidate
  }
  return `${baseName} (${Date.now()})`
}

const parseArchiveConflict = (detail: any): ArchiveConflict | null => {
  if (!detail || typeof detail !== 'object') return null
  if (detail.code !== 'NAME_IN_ARCHIVE') return null
  return {
    code: detail.code,
    message: detail.message || '',
    name: detail.name || form.name,
    archived_campaigns: Array.isArray(detail.archived_campaigns) ? detail.archived_campaigns : []
  }
}

const renameCopy = () => {
  form.name = suggestedName.value
  resetConflict()
}

const restoreArchived = async (item: ArchivedCampaign) => {
  restoring.value = true
  restoreError.value = ''
  try {
    await store.restoreCampaign(item.campaign_id)
    await store.fetchCampaigns()
    close()
  } catch (cause: any) {
    restoreError.value = cause?.response?.data?.detail || 'Не удалось восстановить кампанию из архива.'
  } finally {
    restoring.value = false
  }
}

const close = () => emit('update:visible', false)

watch(() => form.name, () => {
  if (archiveConflict.value) resetConflict()
  idempotencyKey = ''
})

watch(() => props.visible, async (isVisible) => {
  if (!isVisible) return
  error.value = ''
  resetConflict()
  loadingOptions.value = true
  try {
    const [referenceData, offerData] = await Promise.all([store.fetchReferences(), store.fetchOffers()])
    references.value = referenceData
    offers.value = offerData
    form.domainId = referenceData.defaults.domain_id ? String(referenceData.defaults.domain_id) : ''
    form.groupId = referenceData.defaults.group_id ? String(referenceData.defaults.group_id) : ''
    form.trafficSourceId = referenceData.defaults.traffic_source_id ? String(referenceData.defaults.traffic_source_id) : ''
  } catch (cause: any) {
    error.value = cause?.response?.data?.detail || 'Не удалось загрузить справочники Keitaro.'
  } finally {
    loadingOptions.value = false
  }
}, { immediate: true })

// Ключ держим на попытку: повтор после конфликта имени — это уже другой запрос.
let idempotencyKey = ''
const nextIdempotencyKey = () => {
  idempotencyKey = globalThis.crypto?.randomUUID?.() || `campaign-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const submit = async () => {
  error.value = ''
  restoreError.value = ''
  submitting.value = true
  try {
    if (!idempotencyKey) nextIdempotencyKey()
    await store.createCampaign({
      name: form.name,
      offer_id: Number(form.offerId),
      excluded_countries: form.excludedCountries,
      domain_id: form.domainId ? Number(form.domainId) : undefined,
      group_id: form.groupId ? Number(form.groupId) : undefined,
      traffic_source_id: form.trafficSourceId ? Number(form.trafficSourceId) : undefined
    }, idempotencyKey)
    await store.fetchCampaigns()
    close()
  } catch (cause: any) {
    const conflict = parseArchiveConflict(cause?.response?.data?.detail)
    if (conflict) {
      archiveConflict.value = conflict
      firstAvailableName.value = await suggestFreeName(form.name)
      nextIdempotencyKey()
    } else {
      error.value = cause?.response?.data?.detail || 'Не удалось создать кампанию.'
      nextIdempotencyKey()
    }
  } finally {
    submitting.value = false
  }
}
</script>
