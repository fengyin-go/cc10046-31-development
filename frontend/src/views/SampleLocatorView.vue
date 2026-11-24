<template>
  <section class="page" data-module="sample_locator">
    <header class="page-head">
      <div>
        <h2>异常样本定位</h2>
        <p class="page-desc">
          按采集来源和未齐类型定位批次差额所属分片；补录统计后按筛选快照提交统计抽验。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="refresh" type="button" @click="reload()">刷新清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">差额分片</span>
        <strong class="stat-value" data-testid="stat-gap">{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">当前页有效差额合计</span>
        <strong class="stat-value" data-testid="stat-valid-gap">{{ pageValidGap }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">涉及来源</span>
        <strong class="stat-value" data-testid="stat-sources">{{ sourceCount }}</strong>
      </article>
    </div>

    <form class="filter-bar" data-testid="sample-filter" @submit.prevent="query">
      <label class="filter-item">
        <span>采集来源</span>
        <select v-model="filters.source" data-testid="filter-采集来源">
          <option value="">全部来源</option>
          <option v-for="source in options.采集来源" :key="source" :value="source">{{ source }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>未齐类型</span>
        <select v-model="filters.unfinishedType" data-testid="filter-未齐类型">
          <option value="">全部类型</option>
          <option v-for="kind in options.未齐类型" :key="kind" :value="kind">{{ kind }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>批次标识</span>
        <input v-model="filters.batchLabel" data-testid="filter-批次标识" placeholder="按批次标识检索" />
      </label>
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="filters.keyword" data-testid="filter-keyword" placeholder="批次/范围/路径" />
      </label>
      <label class="filter-item">
        <span>每页条数</span>
        <select v-model.number="size" data-testid="filter-size" @change="go(1)">
          <option :value="1">1</option>
          <option :value="2">2</option>
          <option :value="5">5</option>
          <option :value="20">20</option>
        </select>
      </label>
      <button class="btn primary" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="reset">重置条件</button>
    </form>

    <p class="snapshot-hint" data-testid="snapshot-hint">
      筛选快照覆盖全部 {{ snapshot.length }} 条差额分片（不受当前页影响），提交抽验按该快照冻结差额。
    </p>

    <table class="data-table">
      <thead>
        <tr>
          <th>清单编号</th>
          <th>批次标识</th>
          <th>采集来源</th>
          <th>分片</th>
          <th>分片范围</th>
          <th>期望行数</th>
          <th>原始行数</th>
          <th>有效行数</th>
          <th>差额</th>
          <th>未齐类型</th>
          <th>统计版本</th>
          <th>存储路径</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.清单编号"
          :data-testid="`sample-row-${row.清单编号}`"
          :data-source="row.采集来源"
          :data-shard="row.分片"
        >
          <td>{{ row.清单编号 }}</td>
          <td>{{ row.批次标识 }}</td>
          <td>{{ row.采集来源 }}</td>
          <td>{{ row.分片 }}</td>
          <td>{{ row.分片范围 }}</td>
          <td>{{ row.期望行数 }}</td>
          <td>{{ row.原始行数 }}</td>
          <td>{{ row.有效行数 }}</td>
          <td :class="{ 'error-text': row.差额 > 0 }" data-testid="cell-gap">{{ row.差额 }}</td>
          <td>{{ row.未齐类型文本 || '—' }}</td>
          <td>{{ row.统计版本 }}</td>
          <td class="path-cell">{{ row.存储路径 }}</td>
          <td class="row-actions">
            <button
              class="link"
              type="button"
              :data-testid="`supplement-${row.清单编号}`"
              @click="openSupplement(row)"
            >
              补录统计
            </button>
            <button
              class="link"
              type="button"
              :data-testid="`spotcheck-one-${row.清单编号}`"
              @click="submitForGroup(row.采集来源, row.批次标识, false)"
            >
              提交抽验
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="13" class="empty-state">当前筛选条件下没有差额分片</td>
        </tr>
      </tbody>
    </table>

    <div class="page-foot">
      <span>共 {{ total }} 条差额分片，第 {{ page }} / {{ pageCount }} 页</span>
      <span class="pager">
        <button class="btn ghost" data-testid="prev-page" type="button" :disabled="page <= 1" @click="go(page - 1)">
          上一页
        </button>
        <button
          class="btn ghost"
          data-testid="next-page"
          type="button"
          :disabled="page >= pageCount"
          @click="go(page + 1)"
        >
          下一页
        </button>
      </span>
      <span v-if="errorMessage" class="error-text" data-testid="error-text">{{ errorMessage }}</span>
      <span v-if="noticeMessage" class="notice-text" data-testid="notice-text">{{ noticeMessage }}</span>
    </div>

    <section class="panel" data-testid="spotcheck-panel">
      <h3>统计抽验</h3>
      <p class="panel-hint">
        同一批次标签的不同采集来源单独定位、单独提交。勾选“保留历史对照”可把提交前已补齐的分片统计留在记录里。
      </p>
      <div v-if="!groups.length" class="empty-state">筛选结果里没有可抽验的批次分组</div>
      <div v-for="group in groups" :key="`${group.source}|${group.batchLabel}`" class="group-row" data-testid="group-row">
        <div class="group-head">
          <strong>{{ group.source }}</strong>
          <span class="muted">批次 {{ group.batchLabel }}</span>
          <span class="muted">差额分片 {{ group.count }} 个，差额合计 {{ group.gap }}</span>
        </div>
        <label class="inline-check">
          <input
            v-model="keepHistory[group.key]"
            type="checkbox"
            :data-testid="`keep-history-${group.key}`"
          />
          保留历史对照
        </label>
        <button
          class="btn primary"
          type="button"
          :data-testid="`spotcheck-${group.key}`"
          :disabled="submitting === group.key"
          @click="submitForGroup(group.source, group.batchLabel, keepHistory[group.key])"
        >
          {{ submitting === group.key ? '提交中…' : '提交统计抽验' }}
        </button>
      </div>
    </section>

    <section v-if="lastRecord" class="panel result-panel" data-testid="spotcheck-result">
      <h3>抽验结果 {{ lastRecord.抽验编号 }}</h3>
      <div class="result-grid">
        <div>
          <span class="muted">采集来源</span>
          <strong data-testid="result-source">{{ lastRecord.结果存储.采集来源 }}</strong>
        </div>
        <div>
          <span class="muted">批次标识</span>
          <strong data-testid="result-batch">{{ lastRecord.批次标识 }}</strong>
        </div>
        <div>
          <span class="muted">采用分片</span>
          <strong data-testid="result-shards">{{ lastRecord.采用分片.join('、') }}</strong>
        </div>
        <div>
          <span class="muted">存储路径</span>
          <strong class="path-cell" data-testid="result-path">{{ lastRecord.结果存储.存储路径 }}</strong>
        </div>
        <div>
          <span class="muted">返回原始行数</span>
          <strong data-testid="result-raw">{{ lastRecord.返回行数.原始行数 }}</strong>
        </div>
        <div>
          <span class="muted">返回有效行数</span>
          <strong data-testid="result-valid">{{ lastRecord.返回行数.有效行数 }}</strong>
        </div>
        <div>
          <span class="muted">筛选时差额</span>
          <strong data-testid="result-frozen-gap">{{ lastRecord.筛选时差额 }}</strong>
        </div>
        <div>
          <span class="muted">实际差额</span>
          <strong data-testid="result-actual-gap">{{ lastRecord.实际差额 }}</strong>
        </div>
      </div>

      <p class="path-line">实际采用范围：{{ lastRecord.结果存储.分片范围 }}，统计版本 {{ lastRecord.结果存储.统计版本 }}</p>
      <p v-if="lastRecord.对照范围.length" class="path-line">
        历史对照范围：{{ lastRecord.对照范围.join('、') }}
      </p>

      <table class="data-table compact">
        <thead>
          <tr>
            <th>分片</th>
            <th>筛选时差额</th>
            <th>筛选时版本</th>
            <th>实际差额</th>
            <th>实际版本</th>
            <th>实际原始行数</th>
            <th>实际有效行数</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="detail in lastRecord.分片明细" :key="detail.分片" :data-testid="`result-detail-${detail.分片}`">
            <td>{{ detail.分片 }}</td>
            <td>{{ detail.筛选时差额 }}</td>
            <td>{{ detail.筛选时统计版本 }}</td>
            <td>{{ detail.实际差额 }}</td>
            <td>{{ detail.实际统计版本 }}</td>
            <td>{{ detail.实际原始行数 }}</td>
            <td>{{ detail.实际有效行数 }}</td>
            <td>{{ detail.说明 }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel" data-testid="record-list">
      <h3>抽验记录</h3>
      <p v-if="!records.length" class="empty-state">暂无抽验记录</p>
      <table v-else class="data-table compact">
        <thead>
          <tr>
            <th>抽验编号</th>
            <th>提交时间</th>
            <th>采集来源</th>
            <th>批次标识</th>
            <th>采用分片</th>
            <th>返回有效行数</th>
            <th>筛选时差额</th>
            <th>实际差额</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in records" :key="record.抽验编号" :data-testid="`record-${record.抽验编号}`">
            <td>{{ record.抽验编号 }}</td>
            <td>{{ record.提交时间 }}</td>
            <td>{{ record.采集来源 }}</td>
            <td>{{ record.批次标识 }}</td>
            <td>{{ record.采用分片.join('、') }}</td>
            <td>{{ record.返回行数.有效行数 }}</td>
            <td>{{ record.筛选时差额 }}</td>
            <td>{{ record.实际差额 }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="showSupplement" class="modal-backdrop" data-testid="supplement-modal">
      <form class="modal" @submit.prevent="saveSupplement">
        <h3>补录分片统计</h3>
        <p class="panel-hint">
          {{ supplementTarget?.采集来源 }} / {{ supplementTarget?.批次标识 }} 第
          {{ supplementTarget?.分片 }} 片（{{ supplementTarget?.分片范围 }}）
        </p>
        <label class="create-field">
          <span>原始行数</span>
          <input v-model="supplementForm.原始行数" type="number" min="0" data-testid="supplement-raw" />
        </label>
        <label class="create-field">
          <span>有效行数</span>
          <input v-model="supplementForm.有效行数" type="number" min="0" data-testid="supplement-valid" />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showSupplement = false">取消</button>
          <button class="btn primary" data-testid="submit-supplement" type="submit">确认补录</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  listSamples,
  loadSampleOptions,
  loadSpotcheckRecords,
  submitSpotcheck,
  supplementStatistics,
} from '@/api/sample-locator'
import type {
  SampleItem,
  SampleOptions,
  SnapshotEntry,
  SpotcheckRecord,
} from '@/api/sample-locator'

const rows = ref<SampleItem[]>([])
const total = ref(0)
const snapshot = ref<SnapshotEntry[]>([])
const page = ref(1)
const size = ref(20)
const errorMessage = ref('')
const noticeMessage = ref('')
const records = ref<SpotcheckRecord[]>([])
const lastRecord = ref<SpotcheckRecord | null>(null)
const submitting = ref('')
const keepHistory = reactive<Record<string, boolean>>({})
const showSupplement = ref(false)
const supplementTarget = ref<SampleItem | null>(null)
const supplementForm = reactive({ 原始行数: '0', 有效行数: '0' })

const options = ref<SampleOptions>({ 采集来源: [], 未齐类型: [] })
const filters = reactive({ source: '', unfinishedType: '', batchLabel: '', keyword: '' })
const applied = reactive({ source: '', unfinishedType: '', batchLabel: '', keyword: '' })

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const pageValidGap = computed(() =>
  rows.value.reduce((sum, row) => sum + Number(row.有效差额 || 0), 0),
)
const sourceCount = computed(
  () => new Set(snapshot.value.map((entry) => entry.采集来源)).size,
)
const groups = computed(() => {
  const grouped = new Map<
    string,
    { key: string; source: string; batchLabel: string; count: number; gap: number }
  >()
  for (const entry of snapshot.value) {
    const key = `${entry.采集来源}-${entry.批次标识}`
    const current = grouped.get(key) ?? {
      key,
      source: entry.采集来源,
      batchLabel: entry.批次标识,
      count: 0,
      gap: 0,
    }
    current.count += 1
    current.gap += Number(entry.差额 || 0)
    grouped.set(key, current)
  }
  return [...grouped.values()]
})

function groupSnapshot(source: string, batchLabel: string): SnapshotEntry[] {
  return snapshot.value.filter(
    (entry) => entry.采集来源 === source && entry.批次标识 === batchLabel,
  )
}

async function reload({ keepSnapshot = false }: { keepSnapshot?: boolean } = {}) {
  errorMessage.value = ''
  try {
    const payload = await listSamples({
      采集来源: applied.source,
      未齐类型: applied.unfinishedType,
      批次标识: applied.batchLabel,
      keyword: applied.keyword,
      page: page.value,
      size: size.value,
    })
    rows.value = payload.items
    total.value = payload.total
    // 补录统计后刷新清单时保留筛选时的快照，抽验按筛选范围冻结差额。
    if (!keepSnapshot || !snapshot.value.length) snapshot.value = payload.快照
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '异常样本定位失败'
  }
}

async function reloadRecords() {
  try {
    const payload = await loadSpotcheckRecords()
    records.value = payload.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '抽验记录读取失败'
  }
}

async function query() {
  applied.source = filters.source
  applied.unfinishedType = filters.unfinishedType
  applied.batchLabel = filters.batchLabel
  applied.keyword = filters.keyword
  page.value = 1
  await reload()
}

async function reset() {
  filters.source = ''
  filters.unfinishedType = ''
  filters.batchLabel = ''
  filters.keyword = ''
  await query()
}

async function go(next: number) {
  page.value = Math.min(Math.max(1, next), pageCount.value)
  await reload()
}

function openSupplement(row: SampleItem) {
  supplementTarget.value = row
  supplementForm.原始行数 = String(row.原始行数)
  supplementForm.有效行数 = String(row.有效行数)
  showSupplement.value = true
}

async function saveSupplement() {
  if (!supplementTarget.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const result = await supplementStatistics({
      采集来源: supplementTarget.value.采集来源,
      批次标识: supplementTarget.value.批次标识,
      分片: supplementTarget.value.分片,
      原始行数: Number(supplementForm.原始行数),
      有效行数: Number(supplementForm.有效行数),
    })
    if (!result.ok && !result.entry) throw new Error(result.message)
    showSupplement.value = false
    noticeMessage.value = result.message
    await reload({ keepSnapshot: true })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '统计补录失败'
  }
}

async function submitForGroup(source: string, batchLabel: string, keep: boolean) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const frozen = groupSnapshot(source, batchLabel)
  if (!frozen.length) {
    errorMessage.value = '筛选快照里没有该批次的分片差额'
    return
  }
  submitting.value = `${source}-${batchLabel}`
  try {
    const result = await submitSpotcheck({
      采集来源: source,
      批次标识: batchLabel,
      快照: frozen,
      保留历史对照: keep,
    })
    if (!result.ok || !result.entry) throw new Error(result.message)
    lastRecord.value = result.entry
    noticeMessage.value = result.message
    await Promise.all([reload(), reloadRecords()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '抽验提交失败'
  } finally {
    submitting.value = ''
  }
}

onMounted(async () => {
  await reloadRecords()
  try {
    options.value = await loadSampleOptions()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '筛选条件读取失败'
  }
  await reload()
})
</script>

<style scoped>
.filter-item select,
.filter-item input {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  min-width: 160px;
}
.snapshot-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 10px;
}
.path-cell {
  font-size: 12px;
  word-break: break-all;
}
.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  margin-top: 16px;
}
.panel h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.panel-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 10px;
}
.group-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f2f5;
}
.group-head {
  flex: 1;
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 13px;
}
.inline-check {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.muted {
  color: var(--muted);
  font-size: 12px;
}
.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}
.result-grid span {
  display: block;
}
.result-grid strong {
  font-size: 14px;
}
.path-line {
  font-size: 12px;
  color: var(--muted);
  margin: 4px 0;
}
.compact th,
.compact td {
  padding: 6px 8px;
}
.pager {
  display: flex;
  gap: 8px;
}
</style>
