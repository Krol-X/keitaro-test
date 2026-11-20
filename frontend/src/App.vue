<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <router-link to="/" class="brand-lockup" aria-label="Keitaro Campaign Panel — главная">
        <span class="brand-mark"><i class="pi pi-chart-line" aria-hidden="true"></i></span>
        <span><strong>Keitaro</strong><small>Campaign panel</small></span>
      </router-link>
      <nav class="side-nav" aria-label="Основная навигация">
        <router-link to="/" class="side-nav-link">
          <i class="pi pi-folder" aria-hidden="true"></i><span>Кампании</span>
        </router-link>
      </nav>
      <p class="side-footer">Данные кампаний и потоков синхронизируются с Keitaro.</p>
    </aside>
    <main class="app-content">
      <router-view />
    </main>
  </div>
</template>
