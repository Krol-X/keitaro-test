// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, fireEvent, cleanup } from '@testing-library/vue'
import CountrySelector from '../src/components/CountrySelector.vue'

const countries = [
  { code: 'BY', name: 'Belarus' },
  { code: 'PL', name: 'Poland' },
  { code: 'LT', name: 'Lithuania' }
]

afterEach(cleanup)

describe('CountrySelector', () => {
  it('emits the selected country codes when a country is toggled', async () => {
    const { getByLabelText, emitted } = render(CountrySelector, {
      props: { modelValue: ['PL'], countries }
    })

    await fireEvent.click(getByLabelText(/\(BY\)/))

    expect(emitted()['update:modelValue'][0]).toEqual([['BY', 'PL']])
  })

  it('filters countries by ISO code', async () => {
    const { getByLabelText, queryByLabelText } = render(CountrySelector, {
      props: { modelValue: [], countries }
    })

    await fireEvent.update(getByLabelText('Поиск страны'), 'lt')

    expect(queryByLabelText(/\(LT\)/)).toBeTruthy()
    expect(queryByLabelText(/\(PL\)/)).toBeNull()
    expect(queryByLabelText(/\(BY\)/)).toBeNull()
  })
})
