/** 异常样本定位清单接口：按来源和未齐类型定位分片差额，补录统计并提交抽验。 */
import { request } from './client'

export type SampleItem = {
  清单编号: string
  批次记录: number
  批次标识: string
  采集来源: string
  批次状态: string
  存储路径: string
  分片: number
  分片范围: string
  期望行数: number
  原始行数: number
  有效行数: number
  原始差额: number
  有效差额: number
  差额: number
  未齐类型: string[]
  未齐类型文本: string
  统计版本: string
  统计时间: string
}

export type SnapshotEntry = {
  清单编号?: string
  采集来源: string
  批次标识: string
  分片: number
  分片范围: string
  差额: number
  原始差额?: number
  有效差额?: number
  统计版本: string
  存储路径?: string
}

export type SampleListResult = {
  items: SampleItem[]
  total: number
  page: number
  size: number
  快照: SnapshotEntry[]
  筛选: Record<string, string>
}

export type SpotcheckDetail = {
  分片: number
  分片范围: string
  筛选时差额: number
  筛选时统计版本: string
  实际差额: number
  实际统计版本: string
  实际原始行数: number
  实际有效行数: number
  期望行数: number
  原始差额: number
  有效差额: number
  采用: boolean
  说明: string
}

export type SpotcheckRecord = {
  抽验编号: string
  提交时间: string
  采集来源: string
  批次标识: string
  存储路径: string
  采用范围: string[]
  对照范围: string[]
  采用分片: number[]
  触发前范围: { 分片: number; 分片范围: string; 差额: number; 统计版本: string }[]
  触发后范围: { 分片: number; 分片范围: string; 差额: number; 统计版本: string }[]
  筛选时差额: number
  实际差额: number
  筛选时统计版本: Record<string, string>
  实际统计版本: Record<string, string>
  返回行数: {
    记录数: number
    分片数: number
    原始行数: number
    有效行数: number
    期望行数: number
  }
  结果存储: {
    采集来源: string
    批次标识: string
    存储路径: string
    原始行数: number
    有效行数: number
    期望行数: number
    分片范围: string
    统计版本: string
  }
  分片明细: SpotcheckDetail[]
  保留历史对照: boolean
}

export type SampleOptions = {
  采集来源: string[]
  未齐类型: string[]
}

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) throw new Error(`${fallback}（接口返回 ${response.status}）`)
  return (await response.json()) as T
}

export async function loadSampleOptions(): Promise<SampleOptions> {
  const response = await request('/api/sample_locator/options')
  return await readJson<SampleOptions>(response, '筛选条件读取失败')
}

export async function listSamples(params: {
  采集来源?: string
  未齐类型?: string
  批次标识?: string
  keyword?: string
  page?: number
  size?: number
}): Promise<SampleListResult> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const response = await request(`/api/sample_locator?${query.toString()}`)
  return await readJson<SampleListResult>(response, '异常样本定位失败')
}

export async function supplementStatistics(payload: {
  采集来源: string
  批次标识: string
  分片: number
  原始行数?: number
  有效行数?: number
}): Promise<{ ok: boolean; message: string; entry: SampleItem | null }> {
  const response = await request('/api/sample_locator/supplement', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return await readJson(response, '统计补录失败')
}

export async function submitSpotcheck(payload: {
  采集来源: string
  批次标识: string
  快照: SnapshotEntry[]
  保留历史对照: boolean
}): Promise<{ ok: boolean; message: string; entry: SpotcheckRecord | null }> {
  const response = await request('/api/sample_locator/spotcheck', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return await readJson(response, '抽验提交失败')
}

export async function loadSpotcheckRecords(): Promise<{
  items: SpotcheckRecord[]
  total: number
}> {
  const response = await request('/api/sample_locator/records')
  return await readJson(response, '抽验记录读取失败')
}
