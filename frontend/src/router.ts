import { createRouter, createWebHistory } from 'vue-router'
import CampaignsView from './views/CampaignsView.vue'
import CampaignDetailView from './views/CampaignDetailView.vue'

const routes = [
  {
    path: '/',
    name: 'Campaigns',
    component: CampaignsView
  },
  {
    path: '/campaigns/:id',
    name: 'CampaignDetail',
    component: CampaignDetailView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
