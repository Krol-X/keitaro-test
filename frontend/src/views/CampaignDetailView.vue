<template>
  <div v-if="campaign" class="detail-page">
    <header class="detail-header">
      <div>
        <h1>{{ campaign.name }}</h1>
        <div class="detail-subline">
          <span class="detail-id">ID: {{ campaign.campaign_id }}</span>
          <span class="status-pill" :class="campaign.state === 'active' ? 'status-active' : 'status-disabled'">
            <span class="status-dot"></span>{{ campaign.state === 'active' ? 'Активна' : 'Выключена' }}
          </span>
          <a v-if="campaign.campaign_url" :href="campaign.campaign_url" target="_blank" rel="noopener noreferrer">{{ campaign.campaign_url }}</a>
        </div>
        <p v-if="saveError" class="notice notice-error mt-3" role="alert">{{ saveError }}</p>
      </div>
      <button class="button button-secondary" type="button" @click="$router.back()">
        <i class="pi pi-arrow-left" aria-hidden="true"></i>Назад
      </button>
    </header>

    <div class="detail-layout">
      <div class="detail-main">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2>Настройки кампании</h2>
              <p class="panel-subtitle">Название, состояние и привязки кампании.</p>
            </div>
            <button class="button button-primary button-small" type="button" :disabled="savingCampaign || !campaignChanged" @click="saveCampaign">
              {{ savingCampaign ? 'Сохранение…' : 'Сохранить' }}
            </button>
          </div>
          <div class="panel-body">
            <div class="campaign-edit-grid">
              <label>Название<input v-model.trim="draft.name" maxlength="120" /></label>
              <label>Состояние
                <select v-model="draft.state">
                  <option value="active">Активна</option>
                  <option value="disabled">Выключена</option>
                </select>
              </label>
              <label>Домен<select v-model="draft.domainId"><option value="">Не задан</option><option v-for="item in references.domains" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
              <label>Группа кампаний<select v-model="draft.groupId"><option value="">Не задана</option><option v-for="item in references.groups" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
              <label>Источник трафика<select v-model="draft.trafficSourceId"><option value="">Не задан</option><option v-for="item in references.traffic_sources" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h2>Потоки и офферы</h2>
              <p class="panel-subtitle">Доли и блокировки офферов сохраняются отдельно от настроек кампании.</p>
            </div>
            <button class="button button-primary button-small" type="button" :disabled="!changedStreams.length || saving" @click="saveAll">
              {{ saving ? 'Сохранение…' : 'Сохранить офферы' }}
            </button>
          </div>
          <div class="panel-body">
            <div class="stream-list">
              <article v-for="stream in campaign.streams || []" :key="stream.stream_id || stream.id" class="stream-card">
                <div class="stream-head">
                  <span class="stream-position">{{ stream.position }}</span>
                  <span class="stream-name">{{ stream.name }}</span>
                  <span class="stream-type" :class="{ 'is-forced': stream.type === 'forced' }">{{ streamTypeLabel(stream.type) }}</span>
                  <div class="stream-head-right">
                    <span class="status-pill" :class="stream.state === 'active' ? 'status-active' : 'status-disabled'">
                      <span class="status-dot"></span>{{ stream.state === 'active' ? 'Активен' : 'Выключен' }}
                    </span>
                  </div>
                </div>
                <div v-if="isRedirectStream(stream)" class="stream-body">
                  <div>
                    <div class="redirect-label">Редирект</div>
                    <div class="redirect-value mt-1">{{ stream.action_payload || stream.redirect_url || '—' }}</div>
                  </div>
                  <div>
                    <div class="redirect-label">Условие</div>
                    <p class="mb-0 mt-1 text-sm text-gray-700">{{ describeFilters(stream) }}</p>
                  </div>
                </div>
                <div v-if="holdsOffers(stream)" class="stream-body">
                  <div class="offer-add">
                    <div class="offer-add-head">
                      <span class="offer-add-title">Добавить оффер</span>
                      <button
                        v-if="!offersLoaded"
                        class="button button-secondary button-small"
                        type="button"
                        :disabled="loadingOffers"
                        @click="loadOffers()"
                      >
                        {{ loadingOffers ? 'Загрузка…' : 'Загрузить офферы' }}
                      </button>
                    </div>
                    <div class="offer-add-row">
                      <input
                        v-model.trim="offerSearchQuery"
                        type="search"
                        placeholder="Фильтр по названию или ID"
                        aria-label="Поиск офферов для добавления"
                      />
                      <select v-model="selectedOfferId" :disabled="!addableOffers(stream).length" aria-label="Оффер для добавления">
                        <option value="">{{ addableOfferPlaceholder(stream) }}</option>
                        <option v-for="item in addableOffers(stream)" :key="item.offer_id" :value="String(item.offer_id)">{{ item.name }} (ID: {{ item.offer_id }})</option>
                      </select>
                      <button class="button button-primary button-small" type="button" :disabled="!selectedOfferId" @click="addOffer(stream.stream_id || stream.id)">
                        <i class="pi pi-plus" aria-hidden="true"></i>Добавить
                      </button>
                    </div>
                    <p class="offer-add-hint">Новый оффер добавляется с долей 0%, чтобы не менять текущее распределение.</p>
                    <p v-if="offerError" class="inline-error">{{ offerError }}</p>
                    <p v-else-if="offersLoaded && !store.offers.length" class="inline-error">Keitaro не вернул доступные офферы.</p>
                  </div>

                  <div v-if="(stream.offers || []).length" class="table-scroll">
                    <table class="offers-table">
                      <thead>
                        <tr>
                          <th>Оффер</th>
                          <th>Доля</th>
                          <th>Состояние</th>
                          <th aria-label="Действия"></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="offer in stream.offers" :key="offer.offer_id">
                          <td>
                            <span class="offer-name">{{ offer.name || `Оффер #${offer.offer_id}` }}</span>
                            <span class="offer-id">ID: {{ offer.offer_id }}</span>
                          </td>
                          <td>
                            <div class="share-field">
                              <input
                                v-model.number="offer.share"
                                type="number"
                                min="0"
                                max="100"
                                step="1"
                                :disabled="offer.share_locked"
                                :aria-label="`Доля оффера ${offer.offer_id} в процентах`"
                              />
                              <span class="share-suffix">%</span>
                              <button
                                type="button"
                                class="icon-button"
                                :class="{ 'is-locked': offer.share_locked }"
                                :aria-label="offer.share_locked ? `Разблокировать долю оффера ${offer.offer_id}` : `Заблокировать долю оффера ${offer.offer_id}`"
                                :title="offer.share_locked ? 'Доля защищена от последующих изменений' : 'Заблокировать долю от последующих изменений'"
                                @click="toggleOfferLock(stream.stream_id || stream.id, offer.offer_id)"
                              >
                                <i :class="offer.share_locked ? 'pi pi-lock' : 'pi pi-lock-open'" aria-hidden="true"></i>
                              </button>
                            </div>
                          </td>
                          <td>
                            <span class="status-pill" :class="offer.state === 'active' ? 'status-active' : 'status-disabled'">
                              <span class="status-dot"></span>{{ offer.state === 'active' ? 'Активен' : 'Отключён' }}
                            </span>
                          </td>
                          <td class="cell-actions">
                            <button v-if="offer.state === 'active'" class="button button-danger-quiet button-small" type="button" @click="removeOffer(stream.stream_id || stream.id, offer.offer_id)">
                              <i class="pi pi-ban" aria-hidden="true"></i>Отключить
                            </button>
                            <button v-else class="button button-secondary button-small" type="button" @click="restoreOffer(stream.stream_id || stream.id, offer.offer_id)">
                              <i class="pi pi-replay" aria-hidden="true"></i>Восстановить
                            </button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p v-else class="offers-empty mb-0">В потоке пока нет офферов.</p>
                </div>
              </article>
            </div>

            <div v-if="!streamsWithOffers" class="stream-missing">
              <p class="stream-missing-title">В кампании нет потока с офферами</p>
              <p class="stream-missing-text">
                Остался только перехватывающий поток: трафик, не попавший под его условие, никуда не уходит.
                Создайте поток с офферами — он встанет перед замыкающим.
              </p>
            </div>

            <button
              v-if="!creatingStream"
              class="button button-secondary button-small stream-create-toggle"
              type="button"
              @click="startStreamCreation"
            >
              <i class="pi pi-plus" aria-hidden="true"></i>Добавить поток с офферами
            </button>

            <form v-else class="stream-create" @submit.prevent="submitStream">
              <div class="stream-create-head">
                <span class="offer-add-title">Новый поток с офферами</span>
                <button class="country-clear" type="button" @click="cancelStreamCreation">Отмена</button>
              </div>

              <div class="stream-create-grid">
                <label>
                  Название
                  <input v-model.trim="newStream.name" maxlength="120" placeholder="Например, Основной поток" />
                </label>
                <label>
                  Тип потока
                  <select v-model="newStream.type">
                    <option value="regular">Обычный — перед замыкающим</option>
                    <option value="default">Замыкающий — последним</option>
                  </select>
                </label>
              </div>

              <div v-if="!offersLoaded" class="stream-create-note">
                <span>Список офферов ещё не загружен.</span>
                <button class="button button-secondary button-small" type="button" :disabled="loadingOffers" @click="loadOffers()">
                  {{ loadingOffers ? 'Загрузка…' : 'Загрузить офферы' }}
                </button>
              </div>
              <p v-else-if="!store.offers.length" class="inline-error">Keitaro не вернул доступные офферы.</p>
              <p v-else class="stream-create-offers-label">
                Офферы потока — выберите хотя бы один, доли разделятся поровну:
              </p>

              <div v-if="store.offers.length" class="stream-create-offers">
                <label v-for="item in store.offers" :key="item.offer_id" class="stream-create-offer">
                  <input
                    type="checkbox"
                    :value="String(item.offer_id)"
                    :checked="newStream.offerIds.includes(String(item.offer_id))"
                    @change="toggleNewStreamOffer(String(item.offer_id))"
                  />
                  <span>{{ item.name }} <span class="offer-id">ID: {{ item.offer_id }}</span></span>
                </label>
              </div>

              <p v-if="createStreamError" class="inline-error">{{ createStreamError }}</p>

              <div class="stream-create-actions">
                <button
                  class="button button-primary button-small"
                  type="submit"
                  :disabled="creating || !newStream.offerIds.length"
                >
                  {{ creating ? 'Создаём…' : 'Создать поток' }}
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>

      <aside class="detail-aside">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2>Фильтрация стран</h2>
              <p class="panel-subtitle">Страны, которые уходят на Google вместо офферов.</p>
            </div>
          </div>
          <div class="panel-body">
            <CountrySelector v-model="draftCountries" :countries="references.countries" />
            <p v-if="countriesError" class="notice notice-error mt-3" role="alert">{{ countriesError }}</p>
          </div>
          <div class="panel-body">
            <button class="button button-primary w-full" type="button" :disabled="savingCountries || !countriesChanged" @click="saveCountries">
              {{ savingCountries ? 'Сохранение…' : 'Сохранить страны' }}
            </button>
            <p class="offer-add-hint mt-2">Пустой список отключает поток с редиректом.</p>
          </div>
        </section>
      </aside>
    </div>
  </div>
  <div v-else class="loading-panel">
    <span class="loader" aria-hidden="true"></span><span>Загружаем кампанию…</span>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useCampaignStore } from '../stores/campaigns'
