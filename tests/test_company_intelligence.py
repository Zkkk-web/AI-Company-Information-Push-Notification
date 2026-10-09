import unittest

from trendradar.intelligence.company import (
    build_company_intelligence_batches,
    extract_readable_text,
    extract_company_signal,
    merge_company_signals,
)


class CompanyIntelligenceTest(unittest.TestCase):
    def test_extracts_english_company_investor_and_event(self):
        signal = extract_company_signal(
            {
                "title": "Robot data startup Mecka AI nabs $60M from Sequoia",
                "summary": "Mecka AI raised a $60 million round from Sequoia Capital.",
                "source_name": "TechCrunch Venture",
                "url": "https://example.com/mecka",
            },
            "A级·重点机构投资",
        )

        self.assertEqual(signal.company_name, "Mecka AI")
        self.assertIn("红杉资本 / Sequoia", signal.investors)
        self.assertIn("$60M", signal.event)
        self.assertEqual(signal.team, [])

    def test_extracts_chinese_company_investor_and_team_with_evidence(self):
        signal = extract_company_signal(
            {
                "title": "清华 AIR 首届博士李健雄创立本溯智能：五源资本领投",
                "summary": "李健雄创立具身智能公司本溯智能，五源资本领投本轮融资。",
                "source_name": "雷峰网",
                "url": "https://example.com/bensu",
            },
            "A级·重点机构投资",
        )

        self.assertEqual(signal.company_name, "本溯智能")
        self.assertIn("五源资本", signal.investors)
        self.assertTrue(any("李健雄" in member for member in signal.team))
        self.assertTrue(any("清华 AIR" in member for member in signal.team))

    def test_merges_same_company_event_and_keeps_all_sources(self):
        first = extract_company_signal(
            {
                "title": "Arena 获 Lightspeed 领投 2 亿美元 B 轮融资",
                "summary": "",
                "source_name": "AIHOT 精选",
                "url": "https://example.com/arena-1",
            },
            "A级·重点机构投资",
        )
        second = extract_company_signal(
            {
                "title": "AI评测榜单Arena宣布融资2亿美元：Lightspeed领投",
                "summary": "",
                "source_name": "新浪网",
                "url": "https://example.com/arena-2",
            },
            "A级·融资达标",
        )

        merged = merge_company_signals([first, second])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].company_name, "Arena")
        self.assertEqual(len(merged[0].sources), 2)
        self.assertIn("Lightspeed", merged[0].investors)

    def test_renders_company_fields_without_unsupported_html(self):
        stats = [
            {
                "word": "A级·重点机构投资",
                "count": 1,
                "titles": [
                    {
                        "title": "Robot data startup Mecka AI nabs $60M from Sequoia",
                        "summary": "",
                        "source_name": "TechCrunch Venture",
                        "url": "https://example.com/mecka",
                        "time_display": "10-09 09:30",
                    }
                ],
            }
        ]

        batches = build_company_intelligence_batches([], stats, batch_size=29000)

        self.assertEqual(len(batches), 1)
        content = batches[0]
        self.assertIn("**公司：** Mecka AI", content)
        self.assertIn("**资方：** 红杉资本 / Sequoia", content)
        self.assertIn("**团队：** 暂未从公开报道确认", content)
        self.assertIn("[TechCrunch Venture](https://example.com/mecka)", content)
        self.assertNotIn("<font", content)

    def test_extracts_company_after_startup_when_investor_leads_title(self):
        signal = extract_company_signal(
            {
                "title": "a16z leads $16M seed for AI data startup Preference Model",
                "summary": "",
                "source_name": "Dealroom",
                "url": "https://example.com/preference-model",
            },
            "A级·重点机构投资",
        )

        self.assertEqual(signal.company_name, "Preference Model")
        self.assertEqual(signal.investors, ["a16z"])

    def test_does_not_treat_founder_phrase_as_company(self):
        signal = extract_company_signal(
            {
                "title": "Cal AI’s 19-year-old founder just raised $10M for his new AI startup",
                "summary": "",
                "source_name": "TechCrunch",
                "url": "https://example.com/cal-ai",
            },
            "A级·融资达标",
        )

        self.assertEqual(signal.company_name, "Cal AI")
        self.assertIn("19 岁创始人（姓名未披露）", signal.team)

    def test_handles_continuous_financing_chinese_company_name(self):
        signal = extract_company_signal(
            {
                "title": "厘清智能连续完成两轮数亿元融资",
                "summary": "",
                "source_name": "泰伯网",
                "url": "https://example.com/liq",
            },
            "A级·融资达标",
        )

        self.assertEqual(signal.company_name, "厘清智能")

    def test_strips_descriptive_startup_prefix_from_company(self):
        signal = extract_company_signal(
            {
                "title": "Engineering AI Startup Vinci Raises $250M",
                "summary": "",
                "source_name": "Wowtale",
                "url": "https://example.com/vinci",
            },
            "A级·融资达标",
        )

        self.assertEqual(signal.company_name, "Vinci")

    def test_merges_multiple_events_for_same_company_card(self):
        financing = extract_company_signal(
            {
                "title": "Manus完成超5亿美元新一轮融资",
                "summary": "",
                "source_name": "财联社",
                "url": "https://example.com/manus-funding",
            },
            "A级·融资达标",
        )
        hiring = extract_company_signal(
            {
                "title": "Manus重启北京办公室大举招聘",
                "summary": "",
                "source_name": "量子位",
                "url": "https://example.com/manus-hiring",
            },
            "B级·新业务或新市场",
        )

        merged = merge_company_signals([financing, hiring])

        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0].sources), 2)

    def test_uses_article_text_only_when_title_and_summary_lack_company(self):
        signal = extract_company_signal(
            {
                "title": "港大教授孔令鹏创业，拿下dLLM模型全球最大融资",
                "summary": "",
                "article_text": "港大教授孔令鹏创立于界智能，公司宣布完成新一轮融资。",
                "source_name": "36氪",
                "url": "https://example.com/kong",
            },
            "A级·融资达标",
        )

        self.assertEqual(signal.company_name, "于界智能")
        self.assertTrue(any("孔令鹏" in member for member in signal.team))

    def test_batch_builder_can_enrich_missing_fields_from_article(self):
        stats = [
            {
                "word": "A级·融资达标",
                "titles": [
                    {
                        "title": "港大教授孔令鹏创业，拿下dLLM模型全球最大融资",
                        "summary": "五源资本领投本轮融资。",
                        "source_name": "36氪",
                        "url": "https://example.com/kong",
                    }
                ],
            }
        ]

        batches = build_company_intelligence_batches(
            [],
            stats,
            fetch_full_text=True,
            article_fetcher=lambda _url: "港大教授孔令鹏创立于界智能，五源资本领投。",
        )

        self.assertIn("**公司：** 于界智能", batches[0])
        self.assertIn("**资方：** 五源资本", batches[0])
        self.assertIn("孔令鹏", batches[0])

    def test_does_not_match_investor_name_inside_unrelated_word(self):
        signal = extract_company_signal(
            {
                "title": "Waymo raises debt to accelerate expansion",
                "summary": "",
                "source_name": "Example",
                "url": "https://example.com/waymo",
            },
            "A级·融资达标",
        )

        self.assertNotIn("Accel", signal.investors)

    def test_article_extraction_prefers_primary_content_over_recommendations(self):
        article = "Mecka AI was founded by Jane Smith. " * 8
        page = (
            "<html><body><main><p>" + article + "</p></main>"
            "<section><p>Recommended: Arena was funded by a16z.</p></section>"
            "</body></html>"
        )

        text = extract_readable_text(page)

        self.assertIn("Jane Smith", text)
        self.assertNotIn("Recommended", text)


if __name__ == "__main__":
    unittest.main()
