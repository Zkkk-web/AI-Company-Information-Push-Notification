# 大厂幼年体公司情报

本仓库的飞书应用机器人交付已经从“逐篇新闻列表”升级为“公司级 BD 线索”。Jev 仍只负责 A/B 级候选筛选；候选通过后，由 `trendradar.intelligence.company` 完成以下工作：

1. 从标题和 RSS 摘要提取公司、主要业务、所属方向、融资阶段、总部与团队所在地、资方、团队和触发事件。
2. 字段缺失时尝试读取公开网页正文；网页失败不会阻塞当天推送。
3. 按规范化公司名合并同一公司的多来源报道，保留最多四个证据链接。
4. 合并证据后执行 BD 成熟度门槛：排除 C 轮及以后、Pre-IPO、已上市及配置中的成熟公司；阶段未知的早期线索保留。
5. 只输出报道中有明确文字证据的内容；缺失值显示“暂未从公开报道确认”。
6. 生成飞书 `post` 可直接渲染的 Markdown，不使用 `<font>` 等卡片专属标签。

该能力只作用于 `FEISHU_OUTBOX_PATH` 对应的本机应用机器人交付，不改变原有飞书 webhook 交互卡片及其他通知渠道。

配置位于 `config/config.yaml`：

```yaml
notification:
  channels:
    feishu:
      company_intelligence: true
      fetch_article_text: true
      mature_company_exclusions:
        - Anthropic
        - DeepSeek
        - OpenAI
        - Waymo
```

环境变量 `FEISHU_COMPANY_INTELLIGENCE` 和 `FEISHU_FETCH_ARTICLE_TEXT` 可以覆盖两个功能开关。成熟公司排除表保留在版本化配置中，便于审阅每次变化。正文读取最多并发八个请求，单个请求默认超时八秒，页面不可读时自动退回标题和 RSS 摘要。

## 输出字段

- 公司：报道明确指向的创业公司；无法确认时不猜测。
- 主要业务：公司明确提供、开发或建设的产品与能力；优先使用标题和摘要，避免网页推荐区污染。
- 所属方向：仅根据已经提取的业务描述映射，不根据公司名称猜测。
- 融资阶段：种子、天使、A/B/C 等明确轮次；“新一轮”“两轮”但未披露轮次时保持未知。
- 总部所在地、核心团队所在地：仅提取“总部位于”“团队位于”“headquartered in”等明确陈述，不从媒体 dateline、学校或创始人籍贯推断。
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

## 成熟度门槛与审计

- C 轮及以后、Pre-IPO 和已上市公司不会进入飞书批次。
- `mature_company_exclusions` 用于处理新闻未披露轮次、但已经明确不属于早期 BD 的公司。
- 每家被排除的公司和原因都会写入 GitHub Actions 日志，例如 `[公司情报] 排除 Anthropic：已知成熟公司，不属于当前早期 BD 阶段`。
- 若所有候选都被排除，outbox 会生成空 `batches`，不会退回旧新闻列表绕过门槛。
