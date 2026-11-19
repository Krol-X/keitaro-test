<template>
  <div class="p-6 bg-white rounded-lg shadow-sm">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-lg font-semibold">Кампании</h2>
      <div class="flex gap-2">
        <InputText v-model="query" placeholder="Поиск по ID или названию" class="w-64" @keyup.enter="fetch" />
        <Button label="Поиск" @click="fetch" />
      </div>
    </div>

    <div v-if="store.loading" class="flex justify-center p-8">
      <i class="pi pi-spin pi-spinner text-2xl"></i>
    </div>

    <div v-else-if="store.error" class="p-4 bg-red-50 text-red-700 rounded">
      {{ store.error }}
    </div>

    <DataTable :value="store.campaigns" :paginator="true" :rows="25" :rowsPerPageOptions="[25, 50, 100]" class="mt-4">
      <Column field="campaign_id" header="ID" :sortable="true" />
      <Column field="name" header="Название" :sortable="true" />
      <Column field="group_name" header="Группа" />
      <Column field="traffic_source_name" header="Источник" />
      <Column field="state" header="Состояние">
        <template #body="{ data }">
          <Tag :value="data.state" :severity="data.state === 'active' ? 'success' : 'danger'" />
        </template>
      </Column>
      <Column header="Действия">
        <template #body="{ data }">
          <Button label="Открыть" @click="goToDetail(data.campaign_id)" size="small" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaigns'
import { DataTable, Column } from 'primevue/datatable'
import { InputText } from 'primevue/inputtext'
import { Button } from 'primevue/button'
import { Tag } from 'primevue/tag'

const store = useCampaignStore()
const router = useRouter()
const query = ref('')

const fetch = () => store.fetchCampaigns(query.value)
const goToDetail = (id: number) => router.push(`/campaigns/${id}`)

onMounted(() => fetch())
</script>
