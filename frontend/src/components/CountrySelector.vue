<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <span class="text-xs text-gray-500">Выбрано: {{ modelValue.length }} из {{ countries.length }}</span>
      <div class="flex gap-3 text-sm">
        <button type="button" class="text-blue-700 hover:underline" @click="selectAll">Выбрать все</button>
        <button type="button" class="text-blue-700 hover:underline" @click="clear">Снять выбор</button>
      </div>
    </div>
    <input
      v-model="search"
      type="search"
      class="mt-2 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
      :placeholder="placeholder"
      aria-label="Поиск страны"
    />
    <div class="mt-2 max-h-48 overflow-y-auto rounded-md border border-gray-200 p-3">
      <div class="grid gap-x-4 gap-y-2 sm:grid-cols-2">
        <label v-for="country in filteredCountries" :key="country.code" class="inline-flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            class="rounded border-gray-300"
            :checked="modelValue.includes(country.code)"
            @change="toggle(country.code)"
          />
          {{ displayCountryName(country) }} ({{ country.code }})
        </label>
      </div>
      <p v-if="filteredCountries.length === 0" class="text-sm text-gray-500">Страны не найдены.</p>
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
const filteredCountries = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return [...props.countries]
    .filter(country =>
      !query ||
      displayCountryName(country).toLocaleLowerCase().includes(query) ||
      country.name.toLocaleLowerCase().includes(query) ||
      country.code.toLowerCase().includes(query)
    )
    .sort((left, right) => displayCountryName(left).localeCompare(displayCountryName(right), 'ru'))
})

const toggle = (code: string) => {
  const next = props.modelValue.includes(code)
    ? props.modelValue.filter(item => item !== code)
    : [...props.modelValue, code]
  emit('update:modelValue', [...next].sort())
}
const selectAll = () => emit('update:modelValue', props.countries.map(country => country.code).sort())
const clear = () => emit('update:modelValue', [])
</script>
