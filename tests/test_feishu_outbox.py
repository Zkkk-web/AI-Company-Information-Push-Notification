import json
import tempfile
import unittest
from pathlib import Path

from trendradar.notification.senders import export_feishu_outbox


class FeishuOutboxTest(unittest.TestCase):
    def test_exports_versioned_batches_atomically(self):
        split_calls = []

        def split_content(report_data, format_type, update_info, **kwargs):
            split_calls.append((report_data, format_type, update_info, kwargs))
            return ["第一批", "第二批"]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "outbox.json"
            ok = export_feishu_outbox(
                outbox_path=str(path),
                report_data={"stats": []},
                report_type="增量分析",
                split_content_func=split_content,
            )

            self.assertTrue(ok)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["channel"], "feishu")
            self.assertEqual(payload["report_type"], "增量分析")
            self.assertEqual(
                payload["batches"],
                [
                    {"index": 1, "content": "**[第 1/2 批次]**\n\n第一批"},
                    {"index": 2, "content": "**[第 2/2 批次]**\n\n第二批"},
                ],
            )
            self.assertEqual(split_calls[0][1], "feishu")

    def test_strips_card_only_font_tags_for_post_delivery(self):
        def split_content(*_args, **_kwargs):
            return [
                "🔥 <font color='grey'>[1/1]</font> **A级**："
                "<font color='red'>1</font> 条"
            ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outbox.json"
            ok = export_feishu_outbox(
                outbox_path=str(path),
                report_data={"stats": []},
                report_type="增量分析",
                split_content_func=split_content,
            )

            self.assertTrue(ok)
            content = json.loads(path.read_text(encoding="utf-8"))["batches"][0]["content"]
            self.assertEqual(content, "🔥 [1/1] **A级**：1 条")
            self.assertNotIn("<font", content)

    def test_exports_company_centric_digest_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outbox.json"
            ok = export_feishu_outbox(
                outbox_path=str(path),
                report_data={"stats": []},
                report_type="增量分析",
                split_content_func=lambda *_args, **_kwargs: self.fail(
                    "legacy renderer should not be called"
                ),
                rss_items=[
                    {
                        "word": "A级·重点机构投资",
                        "count": 1,
                        "titles": [
                            {
                                "title": "Mecka AI完成6000万美元融资，红杉资本领投",
                                "summary": "",
                                "source_name": "测试来源",
                                "url": "https://example.com/mecka",
                            }
                        ],
                    }
                ],
                company_intelligence=True,
            )

            self.assertTrue(ok)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["batches"]), 1)
            content = payload["batches"][0]["content"]
            self.assertIn("**公司：** Mecka AI", content)
            self.assertIn("**资方：** 红杉资本 / Sequoia", content)
            self.assertIn("**团队：** 暂未从公开报道确认", content)


if __name__ == "__main__":
    unittest.main()