import CountrySelector from '../components/CountrySelector.vue'

const route = useRoute()
const store = useCampaignStore()
const campaign = ref<any>(null)
const references = ref<any>({ domains: [], groups: [], traffic_sources: [], countries: [] })
const draft = reactive({ name: '', state: 'active', domainId: '', groupId: '', trafficSourceId: '' })
const campaignChanged = computed(() => Boolean(campaign.value && (
  draft.name !== campaign.value.name ||
  draft.state !== campaign.value.state ||
  draft.domainId !== String(campaign.value.domain_id ?? '') ||
  draft.groupId !== String(campaign.value.group_id ?? '') ||
  draft.trafficSourceId !== String(campaign.value.traffic_source_id ?? '')
)))
const savingCampaign = ref(false)
const saving = ref(false)
const saveError = ref('')
const offerSearchQuery = ref('')
const selectedOfferId = ref('')
const draftCountries = ref<string[]>([])
const savedCountries = ref<string[]>([])
const savingCountries = ref(false)
const countriesError = ref('')
const countriesChanged = computed(() => {
  const left = [...draftCountries.value].sort().join(',')
  const right = [...savedCountries.value].sort().join(',')
  return left !== right
})

const fetchDetail = async () => {
  try {
    campaign.value = await store.getCampaignDetail(Number(route.params.id))
    rememberSnapshots()
    draft.name = campaign.value.name || ''
    draft.state = campaign.value.state || 'disabled'
    draft.domainId = String(campaign.value.domain_id ?? '')
    draft.groupId = String(campaign.value.group_id ?? '')
    draft.trafficSourceId = String(campaign.value.traffic_source_id ?? '')
    const loadedCountries = [...(campaign.value.excluded_countries || [])].sort()
    // Не затираем выбор пользователя, если он уже что-то изменил до ответа сервера.
    const pendingEdit = [...draftCountries.value].sort().join(',') !== [...savedCountries.value].sort().join(',')
    savedCountries.value = loadedCountries
    if (!pendingEdit) draftCountries.value = loadedCountries
  } catch (error: any) {
    saveError.value = error?.response?.data?.detail || 'Не удалось загрузить кампанию.'
  }
}

