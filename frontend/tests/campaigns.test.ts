import { describe, it, expect } from 'vitest'
import { mount } from '@testing-library/vue'
import { createTestingPinia } from '@pinia/testing'
import CampaignsView from '../views/CampaignsView.vue'

describe('CampaignsView', () => {
  it('renders campaigns list', async () => {
    const wrapper = mount(CampaignsView, {
      global: {
        plugins: [createTestingPinia()],
        stubs: ['DataTable', 'Column', 'InputText', 'Button', 'Spinner', 'Tag']
      }
    })
    expect(wrapper.find('h2').text()).toBe('Кампании')
  })
})
