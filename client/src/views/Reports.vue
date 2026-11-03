<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading" role="status">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error" role="alert">{{ error }}</div>
    <div v-else-if="isEmpty" class="loading" role="status">{{ t('reports.empty') }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalRevenue') }}</div>
          <div class="stat-value">{{ formatCurrency(totalRevenue, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatCurrency(avgMonthlyRevenue, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalOrders') }}</div>
          <div class="stat-value">{{ totalOrders.toLocaleString(numberLocale) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>

      <div v-if="quarterlyData.length" class="card">
        <div class="card-header">
          <h3 id="reports-quarterly-title" class="card-title">{{ t('reports.quarterly.title') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table" aria-labelledby="reports-quarterly-title">
            <thead>
              <tr>
                <th scope="col">{{ t('reports.quarterly.quarter') }}</th>
                <th scope="col">{{ t('reports.quarterly.totalOrders') }}</th>
                <th scope="col">{{ t('reports.quarterly.totalRevenue') }}</th>
                <th scope="col">{{ t('reports.quarterly.avgOrderValue') }}</th>
                <th scope="col">{{ t('reports.quarterly.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ q.quarter }}</strong></td>
                <td>{{ q.total_orders }}</td>
                <td>{{ formatCurrency(q.total_revenue, currentCurrency) }}</td>
                <td>{{ formatCurrency(q.avg_order_value, currentCurrency) }}</td>
                <td>
                  <span :class="['badge', getFulfillmentClass(q.fulfillment_rate)]">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="monthlyRows.length" class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.trend.title') }}</h3>
        </div>
        <div class="chart-container">
          <div class="bar-chart" role="img" :aria-label="t('reports.trend.chartLabel')">
            <div v-for="row in monthlyRows" :key="row.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  :style="{ height: getBarHeight(row.revenue) + 'px' }"
                  :title="row.label + ': ' + formatCurrency(row.revenue, currentCurrency)"
                ></div>
              </div>
              <div class="bar-label">{{ row.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="monthlyRows.length" class="card">
        <div class="card-header">
          <h3 id="reports-mom-title" class="card-title">{{ t('reports.mom.title') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table" aria-labelledby="reports-mom-title">
            <thead>
              <tr>
                <th scope="col">{{ t('reports.mom.month') }}</th>
                <th scope="col">{{ t('reports.mom.orders') }}</th>
                <th scope="col">{{ t('reports.mom.revenue') }}</th>
                <th scope="col">{{ t('reports.mom.change') }}</th>
                <th scope="col">{{ t('reports.mom.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthlyRows" :key="row.month">
                <td><strong>{{ row.label }}</strong></td>
                <td>{{ row.order_count }}</td>
                <td>{{ formatCurrency(row.revenue, currentCurrency) }}</td>
                <td>
                  <span v-if="row.hasPrevious" :class="row.changeClass">{{ row.changeText }}</span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="row.hasPrevious" :class="row.changeClass">{{ row.growthText }}</span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const CHART_MAX_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()
    const { selectedPeriod, selectedLocation, selectedCategory, selectedStatus, getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    const numberLocale = computed(() => (currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'))

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        error.value = t('reports.loadError') + ': ' + err.message
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], loadData)
    onMounted(loadData)

    const isEmpty = computed(() => quarterlyData.value.length === 0 && monthlyData.value.length === 0)

    const totalRevenue = computed(() => monthlyData.value.reduce((sum, m) => sum + m.revenue, 0))

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() => monthlyData.value.reduce((sum, m) => sum + m.order_count, 0))

    const bestQuarter = computed(() => {
      const best = quarterlyData.value.reduce(
        (top, q) => (q.total_revenue > (top ? top.total_revenue : 0) ? q : top),
        null
      )
      return best ? best.quarter : '-'
    })

    const maxRevenue = computed(() => Math.max(0, ...monthlyData.value.map(m => m.revenue)))

    const getBarHeight = (revenue) =>
      maxRevenue.value === 0 ? 0 : (revenue / maxRevenue.value) * CHART_MAX_HEIGHT

    const formatMonth = (monthStr) => {
      const date = new Date(`${monthStr}-01T00:00:00`)
      if (isNaN(date.getTime())) return monthStr
      return date.toLocaleDateString(numberLocale.value, { year: 'numeric', month: 'short' })
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    const formatSignedCurrency = (change) => {
      if (change > 0) return '+' + formatCurrency(change, currentCurrency.value)
      if (change < 0) return '-' + formatCurrency(Math.abs(change), currentCurrency.value)
      return formatCurrency(0, currentCurrency.value)
    }

    const formatGrowthRate = (current, previous) => {
      if (previous === 0) return t('reports.mom.notAvailable')
      const rate = ((current - previous) / previous) * 100
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    const monthlyRows = computed(() =>
      monthlyData.value.map((m, i) => {
        const previous = i > 0 ? monthlyData.value[i - 1] : null
        const change = previous ? m.revenue - previous.revenue : 0
        let changeClass = ''
        if (change > 0) changeClass = 'positive-change'
        else if (change < 0) changeClass = 'negative-change'
        return {
          ...m,
          label: formatMonth(m.month),
          hasPrevious: previous !== null,
          changeClass,
          changeText: formatSignedCurrency(change),
          growthText: previous ? formatGrowthRate(m.revenue, previous.revenue) : ''
        }
      })
    )

    return {
      t,
      currentCurrency,
      numberLocale,
      loading,
      error,
      isEmpty,
      quarterlyData,
      monthlyRows,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      getBarHeight,
      getFulfillmentClass,
      formatCurrency
    }
  }
}
</script>

<style scoped>
.reports-table th:not(:first-child),
.reports-table td:not(:first-child) {
  white-space: nowrap;
}

.chart-container {
  padding: 2rem 1rem 3rem;
  min-height: 300px;
  overflow-x: auto;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #3b82f6, #60a5fa);
  border-radius: 4px 4px 0 0;
  transition: background 0.3s;
}

.bar:hover {
  background: linear-gradient(to top, #2563eb, #3b82f6);
}

.bar-label {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>
