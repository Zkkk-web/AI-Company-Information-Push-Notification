# 大厂幼年体公司情报

本仓库的飞书应用机器人交付已经从“逐篇新闻列表”升级为“公司级 BD 线索”。Jev 仍只负责 A/B 级候选筛选；候选通过后，由 `trendradar.intelligence.company` 完成以下工作：

1. 从标题和 RSS 摘要提取公司、资方、团队与触发事件。
2. 字段缺失时尝试读取公开网页正文；网页失败不会阻塞当天推送。
3. 按规范化公司名合并同一公司的多来源报道，保留最多四个证据链接。
4. 只输出报道中有明确文字证据的内容；缺失值显示“暂未从公开报道确认”。
5. 生成飞书 `post` 可直接渲染的 Markdown，不使用 `<font>` 等卡片专属标签。

该能力只作用于 `FEISHU_OUTBOX_PATH` 对应的本机应用机器人交付，不改变原有飞书 webhook 交互卡片及其他通知渠道。

配置位于 `config/config.yaml`：

```yaml
notification:
  channels:
    feishu:
      company_intelligence: true
      fetch_article_text: true
```

环境变量 `FEISHU_COMPANY_INTELLIGENCE` 和 `FEISHU_FETCH_ARTICLE_TEXT` 可以覆盖配置。正文读取最多并发八个请求，单个请求默认超时八秒，页面不可读时自动退回标题和 RSS 摘要。

## 输出字段

- 公司：报道明确指向的创业公司；无法确认时不猜测。
- 级别：沿用 Jev 的 A/B 级判断。
- 触发事件：融资、团队或业务变化的原始标题。
- 资方：只识别标题和 RSS 摘要中明确出现的机构。
- 团队：从标题、摘要及与该公司同句出现的正文证据中提取。
- 来源：合并后的公开报道链接。

## 验证

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```

核心回归测试覆盖中英文公司名、投资机构、团队证据、未知字段、同公司合并、飞书渲染以及旧 `<font>` 标签清理。