const saveCampaign = async () => {
  if (!campaign.value || !campaignChanged.value || savingCampaign.value) return
  savingCampaign.value = true
  saveError.value = ''
  try {
    await store.updateCampaign(campaign.value.campaign_id, {
      name: draft.name,
      state: draft.state,
      domain_id: draft.domainId ? Number(draft.domainId) : null,
      group_id: draft.groupId ? Number(draft.groupId) : null,
      traffic_source_id: draft.trafficSourceId ? Number(draft.trafficSourceId) : null
    })
    await fetchDetail()
    await store.fetchCampaigns()
  } catch (error: any) {
    saveError.value = error?.response?.data?.detail || 'Не удалось сохранить настройки кампании.'
  } finally {
    savingCampaign.value = false
  }
}

const saveCountries = async () => {
  if (!campaign.value || savingCountries.value || !countriesChanged.value) return
  savingCountries.value = true
  countriesError.value = ''
  try {
    await store.updateCountryFilter(campaign.value.campaign_id, draftCountries.value)
    await fetchDetail()
  } catch (error: any) {
    countriesError.value = error?.response?.data?.detail || 'Не удалось сохранить страны фильтрации.'
  } finally {
    savingCountries.value = false
  }
}

// Содержимое потока определяет схема (landings — офферы, redirect — редирект),
// тип — только приоритет: forced → regular → default. Бэкенд нормализует schema,
// но если поле пришло в неизвестном виде, поток не должен оставаться без управления офферами.
const schemaOf = (stream: any): string => {
  const raw = stream?.schema
  if (typeof raw === 'string') return raw.toLowerCase()
  if (raw && typeof raw === 'object') {
    const nested = raw.value ?? raw.name ?? raw.slug ?? raw.id ?? raw.type
    return typeof nested === 'string' ? nested.toLowerCase() : ''
  }
  return ''
}
const isRedirectSchema = (stream: any) => schemaOf(stream).includes('redirect')
const isLandingsSchema = (stream: any) => schemaOf(stream).includes('landing') || schemaOf(stream).includes('offer')
const holdsOffers = (stream: any) => {
  if (isRedirectSchema(stream)) return false
  if (isLandingsSchema(stream)) return true
  // Схема неизвестна/не пришла: ориентируемся на тип, но перехватывающий без redirect-схемы
  // тоже может содержать офферы — тогда показываем управление ими.
  return stream.type !== 'forced'
}
const isRedirectStream = (stream: any) => !holdsOffers(stream) && (stream.type === 'forced' || isRedirectSchema(stream))
const STREAM_TYPE_LABELS: Record<string, string> = {
  forced: 'Перехватывающий',
  regular: 'Обычный',
  default: 'Замыкающий'
}
const streamTypeLabel = (type: string) => STREAM_TYPE_LABELS[type] || type || '—'

