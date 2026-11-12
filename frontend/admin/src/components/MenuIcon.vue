<script setup lang="ts">
defineProps<{ name: string | null }>()
</script>

<template>
  <svg class="menu-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path
      v-if="name === 'chat'"
      d="M4 5h16v11H9l-4 3v-3H4z M7 8h10 M7 11h6"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'map'"
      d="M9 4 4 6v14l5-2 6 2 5-2V4l-5 2-6-2z M9 4v14 M15 6v14"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
    />
    <path
      v-else-if="name === 'book'"
      d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3V4z M5 4v16 M8 8h7"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'shield'"
      d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3z M9.5 12l2 2 3.5-4"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'users'"
      d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M2 20c0-3 2.5-5 6-5s6 2 6 5 M16 6a3 3 0 0 1 0 5.5 M15 15c3.5 0 6 2 6 5"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'menu'"
      d="M4 6h16 M4 12h16 M4 18h16"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'key'"
      d="M14 10a4 4 0 1 0-3.5 4L9 16H6v3H3v-3l6.5-6.5A4 4 0 0 1 14 10z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'user'"
      d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c0-4 3.5-6 8-6s8 2 8 6"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
    />
    <circle v-else cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.7" />
  </svg>
</template>

<style scoped>
.menu-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: currentColor;
}
</style>
