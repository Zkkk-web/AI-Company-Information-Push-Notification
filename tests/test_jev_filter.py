import unittest

from trendradar.ai.filter_pipeline import AIFilterPipeline
from trendradar.ai.jev_filter import (
    CHOICE_CRITERIA,
    NO_MATCH,
    SIGNAL_CHOICES,
    JevFilter,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 400

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def make_answer(choice, probability=0.8, confidence=0.9):
    remaining = (1 - probability) / (len(CHOICE_CRITERIA) - 1)
    probabilities = {key: remaining for key in CHOICE_CRITERIA}
    probabilities[choice] = probability
    return {
        "choice": choice,
        "probabilities": probabilities,
        "confidence": confidence,
    }


class JevFilterTest(unittest.TestCase):
    def setUp(self):
        self.tags = [
            {"id": index, "tag": value["tag"]}
            for index, value in enumerate(SIGNAL_CHOICES.values(), start=11)
        ]

    def build_filter(self, payload, **overrides):
        config = {
            "API_KEY": "test-key",
            "MODEL": "jev-latest",
            "MIN_SCORE": 0.75,
            "MAX_SUMMARY_CHARS": 100,
            **overrides,
        }
        session = FakeSession([FakeResponse(payload)])
        return JevFilter(config, session=session), session

    def test_valid_choice_maps_to_existing_tag(self):
        payload = {
            "model": "jev-latest",
            "answers": {"article_0": make_answer("A_FINANCING")},
        }
        jev_filter, session = self.build_filter(payload)

        result = jev_filter.classify_batch(
            [
                {
                    "id": 7,
                    "title": "AI SaaS 公司完成 800 万元融资",
                    "summary": "<p>本轮融资将用于产品研发。</p>",
                    "source": "测试媒体",
                    "url": "https://example.com/story",
                }
            ],
            self.tags,
        )

        self.assertEqual(
            result,
            [{"news_item_id": 7, "tag_id": 12, "relevance_score": 0.8}],
        )
        request_body = session.calls[0][1]["json"]
        article = request_body["state"]["articles"][0]
        self.assertEqual(article["summary"], "本轮融资将用于产品研发。")
        self.assertEqual(article["source"], "测试媒体")
        self.assertEqual(article["url"], "https://example.com/story")
        self.assertEqual(
            set(request_body["questions"]["article_0"]["criteria"]),
            set(CHOICE_CRITERIA),
        )

    def test_no_match_is_successful_empty_result(self):
        payload = {"answers": {"article_0": make_answer(NO_MATCH)}}
        jev_filter, _ = self.build_filter(payload)
        result = jev_filter.classify_batch(
            [{"id": 1, "title": "某基金完成百亿基金募集"}], self.tags
        )
        self.assertEqual(result, [])

    def test_low_confidence_match_is_not_pushed(self):
        payload = {
            "answers": {
                "article_0": make_answer(
                    "B_NEW_BUSINESS", probability=0.7, confidence=0.7
                )
            }
        }
        jev_filter, _ = self.build_filter(payload)
        result = jev_filter.classify_batch(
            [{"id": 2, "title": "AI 公司进军海外市场"}], self.tags
        )
        self.assertEqual(result, [])

    def test_invalid_distribution_retries_on_next_run(self):
        invalid = make_answer("A_FINANCING")
        invalid["probabilities"].pop(NO_MATCH)
        payload = {"answers": {"article_0": invalid}}
        jev_filter, _ = self.build_filter(payload)
        result = jev_filter.classify_batch(
            [{"id": 3, "title": "AI 公司融资"}], self.tags
        )
        self.assertIsNone(result)

    def test_missing_key_does_not_call_api(self):
        session = FakeSession([])
        jev_filter = JevFilter({"API_KEY": ""}, session=session)
        result = jev_filter.classify_batch(
            [{"id": 4, "title": "AI 公司融资"}], self.tags
        )
        self.assertIsNone(result)
        self.assertEqual(session.calls, [])

    def test_tag_update_replaces_generic_tags(self):
        jev_filter = JevFilter({"API_KEY": "test-key"})
        result = jev_filter.update_tags(
            [{"id": 1, "tag": "旧的生成式标签"}], "unused"
        )
        self.assertEqual(result["remove"], ["旧的生成式标签"])
        self.assertEqual(len(result["add"]), 4)
        self.assertEqual(result["change_ratio"], 1.0)


class ClassifierInputPipelineTest(unittest.TestCase):
    def test_rss_summary_and_url_reach_classifier(self):
        pipeline = AIFilterPipeline(
            {
                "FILTER": {"METHOD": "jev"},
                "JEV_FILTER": {"BATCH_SIZE": 10, "BATCH_INTERVAL": 0},
                "RSS": {"ENABLED": True, "FEEDS": []},
            },
            storage_manager=object(),
            get_time_func=lambda: None,
        )

        class RecordingClassifier:
            def __init__(self):
                self.received = None

            def classify_batch(self, titles, _tags, _interests):
                self.received = titles
                return []

        classifier = RecordingClassifier()
        pipeline._classify_batches(
            classifier,
            pending_news=[],
            pending_rss=[
                {
                    "id": 9,
                    "title": "测试标题",
                    "source_name": "测试来源",
                    "url": "https://example.com/9",
                    "summary": "摘要证据",
                }
            ],
            active_tags=[],
            interests_content="",
            filter_config={"BATCH_SIZE": 10, "BATCH_INTERVAL": 0},
        )

        self.assertEqual(classifier.received[0]["summary"], "摘要证据")
        self.assertEqual(classifier.received[0]["url"], "https://example.com/9")


if __name__ == "__main__":
    unittest.main()
