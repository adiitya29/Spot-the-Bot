"""Unit tests for Phase 7 bot evaluation harness, metrics, and detector judges."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from apps.bot.decision import should_bot_reply
from apps.bot.llm.fake import FakeLLMClient
from apps.bot.persona import generate_persona
from apps.bot.timing import compute_bot_timings
from scripts.eval_bot import (
    HeuristicDetectorJudge,
    LLMDetectorJudge,
    compute_wasserstein_distance,
    evaluate_variant,
    generate_markdown_report,
)


def test_wasserstein_distance_properties() -> None:
    """Test 1D 1-Wasserstein exact calculation across edge cases and known distributions."""
    # Empty sets
    assert compute_wasserstein_distance([], []) == 0.0
    assert compute_wasserstein_distance([1.0, 2.0], []) == 0.0
    assert compute_wasserstein_distance([], [3.0, 4.0]) == 0.0

    # Single identical value
    assert compute_wasserstein_distance([5.0], [5.0]) == 0.0

    # Shifted point mass: W1(delta_a, delta_b) = |a - b|
    assert compute_wasserstein_distance([0.0], [10.0]) == 10.0
    assert compute_wasserstein_distance([2.5], [-1.5]) == 4.0

    # Symmetric shift: W1(U, V) = W1(V, U)
    u = [1.0, 2.0, 3.0]
    v = [2.0, 3.0, 4.0]
    w_uv = compute_wasserstein_distance(u, v)
    w_vu = compute_wasserstein_distance(v, u)
    assert w_uv == 1.0
    assert w_vu == 1.0

    # Scale invariance on constant offset
    u_shifted = [x + 5.0 for x in u]
    v_shifted = [x + 5.0 for x in v]
    assert compute_wasserstein_distance(u_shifted, v_shifted) == 1.0


def test_heuristic_detector_judge_empty_and_single() -> None:
    """Test heuristic judge edge cases with empty or single participant transcripts."""
    judge = HeuristicDetectorJudge()

    # Empty transcript
    empty_pred = judge.predict_bot({})
    assert empty_pred.predicted_bot_alias == ""
    assert empty_pred.confidence == 0.0

    # Single participant
    single_pred = judge.predict_bot(
        {
            "participants": [{"alias": "Lone Wolf"}],
            "messages": [],
        }
    )
    assert single_pred.predicted_bot_alias == "Lone Wolf"
    assert single_pred.confidence == 1.0


def test_heuristic_detector_judge_detection_signals() -> None:
    """Test that formal punctuation, uniform length, and low slang trigger suspicion."""
    judge = HeuristicDetectorJudge()

    transcript: dict[str, Any] = {
        "participants": [
            {"alias": "Casual Otter"},
            {"alias": "Slangy Fox"},
            {"alias": "Formal Bot"},
        ],
        "answers": [
            {"alias": "Casual Otter", "text": "cold pizza lol"},
            {"alias": "Slangy Fox", "text": "nah fr waking up early"},
            {
                "alias": "Formal Bot",
                "text": "Personally I believe that pineapple does not belong on traditional pizza.",
            },
        ],
        "messages": [
            # Casual Otter: high slang, varying length, no trailing periods
            {"alias": "Casual Otter", "text": "lol same", "latency_ms": 2000},
            {"alias": "Casual Otter", "text": "wait what haha", "latency_ms": 3000},
            {"alias": "Casual Otter", "text": "fr that's crazy though", "latency_ms": 4000},
            # Slangy Fox: short fragments, slang
            {"alias": "Slangy Fox", "text": "lmao nah", "latency_ms": 1500},
            {"alias": "Slangy Fox", "text": "idk honestly", "latency_ms": 2500},
            {"alias": "Slangy Fox", "text": "tbh me too", "latency_ms": 3500},
            # Formal Bot: strict capitalization, trailing periods, zero slang, uniform lengths
            {
                "alias": "Formal Bot",
                "text": "I certainly understand that perspective.",
                "latency_ms": 3200,
            },
            {
                "alias": "Formal Bot",
                "text": "However that is not my experience.",
                "latency_ms": 3100,
            },
            {
                "alias": "Formal Bot",
                "text": "We should consider alternative viewpoints.",
                "latency_ms": 3300,
            },
        ],
    }

    prediction = judge.predict_bot(transcript)
    assert prediction.predicted_bot_alias == "Formal Bot"
    assert prediction.confidence > 0.40
    assert "Formal Bot" in prediction.seat_probabilities
    # Probabilities should sum to approximately 1.0
    total_prob = sum(prediction.seat_probabilities.values())
    assert abs(total_prob - 1.0) < 0.05
    assert (
        "formal punctuation" in prediction.reasoning
        or "uniform message length" in prediction.reasoning
        or "low colloquial" in prediction.reasoning
    )


def test_llm_detector_judge_fake_client_fallback() -> None:
    """Test LLMDetectorJudge gracefully falls back to heuristic scoring with FakeLLMClient."""
    fake_client = FakeLLMClient()
    judge = LLMDetectorJudge(client=fake_client)

    transcript: dict[str, Any] = {
        "participants": [{"alias": "Teal Otter"}, {"alias": "Ruby Falcon"}],
        "answers": [],
        "messages": [
            {"alias": "Teal Otter", "text": "lol same fr", "latency_ms": 2000},
            {"alias": "Ruby Falcon", "text": "Indeed I agree fully.", "latency_ms": 2000},
        ],
    }

    prediction = judge.predict_bot(transcript)
    assert prediction.predicted_bot_alias in ("Teal Otter", "Ruby Falcon")
    assert 0.0 <= prediction.confidence <= 1.0


def test_variant_routing_persona_and_timings() -> None:
    """Verify variant parameter biases archetypes and tunes CPM bounds."""
    rng = random.Random(42)

    # terse_casual biases to chill_casual or distracted_witty
    terse_personas = [
        generate_persona("funny topic", variant="terse_casual", rng=rng) for _ in range(10)
    ]
    terse_archetypes = {p["archetype"] for p in terse_personas}
    assert terse_archetypes.issubset({"chill_casual", "distracted_witty"})

    # chatty_banterer biases to skeptical_critic or enthusiastic_agreeable
    banter_personas = [
        generate_persona("opinion topic", variant="chatty_banterer", rng=rng) for _ in range(10)
    ]
    banter_archetypes = {p["archetype"] for p in banter_personas}
    assert banter_archetypes.issubset({"skeptical_critic", "enthusiastic_agreeable"})

    # Timing bounds: terse_casual CPM is 240-360
    terse_timing = compute_bot_timings(
        len("incoming"), "short text", variant="terse_casual", rng=rng
    )
    assert 0.4 <= terse_timing.read_delay_seconds <= 1.5

    # Cooldowns: terse is 4s, banterer is 2s, baseline is 3s
    now = datetime(2026, 11, 13, 12, 0, 5)
    last_bot_msg = datetime(2026, 11, 13, 12, 0, 1, 500000)  # 3.5s ago

    # With 3.5s elapsed, terse (4s cooldown) should not reply
    terse_should = should_bot_reply(
        last_bot_message_at=last_bot_msg,
        variant="terse_casual",
        clock=lambda: now,
        rng=rng,
    )
    assert not terse_should

    # Banterer (2s cooldown) with 3.5s elapsed should consider replying
    banter_should = should_bot_reply(
        last_bot_message_at=last_bot_msg,
        variant="chatty_banterer",
        clock=lambda: now,
        rng=random.Random(1),
    )
    assert banter_should


def test_evaluate_variant_batch_and_report_generation(tmp_path: Any) -> None:
    """Verify evaluate_variant runs simulation rounds and produces valid markdown report."""
    summary = evaluate_variant("terse_casual", num_rounds=3, seed=123)

    assert summary.variant == "terse_casual"
    assert summary.rounds_evaluated == 3
    assert 0.0 <= summary.detector_accuracy <= 1.0
    assert summary.bot_survival_rate == round(1.0 - summary.detector_accuracy, 4)
    assert summary.mean_length_w1_words >= 0.0
    assert summary.mean_latency_w1_sec >= 0.0
    assert len(summary.round_details) == 3

    # Generate markdown report
    report_file = tmp_path / "test_variant_report.md"
    generate_markdown_report([summary], report_file, seed=123)

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# Bot Variant Evaluation & Tuning Report" in content
    assert "terse_casual" in content
    assert "Executive Summary" in content
    assert "1-Wasserstein Distance" in content
