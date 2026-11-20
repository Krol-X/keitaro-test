// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, cleanup } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CampaignDetailView from '../src/views/CampaignDetailView.vue'

const store = vi.hoisted(() => ({
  offers: [] as any[],
  getCampaignDetail: vi.fn(),
  fetchReferences: vi.fn(async () => ({ domains: [], groups: [], traffic_sources: [], countries: [{ code: 'BY', name: 'Belarus' }, { code: 'PL', name: 'Poland' }] })),
  fetchOffers: vi.fn(async () => []),
  fetchCampaigns: vi.fn(async () => undefined),
  updateCampaign: vi.fn(async () => ({})),
  updateStreamOffers: vi.fn(async () => ({})),
  updateCountryFilter: vi.fn(async () => ({}))
}))

vi.mock('../src/stores/campaigns', () => ({ useCampaignStore: () => store }))

const campaignFixture = {
  campaign_id: 50,
  name: 'Летняя акция',
  state: 'active',
  campaign_url: 'https://go.example.com/c/abc',
  domain_id: 1,
  group_id: 2,
  traffic_source_id: 3,
  streams: [
    {
      stream_id: 201, id: 201, position: 1, name: 'Google редирект', type: 'forced', state: 'active',
      action_payload: 'https://www.google.com/',
      filters: [{ name: 'country', mode: 'accept', payload: ['PL', 'LT'] }],
      country_filter: { name: 'country', mode: 'accept', countries: ['LT', 'PL'] }
    },
    {
      stream_id: 202, id: 202, position: 2, name: 'Default Stream', type: 'default', state: 'active',
      offers: [{ offer_id: 8, name: 'Binomo', share: 60, state: 'active', share_locked: true }]
    }
  ]
}

const renderView = async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/campaigns/:id', component: CampaignDetailView }, { path: '/', component: { template: '<div />' } }]
  })
  await router.push('/campaigns/50')
  await router.isReady()
  return render(CampaignDetailView, { global: { plugins: [router] } })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CampaignDetailView layout', () => {
  it('renders a single settings panel without duplicate summary tiles', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findByRole, queryAllByText, getByRole } = await renderView()

    expect(await findByRole('heading', { name: 'Настройки кампании' })).toBeTruthy()
    expect(getByRole('heading', { name: 'Потоки и офферы' })).toBeTruthy()
    expect(getByRole('heading', { name: 'Фильтрация стран' })).toBeTruthy()
    // Раньше домен/группа/источник дублировались в трёх серых карточках под формой.
    expect(queryAllByText('ID: 1')).toHaveLength(0)
  })

  it('shows offer controls for a regular flow, not only for the catch-all one', async () => {
    const fixture = structuredClone(campaignFixture)
    // Keitaro отдаёт второй поток как regular с schema landings, если его создали не мы.
    fixture.streams[1].type = 'regular'
    fixture.streams[1].schema = 'landings'
    store.getCampaignDetail.mockResolvedValue(fixture)

    const { findByRole, getByRole, getByText, getByLabelText } = await renderView()

    await findByRole('heading', { name: 'Потоки и офферы' })
    expect(getByText('Обычный')).toBeTruthy()
    expect(getByLabelText('Поиск офферов для добавления')).toBeTruthy()
    expect(getByRole('button', { name: 'Добавить' })).toBeTruthy()
  })

  it('shows one save action per section', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findByRole, getByRole } = await renderView()

    await findByRole('heading', { name: 'Настройки кампании' })
    expect(getByRole('button', { name: 'Сохранить' })).toBeTruthy()
    expect(getByRole('button', { name: 'Сохранить офферы' })).toBeTruthy()
    expect(getByRole('button', { name: 'Сохранить страны' })).toBeTruthy()
  })

  it('renders locked offer share as a disabled input', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findByLabelText } = await renderView()

    const input = (await findByLabelText('Доля оффера 8 в процентах')) as HTMLInputElement
    expect(input.value).toBe('60')
    expect(input.disabled).toBe(true)
  })

  it('saves the country filter only when the selection changes', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findByRole, getByRole, container } = await renderView()

    const saveButton = (await findByRole('button', { name: 'Сохранить страны' })) as HTMLButtonElement
    expect(saveButton.disabled).toBe(true)

    const checkbox = container.querySelector('.country-checkbox') as HTMLInputElement
    await fireEvent.click(checkbox)
    expect((getByRole('button', { name: 'Сохранить страны' }) as HTMLButtonElement).disabled).toBe(false)
  })
})
