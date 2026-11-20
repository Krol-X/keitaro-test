import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

export const useCampaignStore = defineStore('campaigns', {
  state: () => ({
    campaigns: [] as any[],
    loading: false,
    error: null as string | null,
    hasMore: false,
    limit: 25,
    offset: 0,
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
        this.hasMore = Boolean(res.data.has_more)
        this.limit = limit
        this.offset = offset
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
    async updateCampaign(id: number, data: any) {
      const res = await axios.put(`${API_BASE}/campaigns/${id}`, data)
      return res.data
    },
    async deleteCampaign(id: number) {
      await axios.delete(`${API_BASE}/campaigns/${id}`)
    },
    async restoreCampaign(id: number) {
      const res = await axios.post(`${API_BASE}/campaigns/${id}/restore`)
      return res.data
    },
    async updateCountryFilter(campaignId: number, excludedCountries: string[]) {
      const res = await axios.put(`${API_BASE}/campaigns/${campaignId}/country-filter`, {
        excluded_countries: excludedCountries
      })
      return res.data
    },
    async updateStreamOffers(campaignId: number, streamId: number, data: any) {
      const res = await axios.put(`${API_BASE}/campaigns/${campaignId}/streams/${streamId}/offers`, data)
      return res.data
    },
    async createStream(campaignId: number, data: any) {
      const res = await axios.post(`${API_BASE}/campaigns/${campaignId}/streams`, data)
      return res.data
    },
    async getOperation(id: string) {
      const res = await axios.get(`${API_BASE}/operations/${id}`)
      this.operations[id] = res.data
      return res.data
    }
  }
})
