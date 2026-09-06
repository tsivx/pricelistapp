<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { callGemini, buildUserPrompt, type PricelistItem } from './lib/gemini'

const LS_KEY = 'pricelist_gemini_key'
const LS_MODEL = 'pricelist_gemini_model'
const DEFAULT_MODEL = 'gemini-3.5-flash-lite'

const apiKey = ref('')
const modelName = ref(DEFAULT_MODEL)
const rawInput = ref('')
const rulesInput = ref('')
const extraInput = ref('')
const rounding = ref('100')
const error = ref('')
const loading = ref(false)
const items = ref<PricelistItem[]>([])
const settingsOpen = ref(false)
const settingsStatus = ref('')
const copyStatus = ref('')

const LS_RAW = 'pricelist_raw'
const LS_RULES = 'pricelist_rules'
const LS_EXTRA = 'pricelist_extra'

onMounted(() => {
  apiKey.value = localStorage.getItem(LS_KEY) ?? ''
  modelName.value = localStorage.getItem(LS_MODEL) ?? DEFAULT_MODEL
  rawInput.value = localStorage.getItem(LS_RAW) ?? ''
  rulesInput.value = localStorage.getItem(LS_RULES) ?? ''
  extraInput.value = localStorage.getItem(LS_EXTRA) ?? ''
  if (!apiKey.value) settingsOpen.value = true
})

function saveSettings() {
  localStorage.setItem(LS_KEY, apiKey.value.trim())
  localStorage.setItem(LS_MODEL, modelName.value.trim() || DEFAULT_MODEL)
  settingsStatus.value = 'Сохранено'
  setTimeout(() => (settingsStatus.value = ''), 1800)
}

function clearAll() {
  rawInput.value = ''
  rulesInput.value = ''
  extraInput.value = ''
  error.value = ''
  items.value = []
  localStorage.removeItem(LS_RAW)
  localStorage.removeItem(LS_RULES)
  localStorage.removeItem(LS_EXTRA)
}

const byCategory = computed(() => {
  const m = new Map<string, PricelistItem[]>()
  for (const it of items.value) {
    const cat = it.category || 'Без категории'
    if (!m.has(cat)) m.set(cat, [])
    m.get(cat)!.push(it)
  }
  return m
})

const resultText = computed(() => {
  if (!items.value.length) return ''
  const lines: string[] = []
  for (const [cat, arr] of byCategory.value) {
    lines.push(cat)
    for (const it of arr) {
      lines.push(`${it.name} - ${formatPrice(it.final_price)}`)
    }
    lines.push('')
  }
  return lines.join('\n').trimEnd()
})

// — динамические колонки таблицы из union attrs.name —
const attrColumns = computed<string[]>(() => {
  const seen = new Set<string>()
  const order: string[] = []
  for (const it of items.value) {
    for (const a of it.attrs ?? []) {
      const k = (a.name || '').trim()
      if (!k || seen.has(k)) continue
      seen.add(k)
      order.push(k)
    }
  }
  return order
})

function attrMap(it: PricelistItem): Map<string, string> {
  const m = new Map<string, string>()
  for (const a of it.attrs ?? []) if (a.name) m.set(a.name, a.value ?? '')
  return m
}

const medians = computed(() => {
  const m = new Map<string, number>()
  for (const [cat, arr] of byCategory.value) {
    const prices = arr.map((x) => x.original_price).sort((a, b) => a - b)
    const mid = Math.floor(prices.length / 2)
    const median = prices.length % 2 ? prices[mid] : (prices[mid - 1] + prices[mid]) / 2
    m.set(cat, median)
  }
  return m
})

function isAnomaly(it: PricelistItem): boolean {
  const median = medians.value.get(it.category) ?? it.original_price
  return it.original_price < 10000 || it.original_price < median * 0.4 || it.final_price < it.original_price
}

