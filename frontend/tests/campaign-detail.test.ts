// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, cleanup, waitFor } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import CampaignDetailView from '../src/views/CampaignDetailView.vue'

const store = vi.hoisted(() => ({
  offers: [] as any[],
  getCampaignDetail: vi.fn(),
  fetchReferences: vi.fn(async () => ({ domains: [], groups: [], traffic_sources: [], countries: [{ code: 'BY', name: 'Belarus' }, { code: 'PL', name: 'Poland' }] })),
  fetchOffers: vi.fn(async () => store.offers),
  fetchCampaigns: vi.fn(async () => undefined),
  updateCampaign: vi.fn(async () => ({})),
  updateStreamOffers: vi.fn(async () => ({})),
  createStream: vi.fn(async () => ({})),
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

  it('saves only the flows whose offers changed', async () => {
    const fixture = structuredClone(campaignFixture)
    // Второй поток с офферами, чтобы проверить, что лишний PUT не уходит.
    fixture.streams.push({
      stream_id: 203, id: 203, position: 3, name: 'Второй', type: 'regular', schema: 'landings', state: 'active',
      offers: [{ offer_id: 11, name: 'Offer 11', share: 100, state: 'active', share_locked: false }]
    })
    store.getCampaignDetail.mockResolvedValue(fixture)

    const { findAllByLabelText, findByRole } = await renderView()

    const shares = await findAllByLabelText(/в процентах$/)
    await fireEvent.update(shares[0], '40')

    await fireEvent.click(await findByRole('button', { name: 'Сохранить офферы' }))

    expect(store.updateStreamOffers).toHaveBeenCalledTimes(1)
    expect(store.updateStreamOffers.mock.calls[0][1]).toBe(202)
  })

  it('refuses to save a flow where every offer was disabled', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findByRole, findAllByText, findByText } = await renderView()

    const disableButtons = await findAllByText('Отключить')
    await fireEvent.click(disableButtons[0])
    await fireEvent.click(await findByRole('button', { name: 'Сохранить офферы' }))

    expect(store.updateStreamOffers).not.toHaveBeenCalled()
    expect(await findByText(/должен остаться хотя бы один активный оффер/)).toBeTruthy()
  })

  it('shows the backend error when Keitaro drops the flow', async () => {
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))
    store.updateStreamOffers.mockRejectedValueOnce({
      response: { data: { detail: 'Keitaro no longer returns flow 202 after the update; open the campaign in Keitaro' } }
    })

    const { findByRole, findAllByLabelText, findByText } = await renderView()

    const shares = await findAllByLabelText(/в процентах$/)
    await fireEvent.update(shares[0], '40')
    await fireEvent.click(await findByRole('button', { name: 'Сохранить офферы' }))

    expect(await findByText(/no longer returns flow 202/)).toBeTruthy()
  })

  it('lists offers for adding without requiring a search first', async () => {
    store.offers = [{ offer_id: 11, name: 'Alpha' }, { offer_id: 22, name: 'Beta' }]
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { container, findByRole, findAllByText } = await renderView()

    await findAllByText('Потоки и офферы')
    const select = container.querySelector('[aria-label="Оффер для добавления"]') as HTMLSelectElement
    await waitFor(() => expect(select.querySelectorAll('option').length).toBeGreaterThan(2))

    const labels = [...select.options].map(option => option.textContent)
    expect(labels).toContain('Alpha (ID: 11)')
    expect(labels).toContain('Beta (ID: 22)')
    store.offers = []
  })

  it('filters the offer list locally and adds the chosen offer', async () => {
    store.offers = [{ offer_id: 11, name: 'Alpha' }, { offer_id: 22, name: 'Beta' }]
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { container, findByLabelText, findByRole, findAllByText } = await renderView()

    await findAllByText('Потоки и офферы')
    await findByLabelText('Поиск офферов для добавления')
    const search = await findByLabelText('Поиск офферов для добавления')
    await fireEvent.update(search, 'beta')

    const select = container.querySelector('[aria-label="Оффер для добавления"]') as HTMLSelectElement
    await waitFor(() => expect([...select.options].map(option => option.value)).toContain('22'))
    expect([...select.options].map(option => option.value)).not.toContain('11')

    await fireEvent.update(select, '22')
    await fireEvent.click(await findByRole('button', { name: 'Добавить' }))

    expect(container.querySelectorAll('.offers-table tbody tr')).toHaveLength(2)
    store.offers = []
  })

  it('offers a way to create a landings flow when only the redirect flow is left', async () => {
    const fixture = structuredClone(campaignFixture)
    // Пользователь остался только с перехватывающим потоком: некуда девать остальной трафик.
    fixture.streams = [fixture.streams[0]]
    store.offers = [{ offer_id: 11, name: 'Alpha' }, { offer_id: 22, name: 'Beta' }]
    store.getCampaignDetail.mockResolvedValue(fixture)

    const { findByText, findByRole, container } = await renderView()

    expect(await findByText('В кампании нет потока с офферами')).toBeTruthy()
    await fireEvent.click(await findByRole('button', { name: /Добавить поток с офферами/ }))

    await fireEvent.update(container.querySelector('.stream-create-grid input') as HTMLInputElement, 'Основной поток')
    await fireEvent.click(container.querySelectorAll('.stream-create-offer input')[0])
    await fireEvent.click(await findByRole('button', { name: 'Создать поток' }))

    await waitFor(() => expect(store.createStream).toHaveBeenCalledTimes(1))
    expect(store.createStream.mock.calls[0][0]).toBe(50)
    expect(store.createStream.mock.calls[0][1]).toEqual({
      name: 'Основной поток',
      type: 'regular',
      offer_ids: [11]
    })
    store.offers = []
  })

  it('keeps the create button disabled until at least one offer is picked', async () => {
    const fixture = structuredClone(campaignFixture)
    fixture.streams = [fixture.streams[0]]
    store.offers = [{ offer_id: 11, name: 'Alpha' }]
    store.getCampaignDetail.mockResolvedValue(fixture)

    const { findByRole, container } = await renderView()

    await fireEvent.click(await findByRole('button', { name: /Добавить поток с офферами/ }))
    const submit = (await findByRole('button', { name: 'Создать поток' })) as HTMLButtonElement
    expect(submit.disabled).toBe(true)

    await fireEvent.click(container.querySelector('.stream-create-offer input') as HTMLInputElement)
    expect((await findByRole('button', { name: 'Создать поток' }) as HTMLButtonElement).disabled).toBe(false)
    store.offers = []
  })

  it('does not ask for a new flow when a landings flow already exists', async () => {
    store.offers = []
    store.getCampaignDetail.mockResolvedValue(structuredClone(campaignFixture))

    const { findAllByText, queryByText } = await renderView()

    await findAllByText('Потоки и офферы')
    expect(queryByText('В кампании нет потока с офферами')).toBeNull()
  })
})
