# 游戏市场资讯 API v1

服务地址：`http://127.0.0.1:8765`

## 鉴权

外部采集器应在服务进程中配置环境变量 `RADAR_API_KEY`，请求时添加 `X-API-Key` 请求头。API 采集账户只有查看、写入资讯和触发采集权限，没有删除机会、编辑公司画像或查看审计日志的权限。

## 写入一条资讯

`POST /api/v1/intelligence`

```json
{
  "title": "某游戏品类榜单连续上升",
  "summary": "关键排名、流水或用户趋势摘要",
  "source_name": "监测脚本",
  "source_url": "https://example.com/source",
  "observed_at": "2026-11-19",
  "sector": "game",
  "region": "全球",
  "evidence_type": "third_party_estimate",
  "confidence_grade": "B"
}
```

可选字段 `opportunity_id` 会把资讯直接关联到现有机会。重复判断使用标题、来源引用、观察日期和指标名称生成的稳定键；重复提交返回 `inserted: 0`。

## 批量写入

`POST /api/v1/intelligence/batch`

请求体使用公共来源字段加 `items` 数组。

## 查询

- `GET /api/v1/intelligence?sector=game`
- 可选参数：`q`、`evidence_type`、`source_type`、`freshness`
- `GET /api/v1/ingestion/status`：查看来源健康和 API 密钥启用状态

## 数据边界

- `source_url` 只允许 HTTP/HTTPS。
- 单次请求体上限 5 MB。
- 官方事实、第三方估算和分析推断必须分别标注。
- 每次正式导入前自动备份 SQLite，关键动作写入审计日志。
