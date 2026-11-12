<script setup lang="ts">
defineProps<{ title: string; subtitle?: string; wide?: boolean }>()
defineEmits<{ close: [] }>()
</script>

<template>
  <Teleport to="body">
    <div class="modal-mask" @click.self="$emit('close')">
      <div class="modal-card" :class="{ wide }">
        <header class="modal-head">
          <div>
            <h3>{{ title }}</h3>
            <p v-if="subtitle">{{ subtitle }}</p>
          </div>
          <button type="button" class="modal-close" @click="$emit('close')">×</button>
        </header>
        <div class="modal-body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="modal-foot">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(3px);
}

.modal-card {
  width: min(560px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border-radius: 16px;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
  overflow: hidden;
}

.modal-card.wide {
  width: min(820px, 100%);
}

.modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 14px;
  border-bottom: 1px solid var(--line);
}

.modal-head h3 {
  margin: 0;
  font-size: 17px;
  color: var(--ink);
}

.modal-head p {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.modal-close {
  align-self: flex-start;
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  padding: 0 2px;
}

.modal-close:hover {
  color: var(--ink);
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px 20px;
  border-top: 1px solid var(--line);
  background: var(--panel-alt);
}
</style>
