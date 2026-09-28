from __future__ import annotations

from io import BytesIO
import json
import unittest
from unittest.mock import patch

from src.link_arena.agents import OpenAICompatibleAgent
from tools.analyze_link_arena_benchmark import _estimate_chutes_cost_usd


class LinkArenaCostTests(unittest.TestCase):
    def test_chutes_catalog_snapshot_captures_rates_and_hashes(self):
        catalog = {
            "object": "list",
            "data": [{
                "id": "zai-org/GLM-5.1-TEE",
                "root": "zai-org/GLM-5.1-FP8",
                "price": {
                    "input": {"usd": 0.98},
                    "output": {"usd": 3.08},
                    "input_cache_read": {"usd": 0.098},
                },
                "confidential_compute": True,
                "chute_id": "fixture-chute",
            }],
        }
        response = BytesIO(json.dumps(catalog).encode("utf-8"))
        with patch("src.link_arena.agents.urlopen", return_value=response) as open_url:
            agent = OpenAICompatibleAgent(
                "A", provider="chutes", model="zai-org/GLM-5.1-TEE",
            )
        open_url.assert_called_once()
        snapshot = agent.benchmark_metadata()["pricing_snapshot"]
        self.assertEqual(snapshot["status"], "captured")
        self.assertEqual(snapshot["rates_per_million_tokens"], {
            "input": 0.98, "output": 3.08, "cached_input": 0.098,
        })
        self.assertTrue(snapshot["confidential_compute"])
        self.assertEqual(len(snapshot["catalog_sha256"]), 64)
        self.assertEqual(len(snapshot["model_record_sha256"]), 64)

    def test_cost_uses_reported_cached_input_tokens(self):
        inference = {
            "provider": "chutes",
            "model_requested": "zai-org/GLM-5.1-TEE",
            "model_resolved": "zai-org/GLM-5.1-TEE",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 1000,
                "prompt_tokens_details": {"cached_tokens": 400},
            },
        }
        pricing = {
            "status": "captured",
            "model_id": "zai-org/GLM-5.1-TEE",
            "rates_per_million_tokens": {
                "input": 0.98, "output": 3.08, "cached_input": 0.098,
            },
        }
        cost, basis = _estimate_chutes_cost_usd(inference, pricing)
        self.assertAlmostEqual(cost, 0.0037072)
        self.assertEqual(basis, "catalog_rate_with_reported_cache_usage")

    def test_missing_cache_breakdown_is_labeled_upper_bound(self):
        inference = {
            "provider": "chutes",
            "model_requested": "fixture-model",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
        }
        pricing = {
            "status": "captured",
            "model_id": "fixture-model",
            "rates_per_million_tokens": {
                "input": 1.0, "output": 2.0, "cached_input": 0.1,
            },
        }
        cost, basis = _estimate_chutes_cost_usd(inference, pricing)
        self.assertAlmostEqual(cost, 0.003)
        self.assertEqual(basis, "uncached_rate_upper_bound_cache_usage_unreported")

    def test_minimax_subscription_is_not_misreported_as_per_token_usd(self):
        inference = {
            "provider": "minimax-api",
            "model_requested": "MiniMax-M3.1-Flash-Preview",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
        }
        cost, basis = _estimate_chutes_cost_usd(inference, {
            "status": "account_billing_not_snapshotted",
        })
        self.assertIsNone(cost)
        self.assertEqual(basis, "no_per_request_usd_rate")

    def test_previously_frozen_snapshot_avoids_catalog_refetch(self):
        frozen = {"status": "captured", "model_id": "fixture-model"}
        with patch.object(
            OpenAICompatibleAgent, "_capture_pricing_snapshot",
            side_effect=AssertionError("frozen snapshot should be reused"),
        ):
            agent = OpenAICompatibleAgent(
                "A", provider="chutes", model="fixture-model",
                pricing_snapshot=frozen,
            )
        self.assertEqual(agent.benchmark_metadata()["pricing_snapshot"], frozen)

    def test_missing_rates_cannot_produce_a_cost_estimate(self):
        inference = {
            "provider": "chutes",
            "model_requested": "fixture-model",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
        }
        cost, basis = _estimate_chutes_cost_usd(inference, {
            "status": "price_fields_missing",
            "model_id": "fixture-model",
        })
        self.assertIsNone(cost)
        self.assertEqual(basis, "missing_frozen_price_snapshot")


if __name__ == "__main__":
    unittest.main()
