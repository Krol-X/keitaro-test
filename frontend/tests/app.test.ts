// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../src/App.vue'

afterEach(cleanup)

describe('App shell', () => {
  it('renders the sidebar and no duplicate top bar', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }]
    })
    await router.push('/')
    await router.isReady()

    const { container, queryByText } = render(App, {
      global: {
        plugins: [router],
        stubs: { 'router-view': true }
      }
    })

    expect(container.querySelector('header')).toBeNull()
    expect(queryByText('Рабочее пространство')).toBeNull()
    expect(container.querySelector('.app-sidebar')).toBeTruthy()
  })
})