const describeFilters = (stream: any) => {
  const filters = stream.filters || []
  if (!filters.length) return 'Без дополнительных условий'
  return filters.map((filter: any) => `${filter.name}: ${(filter.payload || []).join(', ')}`).join('; ')
}

const offersLoaded = ref(false)
const loadingOffers = ref(false)
const offerError = ref('')

// Список офферов грузим сразу, чтобы добавление было доступно без обязательного поиска.
const loadOffers = async () => {
  if (loadingOffers.value) return
  loadingOffers.value = true
  offerError.value = ''
  try {
    await store.fetchOffers()
    offersLoaded.value = true
  } catch (error: any) {
    offerError.value = error?.response?.data?.detail || 'Не удалось загрузить офферы.'
  } finally {
    loadingOffers.value = false
  }
}

const matchesOfferQuery = (offer: any, query: string) => {
  if (!query) return true
  const normalized = query.toLowerCase()
  return String(offer.name || '').toLowerCase().includes(normalized)
    || String(offer.offer_id) === normalized
}

const addableOffers = (stream: any) => store.offers.filter((candidate: any) =>
  !(stream.offers || []).some((offer: any) => Number(offer.offer_id) === Number(candidate.offer_id))
  && matchesOfferQuery(candidate, offerSearchQuery.value.trim())
)

const addableOfferPlaceholder = (stream: any) => {
  if (!offersLoaded.value) return 'Загружаем офферы…'
  if (!store.offers.length) return 'Keitaro не вернул офферы'
  if (!addableOffers(stream).length) {
    return offerSearchQuery.value.trim() ? 'Ничего не найдено по фильтру' : 'Все офферы уже добавлены'
  }
  return 'Выберите оффер'
}

