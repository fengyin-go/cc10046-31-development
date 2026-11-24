"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import sample_locator
from app.routers import resource
from app.routers import chains

# 固定路径路由必须先于通用 /api/{module} 注册，避免被动态模块路径抢先匹配。
ROUTERS = [sample_locator, resource, chains]
