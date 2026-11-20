<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <router-link to="/" class="brand-lockup" aria-label="Keitaro Campaign Panel — главная">
        <span class="brand-mark"><i class="pi pi-chart-line" aria-hidden="true"></i></span>
        <span><strong>Keitaro</strong><small>Campaign panel</small></span>
      </router-link>
      <nav class="side-nav" aria-label="Основная навигация">
        <router-link to="/" class="side-nav-link">
          <i class="pi pi-folder" aria-hidden="true"></i><span>Кампании</span>
        </router-link>
      </nav>
      <p class="side-footer">Данные кампаний и потоков синхронизируются с Keitaro.</p>
    </aside>
    <div class="app-main">
      <header class="app-header">
        <span class="workspace-label"><span class="workspace-dot"></span>Рабочее пространство</span>
        <Button label="Создать кампанию" icon="pi pi-plus" @click="openCreateDialog" severity="success" />
      </header>
      <main class="app-content">
        <router-view />
      </main>
    </div>
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
