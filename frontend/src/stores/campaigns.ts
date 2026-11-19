import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

export const useCampaignStore = defineStore('campaigns', {
  state: () => ({
    campaigns: [] as any[],
    loading: false,
    error: null,
    references: null as any,
    offers: [] as any[],
    operations: {} as Record<string, any>
  }),
  actions: {
    async fetchCampaigns(query?: string, limit = 25, offset = 0) {
      this.loading = true
      this.error = null
      try {
        const res = await axios.get(`${API_BASE}/campaigns`, { params: { query, limit, offset } })
        this.campaigns = res.data.items
      } catch (e: any) {
        this.error = e.response?.data?.detail || 'Ошибка загрузки'
      } finally {
        this.loading = false
      }
    },
    async fetchReferences() {
      const res = await axios.get(`${API_BASE}/references`)
      this.references = res.data
      return res.data
    },
    async fetchOffers(query?: string) {
      const res = await axios.get(`${API_BASE}/offers`, { params: { query } })
      this.offers = res.data.items
      return res.data.items
    },
    async createCampaign(data: any, idempotencyKey: string) {
      const res = await axios.post(`${API_BASE}/campaigns`, data, {
        headers: { 'Idempotency-Key': idempotencyKey }
      })
      return res.data
    },
    async getCampaignDetail(id: number) {
      const res = await axios.get(`${API_BASE}/campaigns/${id}`)
      return res.data
    },
    async updateStreamOffers(campaignId: number, streamId: number, data: any) {
      const res = await axios.put(`${API_BASE}/campaigns/${campaignId}/streams/${streamId}/offers`, data)
      return res.data
    },
    async getOperation(id: string) {
      const res = await axios.get(`${API_BASE}/operations/${id}`)
      this.operations[id] = res.data
      return res.data
    }
  }
})
