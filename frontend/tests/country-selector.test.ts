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

const checkboxes = (getAllByRole: (role: string) => HTMLElement[]) => getAllByRole('checkbox')
const codeOf = (checkbox: HTMLElement) => checkbox.closest('label')?.querySelector('.country-row-code')?.textContent?.trim()

describe('CountrySelector', () => {
  it('emits the selected country codes when a country is toggled', async () => {
    const { getAllByRole, emitted } = render(CountrySelector, {
      props: { modelValue: ['PL'], countries }
    })

    const byCheckbox = checkboxes(getAllByRole).find(node => codeOf(node) === 'BY') as HTMLElement
    await fireEvent.click(byCheckbox)

    expect(emitted()['update:modelValue'][0]).toEqual([['BY', 'PL']])
  })

  it('moves selected countries above the rest', async () => {
    const { getAllByRole } = render(CountrySelector, {
      props: { modelValue: ['PL'], countries }
    })

    expect(codeOf(checkboxes(getAllByRole)[0])).toBe('PL')
  })

  it('shows selected countries as removable chips', async () => {
    const { getAllByLabelText, emitted } = render(CountrySelector, {
      props: { modelValue: ['PL', 'LT'], countries }
    })

    const chips = getAllByLabelText(/^Убрать /)
    const polandChip = chips.find(chip => chip.textContent?.includes('PL'))
    await fireEvent.click(polandChip!)

    expect(emitted()['update:modelValue'][0]).toEqual([['LT']])
  })

  it('filters countries by ISO code', async () => {
    const { getByLabelText, getAllByRole } = render(CountrySelector, {
      props: { modelValue: [], countries }
    })

    await fireEvent.update(getByLabelText('Поиск страны'), 'lt')

    const remaining = checkboxes(getAllByRole).map(codeOf)
    expect(remaining).toEqual(['LT'])
  })

  it('selects only the countries matching the current search', async () => {
    const { getByLabelText, getByText, emitted } = render(CountrySelector, {
      props: { modelValue: [], countries }
    })

    // «пол» совпадает только с польским названием страны.
    await fireEvent.update(getByLabelText('Поиск страны'), 'пол')
    await fireEvent.click(getByText('Выбрать все'))

    expect(emitted()['update:modelValue'][0]).toEqual([['PL']])
  })
})
