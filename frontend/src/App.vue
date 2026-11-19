<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-white shadow-sm p-4 flex justify-between items-center">
      <h1 class="text-xl font-bold text-gray-800">Keitaro Campaign Panel</h1>
      <div class="flex gap-2">
        <Button label="Создать кампанию" @click="openCreateDialog" severity="success" />
      </div>
    </header>
    <main class="flex-1 p-6">
      <router-view />
    </main>
    <CampaignCreateDialog v-model:visible="showCreateDialog" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import CampaignCreateDialog from './components/CampaignCreateDialog.vue'

const showCreateDialog = ref(false)
const openCreateDialog = () => {
  showCreateDialog.value = true
}
</script>
