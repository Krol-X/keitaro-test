// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, fireEvent, cleanup, waitFor } from '@testing-library/vue'
import CampaignCreateDialog from '../src/components/CampaignCreateDialog.vue'

const store = vi.hoisted(() => ({
  references: null as any,
  campaigns: [] as any[],
  fetchReferences: vi.fn(async () => ({
    domains: [{ id: 1, name: 'example.com' }],
    groups: [{ id: 2, name: 'Основная' }],
    traffic_sources: [{ id: 3, name: 'Facebook' }],
    countries: [{ code: 'PL', name: 'Poland' }],
    defaults: { domain_id: 1, group_id: 2, traffic_source_id: 3 }
  })),
  fetchOffers: vi.fn(async () => [{ offer_id: 8, name: 'Binomo' }]),
  fetchCampaigns: vi.fn(async () => undefined),
  createCampaign: vi.fn(async (): Promise<any> => ({ campaign_id: 55 })),
  restoreCampaign: vi.fn(async () => ({}))
}))

vi.mock('../src/stores/campaigns', () => ({ useCampaignStore: () => store }))

const axiosGet = vi.hoisted(() => vi.fn(async () => ({ data: [] })))
vi.mock('axios', () => ({ default: { get: axiosGet } }))

const CONFLICT = {
  response: {
    status: 409,
    data: {
      detail: {
        code: 'NAME_IN_ARCHIVE',
        message: 'Кампания с названием «Летняя акция» уже есть в архиве Keitaro.',
        name: 'Летняя акция',
        archived_campaigns: [{ campaign_id: 77, name: 'Летняя акция', state: 'deleted' }]
      }
    }
  }
}

afterEach(() => {
  sessionStorage.clear()
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  store.campaigns = []
  axiosGet.mockResolvedValue({ data: [] })
})

const renderDialog = async () => {
  const utils = render(CampaignCreateDialog, { props: { visible: true } })
  const nameInput = (await utils.findByLabelText('Название кампании')) as HTMLInputElement
  const offerSelect = (await utils.findByLabelText('Оффер')) as HTMLSelectElement
  await fireEvent.update(nameInput, 'Летняя акция')
  await fireEvent.update(offerSelect, '8')
  return { ...utils, nameInput }
}

describe('CampaignCreateDialog archive conflict', () => {
  it('offers to restore or rename when the name is reserved by an archived campaign', async () => {
    store.createCampaign.mockRejectedValueOnce(CONFLICT)
    axiosGet.mockResolvedValue({ data: [{ id: 77, name: 'Летняя акция' }, { id: 78, name: 'Летняя акция (2)' }] })

    const { findByText, findByRole, nameInput } = await renderDialog()

    await fireEvent.click(await findByRole('button', { name: 'Создать' }))

    expect(await findByText('Название занято кампанией в архиве')).toBeTruthy()
    expect(await findByText(/#77 · Летняя акция/)).toBeTruthy()

    // (2) уже занято — подставляется следующий свободный вариант.
    const rename = await findByRole('button', { name: 'Создать под названием «Летняя акция (3)»' })
    await fireEvent.click(rename)

    expect(nameInput.value).toBe('Летняя акция (3)')
    // Подсказка закрывается, как только имя изменено.
    await waitFor(() => expect(document.body.textContent).not.toContain('Название занято кампанией в архиве'))
  })

  it('restores the archived campaign instead of creating a duplicate', async () => {
    store.createCampaign.mockRejectedValueOnce(CONFLICT)
    const { findByRole } = await renderDialog()

    await fireEvent.click(await findByRole('button', { name: 'Создать' }))
    await fireEvent.click(await findByRole('button', { name: 'Восстановить' }))

    await waitFor(() => expect(store.restoreCampaign).toHaveBeenCalledWith(77))
    expect(store.fetchCampaigns).toHaveBeenCalled()
  })

  it('uses a fresh idempotency key after the name conflict', async () => {
    store.createCampaign.mockRejectedValueOnce(CONFLICT)
    const { findByRole } = await renderDialog()

    await fireEvent.click(await findByRole('button', { name: 'Создать' }))
    await findByRole('button', { name: 'Восстановить' })
    await fireEvent.click(await findByRole('button', { name: 'Создать под названием «Летняя акция (2)»' }))
    await fireEvent.click(await findByRole('button', { name: 'Создать' }))

    await waitFor(() => expect(store.createCampaign).toHaveBeenCalledTimes(2))
    const [firstKey, secondKey] = store.createCampaign.mock.calls.map((call: any[]) => call[1])
    expect(secondKey).not.toBe(firstKey)
  })

  it('keeps a plain error message for other upstream failures', async () => {
    store.createCampaign.mockRejectedValueOnce({ response: { status: 502, data: { detail: 'Keitaro error: boom' } } })

    const { findByRole, findByText, queryByText } = await renderDialog()

    await fireEvent.click(await findByRole('button', { name: 'Создать' }))

    expect(await findByText('Keitaro error: boom')).toBeTruthy()
    expect(queryByText('Название занято кампанией в архиве')).toBeNull()
  })
})


it('rechecks the same submission after a lost response and reload until success is confirmed', async () => {
  store.createCampaign.mockRejectedValueOnce(new Error('connection lost'))
    .mockResolvedValueOnce({ operation_id: 'op-1', stage: 'enabling', status: 'running' })
  const dialog = await renderDialog()
  await fireEvent.click(await dialog.findByRole('button', { name: 'Создать' }))
  await dialog.findByText('Не удалось подтвердить создание кампании.')
  dialog.unmount()
  const resumed = render(CampaignCreateDialog, { props: { visible: true } })
  const check = await resumed.findByRole('button', { name: 'Проверить результат' })
  await fireEvent.click(check)
  expect(await resumed.findByText(/Ещё выполняется/)).toBeTruthy()
  expect(store.fetchCampaigns).not.toHaveBeenCalled()
  expect(resumed.emitted()['update:visible']).toBeUndefined()
  await fireEvent.click(check)
  await waitFor(() => expect(resumed.emitted()['update:visible']).toEqual([[false]]))
  const calls = store.createCampaign.mock.calls
  expect(calls).toHaveLength(3)
  expect(calls[1]).toEqual(calls[0])
  expect(calls[2]).toEqual(calls[0])
})
