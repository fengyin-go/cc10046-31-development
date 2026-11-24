<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">网络数据采集与RPA自动化平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向网页数据采集、自动化流程编排、解析规则管理、代理池调度与采集结果校验的数据采集工程平台</span>
        <span class="head-user">当前值班：数据工程组</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
const navItems = [{ label: "运营概览", path: "/" }, { label: "爬虫配置", path: "/crawler_config" }, { label: "解析规则", path: "/parser_rule" }, { label: "代理池", path: "/proxy_pool" }, { label: "Cookie管理", path: "/cookie_mgr" }, { label: "限速控制", path: "/rate_limiter" }, { label: "抽取模板", path: "/extraction_template" }, { label: "数据校验器", path: "/data_validator" }, { label: "采集调度", path: "/crawl_schedule" }, { label: "结果存储", path: "/result_store" }, { label: "去重引擎", path: "/dedup_engine" }, { label: "字段映射", path: "/field_mapper" }, { label: "异常重试", path: "/error_retry" }, { label: "批次追踪", path: "/batch_tracker" }, { label: "异常样本定位", path: "/sample_locator" }, { label: "导出通道", path: "/export_channel" }, { label: "采集审计", path: "/crawl_audit" }, { label: "来源认证", path: "/source_auth" }, { label: "HTML清洗", path: "/html_cleaner" }, { label: "增量同步", path: "/incremental_sync" }]
</script>
