<template>
  <div v-if="campaign" class="p-6 bg-white rounded-lg shadow-sm">
    <!-- Заголовок и настройки (единый стиль) -->
    <div class="flex justify-between items-start mb-6 border-b pb-4">
      <div>
        <h2 class="text-2xl font-bold text-gray-900">{{ campaign?.name || 'Загрузка...' }} (ID: {{ campaign?.campaign_id }})</h2>
        <div class="flex gap-2 mt-2">
          <Tag :value="campaign?.state" :severity="campaign?.state === 'active' ? 'success' : 'danger'" />
          <a :href="campaign?.campaign_url" target="_blank" class="text-blue-600 underline hover:text-blue-800 transition-colors">{{ campaign?.campaign_url }}</a>
        </div>
      </div>
      <Button label="Назад" @click="$router.back()" severity="secondary" outlined />
    </div>

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
        <AccordionPanel v-for="stream in campaign?.streams || []" :key="stream.stream_id" :value="String(stream.stream_id)" class="border-none shadow-sm">
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
                <div class="font-medium text-gray-700">{{ stream.condition_label || 'Сложное условие' }}</div>
              </div>
            </div>

            <!-- Редирект (для forced потока - Создаватор) -->
            <div v-if="stream.type === 'forced'" class="mb-4 p-3 bg-white border rounded">
              <div class="text-sm text-gray-500 uppercase mb-1">Редирект (Google)</div>
              <div class="font-mono bg-gray-100 p-2 rounded text-sm">{{ stream.redirect_url }}</div>
            </div>

            <!-- Офферы (для default потока - Редактор) -->
            <div v-if="stream.type === 'default' && stream.schema" class="mt-4">
              <div class="flex justify-between items-center mb-3">
                <h4 class="font-semibold text-gray-800">Офферы потока (Ревизия: {{ stream.revision }})</h4>
                <div class="flex gap-2">
                  <span v-if="!stream.can_edit_offers" class="text-sm text-gray-500 italic">{{ stream.edit_disabled_reason }}</span>
                  <Button v-if="stream.can_edit_offers" label="Редактировать" @click="openEditDialog(stream)" size="small" severity="primary" />
                </div>
              </div>
              
              <!-- Таблица активных офферов -->
              <DataTable :value="stream.offers.filter(o => o.state === 'active')" class="mt-2" :showGridlines="true">
                <Column field="offer_id" header="ID" class="w-20" />
                <Column field="name" header="Название" />
                <Column field="share" header="Доля (%)" class="w-20 text-center" />
                <Column field="state" header="Состояние">
                  <template #body="{ data }">
                    <Tag :value="data.state" :severity="data.state === 'active' ? 'success' : 'warning'" />
                  </template>
                </Column>
                <Column header="Действия" class="w-32">
                  <template #body="{ data }">
                    <Button icon="pi pi-trash" @click="removeOffer(stream.stream_id, data.offer_id)" severity="danger" size="small" outlined />
                  </template>
                </Column>
              </DataTable>

              <!-- Список архивных/удалённых (согласно видео - можно восстановить) -->
              <div v-if="stream.offers.some(o => o.state !== 'active')" class="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                <h5 class="text-sm font-bold text-yellow-800 mb-2">Архивные / Удалённые (можно восстановить)</h5>
                <div class="flex flex-wrap gap-2">
                  <Button 
                    v-for="o in stream.offers.filter(o => o.state !== 'active')" 
                    :key="o.offer_id"
                    :label="`Восстановить ${o.offer_id}`" 
                    @click="restoreOffer(stream.stream_id, o.offer_id)"
                    size="small"
                    class="bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-200"
                  />
                </div>
              </div>
            </div>
          </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
      
      <!-- Кнопка сохранения (единая для всей карточки) -->
      <div class="mt-6 flex justify-end">
        <Button label="Сохранить изменения" @click="saveAll" severity="success" :disabled="!hasChanges" />
      </div>
    </div>
  </div>
  <div v-else class="p-6 text-center text-gray-500">Загрузка кампании...</div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
const hasChanges = ref(false) // Локальный черновик

const fetchDetail = async () => {
  const id = route.params.id
  campaign.value = await store.getCampaignDetail(Number(id))
}

onMounted(fetchDetail)

// Логика «Редактора» (согласно видео и ТЗ п. 6)
const openEditDialog = (stream: any) => {
  console.log('Edit stream', stream.stream_id, 'Revision:', stream.revision)
  // В реальном приложении здесь открывается модальное окно с редактированием
}

const removeOffer = (streamId: number, offerId: number) => {
  // Логика «удаления» (пометка как архивный/удалённый локально)
  const stream = campaign.value.streams.find(s => s.stream_id === streamId)
  if (stream) {
    const offer = stream.offers.find(o => o.offer_id === offerId)
    if (offer) {
      offer.state = 'archived' // Помечаем как архивный (согласно видео)
      hasChanges.value = true
    }
  }
}

const restoreOffer = (streamId: number, offerId: number) => {
  // Логика «Восстановления» (согласно видео)
  const stream = campaign.value.streams.find(s => s.stream_id === streamId)
  if (stream) {
    const offer = stream.offers.find(o => o.offer_id === offerId)
    if (offer) {
      offer.state = 'active' // Восстанавливаем
      hasChanges.value = true
    }
  }
}

const saveAll = async () => {
  // Логика «Сохранить» (п. 6 ТЗ: revision, distribution, offers)
  // Здесь отправляем запрос в бэкенд для каждого потока со схемой
  for (const stream of campaign.value.streams) {
    if (stream.type === 'default' && stream.schema) {
      const activeOffers = stream.offers.filter(o => o.state === 'active').map(o => ({ offer_id: o.offer_id }))
      // В реальном коде нужно передавать distribution и revision
      await store.updateStreamOffers(campaign.value.campaign_id, stream.stream_id, {
        revision: stream.revision,
        distribution: 'equal', // или 'explicit'
        offers: activeOffers
      })
      hasChanges.value = false
      fetchDetail() // Перечитать для получения новой ревизии
    }
  }
}
</script>