const addOffer = (streamId: number) => {
  const stream = campaign.value?.streams?.find((item: any) => Number(item.stream_id || item.id) === Number(streamId))
  const offer = store.offers.find((item: any) => String(item.offer_id) === selectedOfferId.value)
  if (!stream || !offer || (stream.offers || []).some((item: any) => Number(item.offer_id) === Number(offer.offer_id))) return
  stream.offers.push({
    offer_id: Number(offer.offer_id),
    name: offer.name,
    share: 0,
    state: 'active',
    share_locked: false
  })
  selectedOfferId.value = ''
}

const findOffer = (streamId: number, offerId: number) => {
  const stream = campaign.value?.streams?.find((item: any) => (item.stream_id || item.id) === streamId)
  return stream?.offers?.find((offer: any) => offer.offer_id === offerId)
}

const removeOffer = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.state = 'disabled'
  }
}

const restoreOffer = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.state = 'active'
  }
}

const toggleOfferLock = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.share_locked = !offer.share_locked
  }
}

const offerPayload = (stream: any) => (stream.offers || []).map((offer: any) => ({
  offer_id: offer.offer_id,
  share: Number(offer.share ?? 0),
  state: offer.state === 'disabled' ? 'disabled' : 'active',
  share_locked: Boolean(offer.share_locked)
}))

// Сравнение с последним сохранённым состоянием потока, чтобы не гонять PUT по всем потокам подряд.
const snapshot = (offers: any[]) => JSON.stringify(
  offers.map((offer: any) => [Number(offer.offer_id), Number(offer.share ?? 0), offer.state === 'disabled' ? 'disabled' : 'active', Boolean(offer.share_locked)])
    .sort((a, b) => a[0] - b[0])
)
const savedSnapshots = ref<Record<number, string>>({})

const rememberSnapshots = () => {
  const snapshots: Record<number, string> = {}
  for (const stream of campaign.value?.streams || []) {
    if (!holdsOffers(stream)) continue
    snapshots[Number(stream.stream_id || stream.id)] = snapshot(stream.offers || [])
  }
  savedSnapshots.value = snapshots
}

const changedStreams = computed(() => (campaign.value?.streams || []).filter((stream: any) => {
  if (!holdsOffers(stream)) return false
  const id = Number(stream.stream_id || stream.id)
  return savedSnapshots.value[id] !== snapshot(stream.offers || [])
}))

const saveAll = async () => {
  if (!campaign.value || saving.value) return
  const streams = changedStreams.value
  if (!streams.length) return
  saving.value = true
  saveError.value = ''
  try {
    for (const stream of streams) {
      // Пустой список активных офферов Keitaro превращает в поток без схемы — он пропадает из кампании.
      const active = (stream.offers || []).filter((offer: any) => offer.state !== 'disabled')
      if (!active.length) {
        saveError.value = `В потоке «${stream.name || stream.stream_id}» должен остаться хотя бы один активный оффер. Чтобы убрать поток, выключите его.`
        return
      }
      await store.updateStreamOffers(campaign.value.campaign_id, stream.stream_id || stream.id, {
        offers: offerPayload(stream)
      })
    }
    await fetchDetail()
  } catch (error: any) {
    saveError.value = error?.response?.data?.detail || 'Не удалось сохранить изменения офферов.'
  } finally {
    saving.value = false
  }
}

const streamsWithOffers = computed(() => (campaign.value?.streams || []).some((stream: any) => holdsOffers(stream)))

const creatingStream = ref(false)
const creating = ref(false)
const createStreamError = ref('')
const newStream = reactive({ name: '', type: 'regular', offerIds: [] as string[] })

const startStreamCreation = () => {
  createStreamError.value = ''
  newStream.name = ''
  newStream.type = 'regular'
  newStream.offerIds = []
  creatingStream.value = true
}

const cancelStreamCreation = () => {
  creatingStream.value = false
  createStreamError.value = ''
}

const toggleNewStreamOffer = (offerId: string) => {
  const index = newStream.offerIds.indexOf(offerId)
  if (index >= 0) {
    newStream.offerIds.splice(index, 1)
  } else {
    newStream.offerIds.push(offerId)
  }
}

const submitStream = async () => {
  if (!campaign.value || creating.value || !newStream.offerIds.length) return
  creating.value = true
  createStreamError.value = ''
  try {
    await store.createStream(campaign.value.campaign_id, {
      name: newStream.name || null,
      type: newStream.type,
      offer_ids: newStream.offerIds.map(Number)
    })
    creatingStream.value = false
    await fetchDetail()
    await store.fetchCampaigns()
  } catch (error: any) {
    createStreamError.value = error?.response?.data?.detail || 'Не удалось создать поток.'
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchDetail()
  loadOffers()
  store.fetchReferences().then(data => { references.value = data }).catch(() => {})
})
</script>
