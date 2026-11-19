// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CampaignsView from '../src/views/CampaignsView.vue'

vi.mock('../src/stores/campaigns', () => ({
  useCampaignStore: () => ({
    campaigns: [],
    loading: false,
    error: null,
    fetchCampaigns: vi.fn()
  })
}))

describe('CampaignsView', () => {
  it('renders the campaigns list heading', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }]
    })
    await router.push('/')
    await router.isReady()

    const { getByRole } = render(CampaignsView, {
      global: {
        plugins: [router],
        stubs: ['DataTable', 'Column', 'InputText', 'Button', 'Tag']
      }
    })

    expect(getByRole('heading', { name: 'Кампании' })).toBeTruthy()
  })
})
