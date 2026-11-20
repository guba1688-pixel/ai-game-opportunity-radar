# 架构说明

浏览器管理台通过同源 JSON API 访问 Python `ThreadingHTTPServer`。服务层负责校验、公司画像融合评分、阶段门、分级、采集与导出；SQLite 仓储负责兼容迁移、事务、唯一约束和审计；适配器通过统一 `collect()` 接口提供标准化信号。

仅使用 Python 3.11 标准库，无外部 CDN或运行时包下载。schema v2 采用加列/新表迁移；`seed_key` 保证演示项目幂等。权限继续使用 MVP 角色头：admin 全权限，analyst 可查看/新增/编辑/导出/采集，viewer 只读；画像只允许 admin 修改。这不是生产身份认证。
