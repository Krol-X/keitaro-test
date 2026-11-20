// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fireEvent, render, cleanup } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CampaignsView from '../src/views/CampaignsView.vue'

const storeActions = vi.hoisted(() => ({
  campaigns: [],
  loading: false,
  error: null,
  hasMore: false,
  limit: 25,
  offset: 0,
  fetchCampaigns: vi.fn(async () => undefined),
  fetchReferences: vi.fn(async () => ({ domains: [], groups: [], traffic_sources: [], countries: [], defaults: {} })),
  fetchOffers: vi.fn(async () => [])
}))

vi.mock('../src/stores/campaigns', () => ({ useCampaignStore: () => storeActions }))

afterEach(cleanup)

const renderView = async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }]
  })
  await router.push('/')
  await router.isReady()
  return render(CampaignsView, { global: { plugins: [router] } })
}

describe('CampaignsView', () => {
  it('renders only the campaigns heading without marketing copy', async () => {
    const { getByRole, queryByText, container } = await renderView()

    expect(getByRole('heading', { name: 'Кампании' })).toBeTruthy()
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(queryByText('Управление трафиком')).toBeNull()
    expect(queryByText('Создавайте кампании и следите за их состоянием в одном месте.')).toBeNull()
  })

  it('opens the create-campaign dialog from the page button', async () => {
    const { getAllByRole, findByRole } = await renderView()

    // Кнопка есть и в заголовке страницы, и в пустом состоянии — обе открывают диалог.
    await fireEvent.click(getAllByRole('button', { name: 'Создать кампанию' })[0])

    expect(await findByRole('dialog')).toBeTruthy()
    expect(storeActions.fetchReferences).toHaveBeenCalledOnce()
  })
})
