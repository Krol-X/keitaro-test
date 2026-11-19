// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../src/App.vue'

const storeActions = vi.hoisted(() => ({
  fetchReferences: vi.fn(async () => ({
    domains: [], groups: [], traffic_sources: [], countries: [], defaults: {}
  })),
  fetchOffers: vi.fn(async () => [])
}))

vi.mock('../src/stores/campaigns', () => ({
  useCampaignStore: () => storeActions
}))

describe('App campaign creation', () => {
  it('opens the create-campaign form from the header button', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }]
    })
    await router.push('/')
    await router.isReady()

    const { getByRole, findByRole } = render(App, {
      global: {
        plugins: [router],
        stubs: {
          'router-view': true,
          Button: {
            props: ['label'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')">{{ label }}</button>'
          }
        }
      }
    })

    await fireEvent.click(getByRole('button', { name: 'Создать кампанию' }))
    expect(await findByRole('dialog')).toBeTruthy()
    expect(storeActions.fetchReferences).toHaveBeenCalledOnce()
    expect(storeActions.fetchOffers).toHaveBeenCalledOnce()
  })
})
