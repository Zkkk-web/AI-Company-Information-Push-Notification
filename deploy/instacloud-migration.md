# 微信 RSS 的 InstaCloud 迁移

2026-10-18，原 `ai-company-wechat-rss` 的三个服务已由 InstaCloud 接管。原账号、SQLite、8 个来源和原来关闭的调度状态保留，源服务只作兼容转发。

| 服务 | 直连入口 |
| --- | --- |
| WeWe RSS | https://prod-main-wewe-31a6fd-0033fe7ez0q.compute.instacloud-edge.com |
| WechRSS | https://prod-main-wechrss-d18172-0020n9hxqfh.compute.instacloud-edge.com |
| WeChat Download API | https://prod-main-download-acd925-001aq41bzyd.compute.instacloud-edge.com |

本仓库 8 个公众号来源仅更换主机，路径、来源 ID、`enabled: false`、筛选和投递规则保持原样。微信平台限流/人工验证是迁移前的独立限制，空 RSS 不表示已取得文章；未通过原有非空内容验收前不要开启采集，也不要为验证迁移触发抓取或消息投递。

已验证：三个数据库完整性、8 个 RSS 路径 HTTP 200、管理接口未认证 401/有效认证 200、目标唯一应用进程、重启后持久化及旧入口转发。旧服务、卷和凭据保留。回退先隔离目标并保全最新数据，不能重放旧快照或双开采集器。
