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


if __name__ == "__main__":
    unittest.main()
