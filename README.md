# 网络数据采集与RPA自动化平台

面向网页数据采集、自动化流程编排、解析规则管理、代理池调度与采集结果校验的数据采集工程平台

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              业务模块配置（含异常样本定位）
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/routers/sample_locator.py  异常样本定位/补录/抽验接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/sample_locator.py  分片差额定位与统计抽验
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8010/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5174/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8010`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 爬虫配置 | `crawler_config` | 爬虫配置 | 配置标识、起始地址、页面编码 |
| 解析规则 | `parser_rule` | 解析规则 | 规则标识、目标页面、字段选择器 |
| 代理池 | `proxy_pool` | 代理节点 | 节点标识、代理地址、代理协议 |
| Cookie管理 | `cookie_mgr` | Cookie会话 | 会话标识、来源站点、Cookie内容 |
| 限速控制 | `rate_limiter` | 限速策略 | 策略标识、目标站点、请求频率 |
| 抽取模板 | `extraction_template` | 抽取模板 | 模板标识、适用站点、列表选择器 |
| 数据校验器 | `data_validator` | 校验规则 | 规则标识、校验字段、校验类型 |
| 采集调度 | `crawl_schedule` | 调度任务 | 任务标识、关联配置、调度周期 |
| 结果存储 | `result_store` | 存储批次 | 批次标识、来源配置、采集时间 |
| 去重引擎 | `dedup_engine` | 去重策略 | 策略标识、业务键列、排序字段 |
| 字段映射 | `field_mapper` | 映射方案 | 方案标识、来源字段、目标字段 |
| 异常重试 | `error_retry` | 重试策略 | 策略标识、错误类型、重试次数 |
| 批次追踪 | `batch_tracker` | 采集批次 | 批次标识、调度任务、开始时间 |
| 导出通道 | `export_channel` | 导出任务 | 任务标识、来源批次、导出格式 |
| 采集审计 | `crawl_audit` | 审计记录 | 记录标识、操作类型、操作对象 |
| 来源认证 | `source_auth` | 认证凭证 | 凭证标识、来源站点、认证方式 |
| HTML清洗 | `html_cleaner` | 清洗模板 | 模板标识、适用站点、标签过滤 |
| 增量同步 | `incremental_sync` | 同步水位 | 水位标识、来源配置、增量字段 |
| 异常样本定位 | `sample_locator` | 异常样本 | 清单编号、采集来源、分片、差额 |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

领域：数据工程
子方向：数据采集、爬虫与RPA

## 异常样本定位清单

批次追踪只记录整批总数，不提供「按批次差额定位到分片」的入口。异常样本定位清单
（`/sample_locator`）把结果存储中实际落库批次的 `分片统计` 展开成按分片一行的清单：

- **按采集来源 + 批次标识 + 分片唯一定位**：同一批次标签来自不同采集来源时是两份
  独立落库批次，必须带采集来源分别定位，不会互相覆盖。
- **筛选**：支持 `采集来源`、`未齐类型`（`原始行缺失` / `有效行不足`）、`批次标识`、
  `keyword` 和分页；差额为 0 的分片不进入清单。
- **筛选快照**：列表响应同时返回覆盖全部筛选结果的 `快照`，不受当前页影响；提交抽验
  时用它冻结「筛选时差额」和「筛选时统计版本」。
- **补录迟到统计**：`POST /api/sample_locator/supplement` 按来源写回某片的原始/有效行数，
  统计版本自动递增（值未变化时不升版本），并回写批次合计。
- **提交抽验**：`POST /api/sample_locator/spotcheck` 按快照提交：
  - 提交时仍有差额的分片进入采用范围，读取的是该来源实际落库批次的统计；
  - 提交前已补齐的分片默认不纳入；传 `保留历史对照` 可把它们留在记录里；
  - 记录同时保存筛选时差额/版本、实际差额/版本、触发前后范围，可逐批次复核；
  - `结果存储` 字段的统计、来源和路径只反映实际采用的抽验范围。

相关接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/sample_locator` | 分片清单 + 冻结快照 |
| GET | `/api/sample_locator/options` | 来源与未齐类型下拉 |
| GET | `/api/sample_locator/batch` | 按来源读取实际落库批次统计 |
| POST | `/api/sample_locator/supplement` | 补录分片迟到统计 |
| POST | `/api/sample_locator/spotcheck` | 按快照提交统计抽验 |
| GET | `/api/sample_locator/records` | 抽验记录 |
