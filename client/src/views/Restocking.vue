<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading && !recommendations.length" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget control -->
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-controls">
          <input
            type="range"
            class="budget-slider"
            v-model.number="budget"
            min="0"
            max="100000"
            step="500"
          />
          <div class="budget-input-group">
            <span class="budget-currency">{{ currencySymbol }}</span>
            <input
              type="number"
              class="budget-number"
              v-model.number="budget"
              min="0"
              max="100000"
              step="500"
            />
          </div>
        </div>
        <div class="budget-display">{{ currencySymbol }}{{ (budget || 0).toLocaleString() }}</div>
      </div>

      <!-- Summary -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.budgetLabel') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ (budget || 0).toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card" :class="{ danger: budgetRemaining < 0 }">
          <div class="stat-label">{{ t('restocking.budgetRemaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ budgetRemaining.toLocaleString() }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ itemsRecommended }}</div>
        </div>
      </div>

      <!-- Success banner -->
      <div v-if="orderPlacedInfo" class="success-banner">
        <div class="success-banner-content">
          <strong>{{ t('restocking.orderPlaced', { orderNumber: orderPlacedInfo.orderNumber }) }}</strong>
          <span>{{ t('restocking.orderPlacedDetail', { count: orderPlacedInfo.count, total: orderPlacedInfo.total, date: orderPlacedInfo.date }) }}</span>
        </div>
        <button class="success-banner-close" @click="orderPlacedInfo = null" aria-label="Dismiss">×</button>
      </div>

      <!-- Recommendations table -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.itemsRecommended') }} ({{ recommendations.length }})</h3>
        </div>
        <div v-if="recommendations.length === 0" class="no-data">{{ t('restocking.noRecommendations') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.currentDemand') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.shortfall') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.recommendedQty') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td>{{ item.category }}</td>
                <td>{{ translateWarehouse(item.warehouse) }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td>{{ item.current_demand }}</td>
                <td>{{ item.forecasted_demand }}</td>
                <td>{{ item.shortfall }}</td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td><strong>{{ item.recommended_quantity }}</strong></td>
                <td>{{ currencySymbol }}{{ item.line_cost.toLocaleString() }}</td>
                <td>{{ item.lead_time_days }} {{ t('restocking.days') }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="place-order-row">
          <button
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
          <span v-if="submitError" class="place-order-error">{{ submitError }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName, translateWarehouse } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const recommendations = ref([])
    const budget = ref(10000)

    const submitting = ref(false)
    const submitError = ref(null)
    const orderPlacedInfo = ref(null)

    // Use shared filters (restocking only supports warehouse/category, no time dimension)
    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    const totalCost = computed(() => {
      return recommendations.value.reduce((sum, item) => sum + item.line_cost, 0)
    })

    const budgetRemaining = computed(() => {
      return (budget.value || 0) - totalCost.value
    })

    const itemsRecommended = computed(() => recommendations.value.length)

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        recommendations.value = await api.getRestockingRecommendations(budget.value || 0, filters)
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Debounce budget slider/number input changes to avoid hammering the API while dragging
    let debounceTimer = null
    watch(budget, () => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations()
      }, 300)
    })

    // React to global FilterBar (warehouse/category only - restocking has no time dimension)
    watch([selectedLocation, selectedCategory], () => {
      loadRecommendations()
    })

    const formatDate = (dateString) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const placeOrder = async () => {
      submitting.value = true
      submitError.value = null
      try {
        const filters = getCurrentFilters()
        const order = await api.createRestockOrder(budget.value || 0, filters)
        orderPlacedInfo.value = {
          orderNumber: order.order_number,
          count: order.items.length,
          total: `${currencySymbol.value}${order.total_cost.toLocaleString()}`,
          date: formatDate(order.expected_delivery)
        }
        // Note: placing an order doesn't mutate inventory/demand data server-side (demo behavior),
        // so re-running recommendations afterward intentionally returns the same list, not a bug.
      } catch (err) {
        submitError.value = err.response?.data?.detail || err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      loading,
      error,
      recommendations,
      budget,
      totalCost,
      budgetRemaining,
      itemsRecommended,
      submitting,
      submitError,
      orderPlacedInfo,
      placeOrder,
      currencySymbol,
      translateProductName,
      translateWarehouse
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-controls {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.5rem 0 1rem;
}

/* Custom range slider styling, matching the app's blue accent + focus-ring convention */
.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.budget-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.budget-slider:focus::-webkit-slider-thumb {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.budget-slider::-moz-range-thumb:hover {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
}

.budget-input-group {
  display: flex;
  align-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: white;
  overflow: hidden;
  flex-shrink: 0;
  transition: all 0.2s;
}

.budget-input-group:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.budget-currency {
  padding: 0.4rem 0 0.4rem 0.75rem;
  color: #64748b;
  font-weight: 600;
  font-size: 0.875rem;
}

.budget-number {
  width: 110px;
  padding: 0.4rem 0.75rem 0.4rem 0.25rem;
  border: none;
  outline: none;
  font-size: 0.875rem;
  font-weight: 600;
  color: #0f172a;
}

.budget-display {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.stat-card.danger .stat-value {
  color: #dc2626;
}

.no-data {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.875rem;
}

.place-order-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #f1f5f9;
}

.place-order-btn {
  padding: 0.625rem 1.5rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.place-order-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.place-order-error {
  color: #991b1b;
  font-size: 0.875rem;
}

/* Success banner - own visual family, green counterpart to the global .error style */
.success-banner {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-size: 0.938rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.success-banner-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.success-banner-close {
  background: none;
  border: none;
  color: #166534;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.success-banner-close:hover {
  color: #14532d;
}
</style>
