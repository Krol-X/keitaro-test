<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="bg-white shadow-sm p-4 flex justify-between items-center">
      <h1 class="text-xl font-bold text-gray-800">Keitaro Campaign Panel</h1>
      <div class="flex gap-2">
        <Button label="Создать кампанию" @click="showCreateDialog" severity="success" />
      </div>
    </header>
    <main class="flex-1 p-6">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'

const showCreateDialog = ref(false)
</script>
