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
          <input v-model="countrySearch" type="search" class="mt-2 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="Найти страну или код, например BY" aria-label="Поиск страны" />
          <div class="mt-2 flex gap-3 text-sm">
            <button type="button" class="text-blue-700 hover:underline" @click="selectAllCountries">Выбрать все</button>
            <button type="button" class="text-blue-700 hover:underline" @click="clearCountries">Снять выбор</button>
          </div>
          <div class="mt-2 max-h-40 overflow-y-auto rounded-md border border-gray-200 p-3">
            <div class="grid gap-x-4 gap-y-2 sm:grid-cols-2">
              <label v-for="country in filteredCountries" :key="country.code" class="inline-flex items-center gap-2 text-sm text-gray-700">
                <input v-model="form.excludedCountries" type="checkbox" :value="country.code" class="rounded border-gray-300" />
                {{ displayCountryName(country) }} ({{ country.code }})
              </label>
            </div>
            <p v-if="filteredCountries.length === 0" class="text-sm text-gray-500">Страны не найдены.</p>
          </div>
        </fieldset>

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
import { useCampaignStore } from '../stores/campaigns'

interface Reference { id: number; name: string }
interface Country { code: string; name: string }

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (event: 'update:visible', value: boolean): void }>()
const store = useCampaignStore()
const loadingOptions = ref(false)
const submitting = ref(false)
const error = ref('')
const countrySearch = ref('')
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

const close = () => emit('update:visible', false)
const countryNames = new Intl.DisplayNames(['ru'], { type: 'region' })
const displayCountryName = (country: Country) => countryNames.of(country.code) || country.name
const filteredCountries = computed(() => {
  const query = countrySearch.value.trim().toLocaleLowerCase()
  return [...references.value.countries]
    .filter(country =>
      !query ||
      displayCountryName(country).toLocaleLowerCase().includes(query) ||
      country.name.toLocaleLowerCase().includes(query) ||
      country.code.toLowerCase().includes(query)
    )
    .sort((left, right) => displayCountryName(left).localeCompare(displayCountryName(right), 'ru'))
})
const selectAllCountries = () => {
  form.excludedCountries = references.value.countries.map(country => country.code)
}
const clearCountries = () => {
  form.excludedCountries = []
}

watch(() => props.visible, async (isVisible) => {
  if (!isVisible) return
  error.value = ''
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

const submit = async () => {
  error.value = ''
  submitting.value = true
  try {
    const idempotencyKey = globalThis.crypto?.randomUUID?.() || `campaign-${Date.now()}-${Math.random().toString(16).slice(2)}`
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
    error.value = cause?.response?.data?.detail || 'Не удалось создать кампанию.'
  } finally {
    submitting.value = false
  }
}
</script>
