<template>
  <div v-if="campaign" class="p-6 bg-white rounded-lg shadow-sm">
    <!-- Заголовок и настройки (единый стиль) -->
    <div class="flex justify-between items-start mb-6 border-b pb-4">
      <div>
        <h2 class="text-2xl font-bold text-gray-900">{{ campaign?.name || 'Загрузка...' }} (ID: {{ campaign?.campaign_id }})</h2>
        <div class="flex gap-2 mt-2">
          <Tag :value="campaign?.state" :severity="campaign?.state === 'active' ? 'success' : 'danger'" />
          <a v-if="campaign?.campaign_url" :href="campaign.campaign_url" target="_blank" rel="noopener noreferrer" class="text-blue-600 underline hover:text-blue-800 transition-colors">{{ campaign.campaign_url }}</a>
        </div>
      </div>
      <Button label="Назад" @click="$router.back()" severity="secondary" outlined />
    </div>

    <section class="detail-edit-panel">
      <div class="detail-section-heading">
        <div><p class="eyebrow">Редактирование</p><h3>Основные настройки</h3></div>
        <button class="button button-primary" type="button" :disabled="savingCampaign || !campaignChanged" @click="saveCampaign">
          {{ savingCampaign ? 'Сохранение…' : 'Сохранить настройки' }}
        </button>
      </div>
      <div class="campaign-edit-grid">
        <label>Название кампании<input v-model.trim="draft.name" maxlength="120" /></label>
        <label>Состояние<select v-model="draft.state"><option value="active">Активна</option><option value="disabled">Выключена</option></select></label>
        <label>Домен<select v-model="draft.domainId"><option value="">Не задан</option><option v-for="item in references.domains" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
        <label>Группа кампаний<select v-model="draft.groupId"><option value="">Не задана</option><option v-for="item in references.groups" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
        <label>Источник трафика<select v-model="draft.trafficSourceId"><option value="">Не задан</option><option v-for="item in references.traffic_sources" :key="item.id" :value="String(item.id)">{{ item.name }} (ID: {{ item.id }})</option></select></label>
      </div>
    </section>

    <!-- Настройки (единый стиль карточек) -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      <div v-for="item in [
        { label: 'Домен', val: campaign?.domain_name, id: campaign?.domain_id },
        { label: 'Группа', val: campaign?.group_name, id: campaign?.group_id },
        { label: 'Источник', val: campaign?.traffic_source_name, id: campaign?.traffic_source_id }
      ]" :key="item.label" class="p-3 bg-gray-50 rounded border">
        <div class="text-xs text-gray-500 uppercase">{{ item.label }}</div>
        <div class="font-medium">{{ item.val }} (ID: {{ item.id }})</div>
      </div>
    </div>

    <!-- Потоки (единый стиль Accordion) -->
    <div class="space-y-4">
      <h3 class="text-lg font-semibold text-gray-800">Потоки кампании</h3>
      <Accordion>
        <AccordionPanel v-for="stream in campaign?.streams || []" :key="stream.stream_id || stream.id" :value="String(stream.stream_id || stream.id)" class="border-none shadow-sm">
          <AccordionHeader>Поток {{ stream.position }}: {{ stream.name }} ({{ stream.type }})</AccordionHeader>
          <AccordionContent>
          <div class="p-4 bg-gray-50 rounded-lg">
            <!-- Общие данные потока -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <div class="text-sm text-gray-500 uppercase">Состояние</div>
                <Tag :value="stream.state" :severity="stream.state === 'active' ? 'success' : 'danger'" />
              </div>
              <div>
                <div class="text-sm text-gray-500 uppercase">Условие</div>
                <div class="font-medium text-gray-700">{{ describeFilters(stream) }}</div>
              </div>
            </div>

            <!-- Редирект (для forced потока - Создаватор) -->
            <div v-if="stream.type === 'forced'" class="mb-4 p-3 bg-white border rounded">
              <div class="text-sm text-gray-500 uppercase mb-1">Редирект (Google)</div>
              <div class="font-mono bg-gray-100 p-2 rounded text-sm">{{ stream.action_payload || stream.redirect_url || '—' }}</div>
            </div>

            <!-- Офферы (для default потока - Редактор) -->
            <div v-if="stream.type === 'default' && stream.offers?.length" class="mt-4">
              <div class="flex justify-between items-center mb-3">
                <h4 class="font-semibold text-gray-800">Офферы потока</h4>
              </div>
              
              <!-- Офферы остаются в списке; отключённые помечаются статусом -->
              <DataTable :value="stream.offers" class="mt-2" :showGridlines="true">
                <Column field="offer_id" header="ID" class="w-20" />
                <Column header="Название">
                  <template #body="{ data }">{{ data.name || `Оффер #${data.offer_id}` }}</template>
                </Column>
                <Column header="Доля / блокировка">
                  <template #body="{ data }">
                    <div class="flex items-center justify-center gap-2">
                      <input
                        v-model.number="data.share"
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        :disabled="data.share_locked"
                        :aria-label="`Доля оффера ${data.offer_id} в процентах`"
                        class="w-20 rounded border border-gray-300 px-2 py-1 text-center disabled:bg-gray-100 disabled:text-gray-500"
                        @input="hasChanges = true"
                      />
                      <button
                        type="button"
                        class="rounded p-2 hover:bg-gray-100"
                        :class="data.share_locked ? 'text-amber-700' : 'text-gray-500'"
                        :aria-label="data.share_locked ? `Разблокировать долю оффера ${data.offer_id}` : `Заблокировать долю оффера ${data.offer_id}`"
                        :title="data.share_locked ? 'Доля защищена от последующих изменений' : 'Заблокировать долю от последующих изменений'"
                        @click="toggleOfferLock(stream.stream_id || stream.id, data.offer_id)"
                      >
                        <i :class="data.share_locked ? 'pi pi-lock' : 'pi pi-lock-open'" aria-hidden="true"></i>
                      </button>
                    </div>
                  </template>
                </Column>
                <Column field="state" header="Состояние">
                  <template #body="{ data }">
                    <Tag :value="data.state === 'active' ? 'Активен' : 'Неактивен'" :severity="data.state === 'active' ? 'success' : 'secondary'" />
                  </template>
                </Column>
                <Column header="Действия" class="w-32">
                  <template #body="{ data }">
                    <Button
                      v-if="data.state === 'active'"
                      label="Отключить"
                      icon="pi pi-ban"
                      @click="removeOffer(stream.stream_id || stream.id, data.offer_id)"
                      severity="danger"
                      size="small"
                      outlined
                    />
                    <Button
                      v-else
                      label="Восстановить"
                      icon="pi pi-replay"
                      @click="restoreOffer(stream.stream_id || stream.id, data.offer_id)"
                      severity="secondary"
                      size="small"
                      outlined
                    />
                  </template>
                </Column>
              </DataTable>


            </div>
          </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
      
      <!-- Кнопка сохранения (единая для всей карточки) -->
      <p v-if="saveError" class="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{{ saveError }}</p>
      <div class="mt-6 flex justify-end">
        <Button :label="saving ? 'Сохранение…' : 'Сохранить изменения'" @click="saveAll" severity="success" :disabled="!hasChanges || saving" />
      </div>
    </div>
  </div>
  <div v-else class="p-6 text-center text-gray-500">Загрузка кампании...</div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useCampaignStore } from '../stores/campaigns'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Accordion from 'primevue/accordion'