async function onRun() {
  error.value = ''
  const key = apiKey.value.trim() || localStorage.getItem(LS_KEY) || ''
  const model = (modelName.value.trim() || DEFAULT_MODEL).replace(/^models\//, '')
  if (!key) {
    settingsOpen.value = true
    error.value = 'Укажи API Key в настройках.'
    return
  }
  if (!rawInput.value.trim()) {
    error.value = 'Вставь сырой прайс-лист.'
    return
  }
  if (!rulesInput.value.trim() && !rounding.value) {
    error.value = 'Опиши правила наценки или выбери округление.'
    return
  }
  localStorage.setItem(LS_RAW, rawInput.value)
  localStorage.setItem(LS_RULES, rulesInput.value)
  localStorage.setItem(LS_EXTRA, extraInput.value)
  localStorage.setItem(LS_KEY, key)
  localStorage.setItem(LS_MODEL, model)

  loading.value = true
  try {
    const prompt = buildUserPrompt(rulesInput.value, rounding.value, rawInput.value, extraInput.value)
    const res = await callGemini(key, model, prompt)
    if (!res.length) throw new Error('Gemini не нашёл товаров. Проверь формат прайса.')
    items.value = res
    setTimeout(() => document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function onCopy() {
  const t = resultText.value
  if (!t) return
  try {
    await navigator.clipboard.writeText(t)
    copyStatus.value = 'Скопировано'
  } catch {
    const el = document.getElementById('resultText')
    if (el) {
      const range = document.createRange()
      range.selectNodeContents(el)
      const sel = window.getSelection()
      sel?.removeAllRanges()
      sel?.addRange(range)
      document.execCommand('copy')
      sel?.removeAllRanges()
      copyStatus.value = 'Скопировано'
    }
  }
  setTimeout(() => (copyStatus.value = ''), 1800)
}

function formatPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString('ru-RU')
}
</script>

<template>
  <div class="min-h-dvh bg-zinc-50 text-zinc-900">
    <div class="mx-auto max-w-[1100px] px-3 sm:px-4 py-4 sm:py-6">
      <header class="mb-4">
        <h1 class="text-[22px] sm:text-2xl font-bold tracking-tight">Pricelist</h1>
        <p class="mt-1 text-sm leading-5 text-zinc-500">
          Вставь сырой прайс и условия наценки — получи готовый текст по категориям. Всё через Gemini, без бэкенда. Товары могут быть любыми.
        </p>
      </header>

      <div class="rounded-2xl border border-zinc-200 bg-white shadow-sm mb-4 overflow-hidden">
        <button type="button" class="flex w-full items-center justify-between px-4 py-3 text-left" @click="settingsOpen = !settingsOpen">
          <span class="text-sm font-semibold">Настройки Gemini</span>
          <span class="text-zinc-400 text-sm">{{ settingsOpen ? '−' : '+' }}</span>
        </button>
        <div v-if="settingsOpen" class="border-t border-zinc-200 px-4 py-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="flex flex-col gap-1.5">
              <span class="text-xs font-semibold">API Key</span>
              <input
                v-model="apiKey"
                type="password"
                placeholder="AIza…"
                autocomplete="off"
                class="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100"
              />
              <span class="text-[11px] text-zinc-500">Хранится в localStorage.</span>
            </label>
            <label class="flex flex-col gap-1.5">
              <span class="text-xs font-semibold">Модель</span>
              <input
                v-model="modelName"
                type="text"
                placeholder="gemini-3.5-flash-lite"
                class="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100"
              />
              <span class="text-[11px] text-zinc-500">По умолчанию как в <code class="rounded bg-zinc-100 px-1 py-0.5">main.py</code>.</span>
            </label>
          </div>
          <div class="mt-3 flex items-center gap-3">
            <button type="button" class="rounded-xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-zinc-50" @click="saveSettings">Сохранить</button>
            <span class="text-xs text-zinc-500">{{ settingsStatus }}</span>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-zinc-200 bg-white shadow-sm p-3 sm:p-4 mb-4">
        <div class="grid gap-3 sm:gap-4 sm:grid-cols-2">
          <label class="flex flex-col gap-1.5">
            <span class="text-xs font-semibold">Сырой прайс-лист от поставщика</span>
            <textarea
              v-model="rawInput"
              rows="10"
              placeholder="Вставь как есть, с эмодзи и флагами&#10;📱iPhone 15 ↙️&#10;15 128 Black - 53800 🇮🇳&#10;15 Pro 512 Blue - 89000 🇺🇸(ESIM)"
              class="min-h-[180px] w-full resize-y rounded-xl border border-zinc-200 bg-white px-3 py-2.5 font-mono text-[13px] leading-5 outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100"
            />
          </label>
          <label class="flex flex-col gap-1.5">
            <span class="text-xs font-semibold">Условия наценки</span>
            <textarea
              v-model="rulesInput"
              rows="10"
              placeholder="Свободный текст:&#10;Базовая на iPhone 15 +1000 ₽&#10;128 ГБ +100, 256 ГБ +200, 512 ГБ +400&#10;Plus +1000, Pro +2000&#10;eSIM +100&#10;Цена 45000–50000 → +2000&#10;% / фикс / % + фикс&#10;Округление до 1000 вверх"
              class="min-h-[180px] w-full resize-y rounded-xl border border-zinc-200 bg-white px-3 py-2.5 font-mono text-[13px] leading-5 outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100"
            />
          </label>
        </div>

        <label class="mt-3 flex flex-col gap-1.5">
          <span class="text-xs font-semibold">Дополнительные условия <span class="font-normal text-zinc-400">— опционально</span></span>
          <textarea
            v-model="extraInput"
            rows="3"
            placeholder="Например: свои категории, правила группировки, исключения или доп. инструкции для Gemini&#10;— iPhone 15 и 15 Plus — в категорию «iPhone 15», Pro/Max — в «iPhone 15 Pro»&#10;— Аксессуары — в «Аксессуары», остальное — по бренду"
            class="min-h-[72px] w-full resize-y rounded-xl border border-zinc-200 bg-white px-3 py-2.5 font-mono text-[13px] leading-5 outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100"
          />
          <span class="text-[11px] text-zinc-500">Gemini будет ориентироваться на этот текст при категоризации и любых других решениях. Оставь пустым, если не нужно.</span>
        </label>

        <div class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label class="flex flex-col gap-1.5 sm:w-[220px]">
            <span class="text-xs font-semibold">Округление</span>
            <select v-model="rounding" class="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-zinc-300 focus:ring-2 focus:ring-zinc-100">
              <option value="">Без округления</option>
              <option value="10">до 10</option>
              <option value="50">до 50</option>
              <option value="100">до 100</option>
              <option value="500">до 500</option>
              <option value="1000">до 1000</option>
            </select>
            <span class="text-[11px] text-zinc-500">В пользу магазина (ceil).</span>
          </label>
          <div class="flex gap-2 sm:ml-auto">
            <button type="button" class="flex-1 sm:flex-none inline-flex items-center justify-center rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-zinc-800 disabled:opacity-50" :disabled="loading" @click="onRun">
              {{ loading ? 'Обрабатываю…' : 'Обработать' }}
            </button>
            <button type="button" class="rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-semibold hover:bg-zinc-50" @click="clearAll">Очистить</button>
          </div>
        </div>

        <div v-if="error" class="mt-3 whitespace-pre-wrap rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">{{ error }}</div>
      </div>

      <div v-if="items.length" id="result" class="rounded-2xl border border-zinc-200 bg-white shadow-sm p-3 sm:p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-sm font-bold">Готовый прайс</h2>
          <div class="flex items-center gap-2">
            <span class="text-xs text-zinc-500">{{ copyStatus }}</span>
            <button type="button" class="rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-sm font-semibold hover:bg-zinc-50" @click="onCopy">Копировать текст</button>
          </div>
        </div>

        <pre id="resultText" contenteditable="true" spellcheck="false" class="mt-3 max-h-[420px] min-h-[120px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-zinc-200 bg-zinc-50/60 px-3 py-3 font-mono text-[13px] leading-5 outline-none focus:bg-white focus:ring-2 focus:ring-zinc-100">{{ resultText }}</pre>

        <h3 class="mt-5 text-sm font-semibold">Проверка</h3>
        <p class="mt-1 text-xs leading-4 text-zinc-500">
          Все атрибуты и колонки формирует Gemini. Жёлтым — подозрительные цены (напр. 4500 вместо 45000). Дубликаты уже удалены.
        </p>

        <!-- Mobile: cards -->
        <div class="mt-3 flex flex-col gap-2 sm:hidden">
          <div
            v-for="(it, idx) in items"
            :key="idx"
            class="rounded-xl border bg-white p-3 shadow-sm"
            :class="isAnomaly(it) ? 'border-amber-400 bg-amber-50' : 'border-zinc-200'"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="text-[11px] font-medium uppercase tracking-wide text-zinc-400">{{ it.category }}</div>
                <div class="mt-0.5 break-words text-[15px] font-semibold leading-5">{{ it.name }}</div>
              </div>
              <div class="shrink-0 text-right">
                <div class="text-[10px] uppercase tracking-wide text-zinc-400">Розница</div>
                <div class="text-[18px] font-bold leading-6 tabular-nums">{{ formatPrice(it.final_price) }}</div>
              </div>
            </div>

            <!-- attrs as label/value chips -->
            <dl v-if="it.attrs && it.attrs.length" class="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
              <div v-for="(a, ai) in it.attrs" :key="ai" class="flex items-baseline gap-1 text-[12px]">
                <dt class="text-zinc-400">{{ a.name }}:</dt>
                <dd class="font-medium text-zinc-700">{{ a.value }}</dd>
              </div>
            </dl>

            <!-- prices -->
            <div class="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-zinc-100 pt-2 text-[12px] tabular-nums">
              <div class="text-zinc-500">Опт <span class="font-semibold text-zinc-700">{{ formatPrice(it.original_price) }}</span></div>
              <div class="text-zinc-500">Наценка <span class="font-semibold text-emerald-600">+{{ formatPrice(it.markup_applied) }}</span></div>
            </div>

            <!-- markup breakdown -->
            <div v-if="it.markup_breakdown" class="mt-2 rounded-lg bg-zinc-50 px-2.5 py-1.5 font-mono text-[11px] leading-4 break-words text-zinc-600">
              {{ it.markup_breakdown }}
            </div>
          </div>
        </div>

        <!-- Desktop: table -->
        <div class="mt-3 hidden overflow-auto rounded-xl border border-zinc-200 sm:block">
          <table class="w-full border-collapse bg-white text-[13px]">
            <thead>
              <tr class="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500">
                <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-semibold">Категория</th>
                <th class="border-b border-zinc-200 px-2.5 py-2 font-semibold">Название</th>
                <th v-for="col in attrColumns" :key="col" class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 font-semibold">
                  {{ col }}
                </th>
                <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 text-right font-semibold">Опт</th>
                <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 text-right font-semibold">Наценка</th>
                <th class="whitespace-nowrap border-b border-zinc-200 px-2.5 py-2 text-right font-semibold">Розница</th>
                <th class="border-b border-zinc-200 px-2.5 py-2 font-semibold">Объяснение наценки</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, idx) in items" :key="idx" :class="isAnomaly(it) ? 'bg-amber-50' : ''" :title="isAnomaly(it) ? 'Подозрительная цена — проверь вручную' : undefined">
                <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-2" :class="isAnomaly(it) ? 'border-l-[3px] border-l-amber-500' : ''">{{ it.category }}</td>
                <td class="border-b border-zinc-100 px-2.5 py-2">{{ it.name }}</td>
                <td v-for="col in attrColumns" :key="col" class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-2">
                  {{ attrMap(it).get(col) ?? '—' }}
                </td>
                <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-2 text-right tabular-nums">{{ formatPrice(it.original_price) }}</td>
                <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-2 text-right tabular-nums text-emerald-600">+{{ formatPrice(it.markup_applied) }}</td>
                <td class="whitespace-nowrap border-b border-zinc-100 px-2.5 py-2 text-right tabular-nums font-semibold">{{ formatPrice(it.final_price) }}</td>
                <td class="min-w-[220px] max-w-[360px] border-b border-zinc-100 px-2.5 py-2 font-mono text-[11px] leading-4 text-zinc-600 whitespace-normal break-words">
                  {{ it.markup_breakdown || '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-2 text-xs text-zinc-500">{{ items.length }} позиций · {{ byCategory.size }} категорий<span v-if="attrColumns.length"> · атрибутов: {{ attrColumns.join(', ') }}</span></div>
      </div>

      <footer class="mt-4 px-1 text-[11px] leading-4 text-zinc-400">
        System instruction — из переданной инструкции; attrs — динамический массив; наценки/округление считает Gemini.
      </footer>
    </div>
  </div>
</template>
