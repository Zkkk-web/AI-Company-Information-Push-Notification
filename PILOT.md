# 大厂幼年体情报提醒：7–10 天试跑

面向日常使用和维护的完整说明见 [`USAGE.zh-CN.md`](USAGE.zh-CN.md)。

这个分支复用 TrendRadar，只做每天一次的候选信号发现。关键词规则负责基线和接口故障时的回退；当前测试分支增加 Jev 固定选项判断，读取标题、来源、链接和 RSS 摘要，再按既定 A/B 口径输出。Jev 不生成长文本，也不负责抓取或发送通知。

## 当前口径

- A 级：AI SaaS/Productivity、AI 内容/娱乐/游戏/陪伴、AI+消费/全球互联网、AI+硬件项目，单轮融资不少于人民币 700 万（或约 100 万美元）。
- A 级：上述赛道被高瓴、HSG/红杉、真格、绿洲、源码、经纬、GGV、启明、顺为、五源、创新工场、a16z、Lightspeed、Accel 等机构投资。
- B 级：阿里、腾讯、字节、美团、快手、小红书、拼多多、百度、京东、华为、小米、大疆及头部 AI/海外大厂高管创业、加入或组建相关新团队。
- B 级：相关公司开新业务、进军新市场或出海。
- 排除基金自身募资；增量模式避免重复提醒。

规则在 `config/frequency_words.txt`，可选 AI 口径在 `config/custom/ai/startup-intelligence.txt`。

## 已接数据源

| 信号范围 | 来源 |
| --- | --- |
| 国内融资、公司与人员变动 | 36氪文章、36氪快讯、钛媒体、极客公园 |
| 国内 AI 产品、团队和产业动态 | 量子位、雷峰网 |
| 海外融资与创投 | TechCrunch Venture、Crunchbase News、Sifted |
| 海外 AI 产品与公司动作 | The Decoder、SiliconANGLE AI |
| 中文 AI 精选补漏 | AIHOT 精选 |
| 中文 AI 融资补漏 | Google 新闻：中文 AI 融资搜索 |
| 重点机构与人员变动补漏 | Google 新闻：重点 VC 投资动态、大厂高管创业动态 |
| 全球 AI 融资补漏 | Google 新闻：全球 AI 融资搜索 |

共 16 路已启用 RSS，其中 11 路来自独立媒体、1 路来自 AIHOT 精选、4 路为新闻搜索聚合。这里只统计已通过实际抓取和解析验证的来源，不把失效链接算入覆盖率。

微信公众号层已改用自托管 WechRss，并登记首批 8 个 VC 来源：真格基金、源码资本、启明创投、峰瑞资本、蓝驰创投、高榕创投、线性资本、绿洲资本。对应 Feed 已写入 `config/config.yaml`，但在首次同步触发微信读书人工验证、且公网 TLS 验证完成前保持 `enabled: false`，不计入上面的 16 路已验证来源。

## 本地验证

```bash
uv sync --frozen --no-dev
uv run python -m unittest discover -s tests -v
uv run python -m trendradar
```

最后一条会真实抓取，但没配置 webhook 时不会发群消息。

## GitHub Actions

工作流每天北京时间 09:30 运行，也支持手动触发。把本分支放到你控制的 GitHub 仓库后配置：

- 必需：`FEISHU_WEBHOOK_URL`，目标飞书群机器人的 webhook。
- Jev 测试：仓库 Secret `TYPESAFE_API_KEY`。手动 Actions 默认不传入飞书 webhook，因此只测试抓取和判断；只有显式勾选 `send_notifications` 才会真实发群消息。
- 通用生成式 AI 筛选仍可选：`AI_FILTER_ENABLED=true`、`AI_API_KEY`、`AI_MODEL`、`AI_API_BASE`。

试跑用 Actions cache 保存 SQLite 去重记录；正式长期运行时再换 R2/S3 或常驻 Docker。Actions cache 不是永久数据库。

## 已知上限

当前 Jev 读取标题和 RSS 自带摘要，尚未主动抓取全文；金额或人物信息只出现在正文深处时仍可能漏报。首轮真实测试确认精度和成本后，再决定是否增加正文抓取、语义去重、公司状态与职位薪资模块。
