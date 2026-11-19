<template>
  <div class="app-frame">
    <header class="app-header">
      <router-link to="/" class="brand-lockup" aria-label="Keitaro Campaign Panel — главная">
        <span class="brand-mark"><i class="pi pi-chart-line" aria-hidden="true"></i></span>
        <span><strong>Keitaro</strong><small>Campaign panel</small></span>
      </router-link>
      <div class="header-actions">
        <span class="workspace-label"><span class="workspace-dot"></span>Рабочее пространство</span>
        <Button label="Создать кампанию" icon="pi pi-plus" @click="openCreateDialog" severity="success" />
      </div>
    </header>
    <main class="app-content">
      <router-view />
    </main>
    <CampaignCreateDialog v-model:visible="showCreateDialog" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import CampaignCreateDialog from './components/CampaignCreateDialog.vue'

const showCreateDialog = ref(false)
const openCreateDialog = () => { showCreateDialog.value = true }
onMounted(() => window.addEventListener('campaign:create', openCreateDialog))
onBeforeUnmount(() => window.removeEventListener('campaign:create', openCreateDialog))
</script>
