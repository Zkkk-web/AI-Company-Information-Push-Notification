import unittest
from pathlib import Path

import yaml

from trendradar.core.frequency import load_frequency_words, matches_word_groups


class StartupIntelligenceRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_frequency_words("config/frequency_words.txt")

    def assertMatches(self, title):
        self.assertTrue(matches_word_groups(title, *self.rules), title)

    def assertDoesNotMatch(self, title):
        self.assertFalse(matches_word_groups(title, *self.rules), title)

    def test_representative_titles(self):
        for title in (
            "AI SaaS 公司完成 800 万元天使轮融资，红杉参与",
            "AI 智能硬件公司获红杉投资，金额未披露",
            "前字节 VP 创办 AI 陪伴产品新公司",
            "AI startup raises $1.5M seed funding",
        ):
            with self.subTest(title=title):
                self.assertMatches(title)

        for title in (
            "某餐饮公司完成 800 万元融资",
            "AI 公司完成 500 万元融资",
            "AI startup raises $500K seed funding",
            "某基金完成百亿基金募资",
        ):
            with self.subTest(title=title):
                self.assertDoesNotMatch(title)

    def test_source_coverage(self):
        with open("config/config.yaml", encoding="utf-8") as config_file:
            feeds = yaml.safe_load(config_file)["rss"]["feeds"]

        feed_ids = {feed["id"] for feed in feeds}
        active_feeds = [feed for feed in feeds if feed.get("enabled", True)]
        self.assertEqual(len(feeds), len(feed_ids), "RSS feed IDs must be unique")
        self.assertGreaterEqual(len(active_feeds), 16)
        self.assertTrue(
            {
                "36kr-articles",
                "qbitai",
                "geekpark",
                "tmtpost",
                "leiphone",
                "techcrunch-venture",
                "crunchbase-news",
                "sifted",
                "the-decoder",
                "siliconangle-ai",
                "aihot-selected",
                "google-news-cn-ai-funding",
                "google-news-cn-vc-watch",
                "google-news-cn-executive-moves",
                "google-news-global-ai-funding",
            }.issubset(feed_ids)
        )
        staged_wechat_ids = {
            "wechat-zhenfund",
            "wechat-sourcecode-capital",
            "wechat-qiming-venture",
            "wechat-frees-fund",
            "wechat-bluerun-ventures",
            "wechat-gaorong-ventures",
            "wechat-linear-capital",
            "wechat-vitalbridge",
        }
        self.assertTrue(staged_wechat_ids.issubset(feed_ids))
        self.assertTrue(
            all(not feed.get("enabled", True) for feed in feeds if feed["id"] in staged_wechat_ids)
        )

    def test_production_workflow_exports_outbox_without_old_webhook(self):
        workflow = Path(".github/workflows/crawler.yml").read_text(encoding="utf-8")
        self.assertIn("FEISHU_OUTBOX_PATH", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("retention-days: 3", workflow)
        self.assertNotIn("secrets.FEISHU_WEBHOOK_URL", workflow)
        self.assertNotIn("schedule:", workflow)

    def test_production_enables_company_centric_feishu_delivery(self):
        with open("config/config.yaml", encoding="utf-8") as config_file:
            feishu = yaml.safe_load(config_file)["notification"]["channels"]["feishu"]

        self.assertTrue(feishu["company_intelligence"])
        self.assertTrue(feishu["fetch_article_text"])
        self.assertIn("Anthropic", feishu["mature_company_exclusions"])
        self.assertIn("DeepSeek", feishu["mature_company_exclusions"])


if __name__ == "__main__":
    unittest.main()
