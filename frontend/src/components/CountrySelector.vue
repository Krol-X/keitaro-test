<template>
  <div class="country-selector">
    <input
      v-model="search"
      type="search"
      class="country-search"
      :placeholder="placeholder"
      aria-label="Поиск страны"
    />

    <div v-if="selectedCountries.length" class="country-chips" aria-label="Выбранные страны">
      <button
        v-for="country in selectedCountries"
        :key="country.code"
        type="button"
        class="country-chip"
        :aria-label="`Убрать ${displayCountryName(country)} из выбранных`"
        :title="`Убрать ${displayCountryName(country)}`"
        @click="toggle(country.code)"
      >
        <span class="country-chip-code">{{ country.code }}</span>
        <span class="country-chip-name">{{ displayCountryName(country) }}</span>
        <i class="pi pi-times" aria-hidden="true"></i>
      </button>
      <button type="button" class="country-clear" @click="clear">Очистить</button>
    </div>

    <div class="country-meta">
      <span>Выбрано {{ selectedCountries.length }} из {{ countries.length }}</span>
      <button type="button" class="country-link" @click="selectVisible">Выбрать все</button>
    </div>

    <div class="country-list">
      <label
        v-for="country in visibleCountries"
        :key="country.code"
        class="country-row"
        :class="{ 'is-selected': isSelected(country.code) }"
      >
        <input
          type="checkbox"
          class="country-checkbox"
          :checked="isSelected(country.code)"
          @change="toggle(country.code)"
        />
        <span class="country-row-code">{{ country.code }}</span>
        <span class="country-row-name">{{ displayCountryName(country) }}</span>
        <i v-if="isSelected(country.code)" class="pi pi-check country-row-check" aria-hidden="true"></i>
      </label>
      <p v-if="visibleCountries.length === 0" class="country-empty">Страны не найдены.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface Country { code: string; name: string }

const props = withDefaults(defineProps<{ modelValue: string[]; countries: Country[]; placeholder?: string }>(), {
  placeholder: 'Найти страну или код, например BY'
})
const emit = defineEmits<{ (event: 'update:modelValue', value: string[]): void }>()

const search = ref('')
const countryNames = new Intl.DisplayNames(['ru'], { type: 'region' })
const displayCountryName = (country: Country) => countryNames.of(country.code) || country.name
const byCode = computed(() => new Map(props.countries.map(country => [country.code, country])))
const isSelected = (code: string) => props.modelValue.includes(code)

const selectedCountries = computed(() =>
  props.countries
    .filter(country => isSelected(country.code))
    .sort((left, right) => displayCountryName(left).localeCompare(displayCountryName(right), 'ru'))
)

const visibleCountries = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return props.countries
    .filter(country =>
      !query ||
      displayCountryName(country).toLocaleLowerCase().includes(query) ||
      country.name.toLocaleLowerCase().includes(query) ||
      country.code.toLowerCase().includes(query)
    )
    // Выбранные страны — всегда сверху, остальные по алфавиту.
    .sort((left, right) =>
      Number(isSelected(right.code)) - Number(isSelected(left.code)) ||
      displayCountryName(left).localeCompare(displayCountryName(right), 'ru')
    )
})

const emitSelection = (codes: string[]) => emit('update:modelValue', [...new Set(codes)].sort())

const toggle = (code: string) => {
  emitSelection(isSelected(code)
    ? props.modelValue.filter(item => item !== code)
    : [...props.modelValue, code])
}
const clear = () => emitSelection([])

// «Выбрать все» учитывает активный поиск, чтобы не выбрать весь список из-за пустого запроса.
const selectVisible = () => emitSelection([
  ...props.modelValue,
  ...visibleCountries.value.map(country => country.code)
])
</script>
