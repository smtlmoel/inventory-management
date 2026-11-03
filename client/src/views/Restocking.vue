<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading" role="status">{{ t('common.loading') }}</div>
    <div v-else-if="initError" class="error" role="alert">{{ initError }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budgetLabel') }}</label>
          <output for="budget-slider" class="budget-value">{{ formatMoney(budget) }}</output>
        </div>
        <input
          id="budget-slider"
          class="budget-slider"
          type="range"
          min="0"
          :max="sliderMax"
          :step="sliderStep"
          :value="budget"
          :aria-valuetext="formatMoney(budget)"
          @input="onBudgetInput"
        />
        <div class="budget-scale" aria-hidden="true">
          <span>{{ formatMoney(0) }}</span>
          <span>{{ formatMoney(sliderMax) }}</span>
        </div>
        <p class="budget-max">{{ t('restocking.budgetMax', { max: formatMoney(maxBudget) }) }}</p>
      </div>

      <div v-if="orderSuccess" class="notice success" role="status">
        <strong>{{ t('restocking.orderPlaced', { number: orderSuccess.order_number }) }}</strong>
        <span>
          {{ t('restocking.orderDetails', {
            total: formatMoney(orderSuccess.total_cost),
            days: orderSuccess.lead_time_days,
            date: formatDate(orderSuccess.expected_delivery)
          }) }}
        </span>
      </div>
      <div v-if="actionError" class="error" role="alert">{{ actionError }}</div>

      <div class="card" :aria-busy="fetching">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendationsTitle') }}</h3>
          <button
            type="button"
            class="place-order"
            :disabled="items.length === 0 || submitting || fetching"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <p class="visually-hidden" role="status" aria-live="polite">
          {{ fetching ? t('restocking.updating') : '' }}
        </p>
        <div v-if="fetchError" class="error" role="alert">{{ fetchError }}</div>

        <p v-if="items.length === 0" class="empty">{{ t('restocking.noItems') }}</p>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th scope="col">{{ t('restocking.table.sku') }}</th>
                <th scope="col">{{ t('restocking.table.itemName') }}</th>
                <th scope="col">{{ t('restocking.table.trend') }}</th>
                <th scope="col" class="num">{{ t('restocking.table.unitCost') }}</th>
                <th scope="col" class="num">{{ t('restocking.table.quantity') }}</th>
                <th scope="col" class="num">{{ t('restocking.table.lineCost') }}</th>
                <th scope="col" class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody aria-live="polite">
              <tr v-for="item in items" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td class="num">{{ formatMoney(item.unit_cost) }}</td>
                <td class="num">{{ item.recommended_qty.toLocaleString() }}</td>
                <td class="num">{{ formatMoney(item.line_cost) }}</td>
                <td class="num">{{ t('restocking.leadDays', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colspan="5">{{ t('restocking.total') }}</th>
                <td class="num"><strong>{{ formatMoney(totalCost) }}</strong></td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const DEBOUNCE_MS = 200

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const loading = ref(true)
    const initError = ref(null)
    const fetching = ref(false)
    const fetchError = ref(null)
    const submitting = ref(false)
    const actionError = ref(null)
    const orderSuccess = ref(null)

    const maxBudget = ref(0)
    const budget = ref(0)
    const items = ref([])
    const totalCost = ref(0)

    let debounceTimer = null
    let requestId = 0

    const sliderStep = computed(() => 1)
    const sliderMax = computed(() => Math.ceil(maxBudget.value))

    const formatMoney = (amount) => formatCurrency(Number(amount) || 0, currentCurrency.value)

    const formatDate = (value) => {
      const date = new Date(value)
      if (isNaN(date.getTime())) return value
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const fetchRecommendations = async () => {
      const id = ++requestId
      fetching.value = true
      fetchError.value = null
      try {
        const data = await api.getRestockingRecommendations(budget.value)
        if (id !== requestId) return
        items.value = data.items
        totalCost.value = data.total_cost
        maxBudget.value = data.max_budget
      } catch (err) {
        if (id !== requestId) return
        fetchError.value = t('restocking.loadFailed') + ': ' + err.message
      } finally {
        if (id === requestId) fetching.value = false
      }
    }

    const onBudgetInput = (event) => {
      budget.value = Number(event.target.value)
      orderSuccess.value = null
      actionError.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(fetchRecommendations, DEBOUNCE_MS)
    }

    const placeOrder = async () => {
      if (items.value.length === 0 || submitting.value) return
      clearTimeout(debounceTimer)
      submitting.value = true
      actionError.value = null
      orderSuccess.value = null
      try {
        const order = await api.submitRestockOrder({
          budget: budget.value,
          items: items.value.map(i => ({ item_sku: i.item_sku, quantity: i.recommended_qty }))
        })
        orderSuccess.value = order
        await fetchRecommendations()
      } catch (err) {
        const detail = err.response?.data?.detail
        actionError.value = t('restocking.orderFailed') + ': ' + (typeof detail === 'string' ? detail : err.message)
      } finally {
        submitting.value = false
      }
    }

    const init = async () => {
      try {
        const data = await api.getRestockingRecommendations(0)
        maxBudget.value = data.max_budget
        budget.value = Math.round(data.max_budget / 2)
      } catch (err) {
        initError.value = t('restocking.loadFailed') + ': ' + err.message
        return
      } finally {
        loading.value = false
      }
      await fetchRecommendations()
    }

    onMounted(init)
    onBeforeUnmount(() => clearTimeout(debounceTimer))

    return {
      t,
      loading,
      initError,
      fetching,
      fetchError,
      submitting,
      actionError,
      orderSuccess,
      maxBudget,
      budget,
      items,
      totalCost,
      sliderStep,
      sliderMax,
      formatMoney,
      formatDate,
      onBudgetInput,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  max-width: 720px;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  height: 1.5rem;
  accent-color: #2563eb;
  cursor: pointer;
}

.budget-slider:focus-visible,
.place-order:focus-visible {
  outline: 3px solid #2563eb;
  outline-offset: 2px;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.budget-max {
  margin-top: 0.5rem;
  font-size: 0.813rem;
  color: #475569;
}

.place-order {
  background: #2563eb;
  color: #ffffff;
  border: 1px solid #2563eb;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.place-order:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order:disabled {
  background: #e2e8f0;
  border-color: #e2e8f0;
  color: #475569;
  cursor: not-allowed;
}

.notice.success {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin: 0 0 1.25rem;
  font-size: 0.938rem;
}

.empty {
  color: #64748b;
  font-size: 0.875rem;
  padding: 0.5rem 0;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

tfoot th,
tfoot td {
  border-top: 2px solid #e2e8f0;
  background: #f8fafc;
  color: #0f172a;
}

tfoot th {
  text-align: right;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