import AccordionPanel from 'primevue/accordionpanel'
import AccordionHeader from 'primevue/accordionheader'
import AccordionContent from 'primevue/accordioncontent'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const route = useRoute()
const store = useCampaignStore()
const campaign = ref<any>(null)
const references = ref<any>({ domains: [], groups: [], traffic_sources: [] })
const draft = reactive({ name: '', state: 'active', domainId: '', groupId: '', trafficSourceId: '' })
const campaignChanged = computed(() => Boolean(campaign.value && (
  draft.name !== campaign.value.name ||
  draft.state !== campaign.value.state ||
  draft.domainId !== String(campaign.value.domain_id ?? '') ||
  draft.groupId !== String(campaign.value.group_id ?? '') ||
  draft.trafficSourceId !== String(campaign.value.traffic_source_id ?? '')
)))
const savingCampaign = ref(false)
const hasChanges = ref(false)
const saving = ref(false)
const saveError = ref('')

const fetchDetail = async () => {
  try {
    campaign.value = await store.getCampaignDetail(Number(route.params.id))
    draft.name = campaign.value.name || ''
    draft.state = campaign.value.state || 'disabled'
    draft.domainId = String(campaign.value.domain_id ?? '')
    draft.groupId = String(campaign.value.group_id ?? '')
    draft.trafficSourceId = String(campaign.value.traffic_source_id ?? '')
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

const describeFilters = (stream: any) => {
  const filters = stream.filters || []
  if (!filters.length) return 'Без дополнительных условий'
  return filters.map((filter: any) => `${filter.name}: ${(filter.payload || []).join(', ')}`).join('; ')
}

const findOffer = (streamId: number, offerId: number) => {
  const stream = campaign.value?.streams?.find((item: any) => (item.stream_id || item.id) === streamId)
  return stream?.offers?.find((offer: any) => offer.offer_id === offerId)
}

const removeOffer = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.state = 'disabled'
    hasChanges.value = true
  }
}

const restoreOffer = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.state = 'active'
    hasChanges.value = true
  }
}

const toggleOfferLock = (streamId: number, offerId: number) => {
  const offer = findOffer(streamId, offerId)
  if (offer) {
    offer.share_locked = !offer.share_locked
    hasChanges.value = true
  }
}

const saveAll = async () => {
  if (!campaign.value || saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    for (const stream of campaign.value.streams || []) {
      if (stream.type !== 'default') continue
      await store.updateStreamOffers(campaign.value.campaign_id, stream.stream_id || stream.id, {
        offers: (stream.offers || []).map((offer: any) => ({
          offer_id: offer.offer_id,
          share: Number(offer.share ?? 0),
          state: offer.state === 'disabled' ? 'disabled' : 'active',
          share_locked: Boolean(offer.share_locked)
        }))
      })
    }
    hasChanges.value = false
    await fetchDetail()
  } catch (error: any) {
    saveError.value = error?.response?.data?.detail || 'Не удалось сохранить изменения офферов.'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchDetail()
  store.fetchReferences().then(data => { references.value = data }).catch(() => {})
})
</script>
