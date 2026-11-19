<template>
  <section class="page-shell">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Управление трафиком</p>
        <h1>Кампании</h1>
        <p class="page-description">Создавайте кампании и следите за их состоянием в одном месте.</p>
      </div>
      <button class="button button-primary" type="button" @click="openCreate">
        <i class="pi pi-plus" aria-hidden="true"></i><span>Создать кампанию</span>
      </button>
    </div>

    <div class="list-toolbar">
      <form class="search-form" @submit.prevent="search">
        <label class="search-box">
          <i class="pi pi-search" aria-hidden="true"></i>
          <input v-model.trim="query" type="search" placeholder="Поиск по названию или ID" aria-label="Поиск кампаний" />
          <button v-if="query" class="clear-search" type="button" aria-label="Очистить поиск" @click="query = ''; search()">×</button>
        </label>
        <button class="button button-secondary" type="submit">Найти</button>
      </form>
      <span class="result-count">{{ store.campaigns.length }} на этой странице</span>
    </div>

    <div v-if="store.error" class="notice notice-error" role="alert">
      <i class="pi pi-exclamation-circle" aria-hidden="true"></i>
      <span>{{ store.error }}</span>
      <button class="button button-quiet" type="button" @click="loadPage(store.offset)">Повторить</button>
    </div>

    <div v-if="store.loading" class="loading-panel" role="status">
      <span class="loader" aria-hidden="true"></span><span>Загружаем кампании…</span>
    </div>
    <div v-else-if="!store.error && store.campaigns.length === 0" class="empty-state">
      <span class="empty-icon"><i class="pi pi-folder-open" aria-hidden="true"></i></span>
      <h2>{{ query ? 'Ничего не найдено' : 'Пока нет кампаний' }}</h2>
      <p>{{ query ? 'Попробуйте изменить запрос или очистить поиск.' : 'Создайте первую кампанию, чтобы начать работу.' }}</p>
      <button v-if="!query" class="button button-primary" type="button" @click="openCreate">Создать кампанию</button>
    </div>
    <div v-else-if="!store.error" class="campaign-list" aria-label="Список кампаний">
      <article v-for="campaign in store.campaigns" :key="campaign.campaign_id" class="campaign-card">
        <div class="campaign-main">
          <div class="campaign-title-row">
            <span class="campaign-id">#{{ campaign.campaign_id }}</span>
            <h2>{{ campaign.name }}</h2>
          </div>
          <div class="campaign-meta">
            <span><i class="pi pi-folder" aria-hidden="true"></i>{{ campaign.group_name || 'Без группы' }}</span>
            <span><i class="pi pi-send" aria-hidden="true"></i>{{ campaign.traffic_source_name || 'Источник не указан' }}</span>
          </div>
        </div>
        <div class="campaign-actions">
          <span class="status-pill" :class="campaign.state === 'active' ? 'status-active' : 'status-disabled'">
            <span class="status-dot"></span>{{ stateLabel(campaign.state) }}
          </span>
          <button class="button button-secondary button-small" type="button" @click="goToDetail(campaign.campaign_id)">
            <i class="pi pi-eye" aria-hidden="true"></i><span>Открыть</span>
          </button>
          <button class="button button-danger-quiet button-small" type="button" :disabled="deletingId === campaign.campaign_id" :aria-label="`Удалить кампанию ${campaign.name}`" @click="removeCampaign(campaign)">
            <i :class="deletingId === campaign.campaign_id ? 'pi pi-spin pi-spinner' : 'pi pi-trash'" aria-hidden="true"></i><span class="delete-label">Удалить</span>
          </button>
        </div>
      </article>
    </div>

    <div v-if="!store.loading && (store.offset > 0 || store.hasMore)" class="pagination-bar">
      <span>Страница {{ Math.floor(store.offset / store.limit) + 1 }}</span>
      <div class="pagination-actions">
        <button class="button button-secondary button-small" type="button" :disabled="store.offset === 0 || store.loading" @click="loadPage(Math.max(0, store.offset - store.limit))">Назад</button>
        <button class="button button-secondary button-small" type="button" :disabled="!store.hasMore || store.loading" @click="loadPage(store.offset + store.limit)">Дальше</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaigns'

const store = useCampaignStore()
const router = useRouter()
const query = ref('')
const deletingId = ref<number | null>(null)

const loadPage = (offset = 0) => store.fetchCampaigns(query.value, 25, offset)
const search = () => loadPage(0)
const goToDetail = (id: number) => router.push(`/campaigns/${id}`)
const stateLabel = (state: string) => state === 'active' ? 'Активна' : 'Выключена'
const openCreate = () => window.dispatchEvent(new CustomEvent('campaign:create'))

const removeCampaign = async (campaign: any) => {
  if (!window.confirm(`Удалить кампанию «${campaign.name}» (ID: ${campaign.campaign_id})? Это действие нельзя отменить.`)) return
  deletingId.value = campaign.campaign_id
  try {
    await store.deleteCampaign(campaign.campaign_id)
    await loadPage(store.offset)
    if (store.campaigns.length === 0 && store.offset > 0) await loadPage(Math.max(0, store.offset - store.limit))
  } catch (error: any) {
    store.error = error?.response?.data?.detail || 'Не удалось удалить кампанию.'
  } finally {
    deletingId.value = null
  }
}

onMounted(() => loadPage())
</script>
