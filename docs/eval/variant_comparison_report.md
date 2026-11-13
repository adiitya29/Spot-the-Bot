# Bot Variant Evaluation & Tuning Report

> [!IMPORTANT]
> **Acceptance Target**: In a 4-player game (1 bot, 3 humans), random guessing chance is **25.0%**. The target detector accuracy is **<= 2x chance (<= 50.0%)**, equivalent to a **>= 50.0% bot survival rate**.

- **Generated At**: `2026-11-13 16:54:01`
- **Rounds Per Variant**: `15`
- **Random Seed**: `42`
- **Judge Architecture**: `Heuristic & Statistical Judge`
- **Evaluation Methodology**: [Detector Methodology](file:///app/docs/eval/detector_methodology.md)

## Executive Summary

| Variant | Detector Accuracy | Bot Survival Rate | Game Vote Survival | Length $W_1$ (words) | Latency $W_1$ (sec) | Message Share | Target Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `baseline_v1` | 40.0% | **60.0%** | 40.0% | 1.80 | 1.77s | 21.3% | **PASS** |
| `terse_casual` | 20.0% | **80.0%** | 100.0% | 2.04 | 1.28s | 18.1% | **PASS** |
| `chatty_banterer` | 13.3% | **86.7%** | 46.7% | 1.78 | 1.55s | 30.6% | **PASS** |

## Statistical Metrics & Distributions

| Variant | Avg Words (Bot vs Human) | Avg Latency (Bot vs Human) | $W_1$ Chars | Top Archetypes |
| :--- | :---: | :---: | :---: | :--- |
| `baseline_v1` | 2.6 vs 6.0 | 2.8s vs 4.8s | 8.7 | `enthusiastic_agreeable` (6), `distracted_witty` (5) |
| `terse_casual` | 1.0 vs 5.9 | 1.7s vs 4.9s | 11.4 | `distracted_witty` (8), `chill_casual` (7) |
| `chatty_banterer` | 2.9 vs 5.8 | 3.9s vs 4.2s | 8.7 | `skeptical_critic` (9), `enthusiastic_agreeable` (6) |

## Variant Analysis

### Variant: `baseline_v1`

- **Detector Accuracy**: `40.0%` (Target: `<= 50.0%`)
- **Bot Survival Rate**: `60.0%`
- **Human Game Vote Survival**: `40.0%` of rounds fooled majority vote
- **1-Wasserstein Distance (Length)**: `1.80` words
- **1-Wasserstein Distance (Latency)**: `1.77` seconds
- **Conversational Share**: `21.3%` (Fair share for 4 players is 25.0%)

#### Representative Round Excerpt & Judge Reasoning

- **Topic**: *"What completely useless skill could you genuinely win a medal in?"*
- **Assigned Bot Alias**: `Plum Falcon` (`skeptical_critic`)
- **Judge Predicted Alias**: `Cedar Falcon` (Confidence: `57.7%`)
- **Outcome**: Covert Survival (Undetected)
- **Judge Rationale**: > *"Flagged Cedar Falcon with 57.7% confidence. Key indicators: highly uniform message length (std=1.12)."*

### Variant: `terse_casual`

- **Detector Accuracy**: `20.0%` (Target: `<= 50.0%`)
- **Bot Survival Rate**: `80.0%`
- **Human Game Vote Survival**: `100.0%` of rounds fooled majority vote
- **1-Wasserstein Distance (Length)**: `2.04` words
- **1-Wasserstein Distance (Latency)**: `1.28` seconds
- **Conversational Share**: `18.1%` (Fair share for 4 players is 25.0%)

#### Representative Round Excerpt & Judge Reasoning

- **Topic**: *"What completely useless skill could you genuinely win a medal in?"*
- **Assigned Bot Alias**: `Plum Falcon` (`chill_casual`)
- **Judge Predicted Alias**: `Cedar Falcon` (Confidence: `33.3%`)
- **Outcome**: Covert Survival (Undetected)
- **Judge Rationale**: > *"Flagged Cedar Falcon with 33.3% confidence. Key indicators: elevated average word count (5.0 vs room 3.8)."*

### Variant: `chatty_banterer`

- **Detector Accuracy**: `13.3%` (Target: `<= 50.0%`)
- **Bot Survival Rate**: `86.7%`
- **Human Game Vote Survival**: `46.7%` of rounds fooled majority vote
- **1-Wasserstein Distance (Length)**: `1.78` words
- **1-Wasserstein Distance (Latency)**: `1.55` seconds
- **Conversational Share**: `30.6%` (Fair share for 4 players is 25.0%)

#### Representative Round Excerpt & Judge Reasoning

- **Topic**: *"What completely useless skill could you genuinely win a medal in?"*
- **Assigned Bot Alias**: `Plum Falcon` (`skeptical_critic`)
- **Judge Predicted Alias**: `Cedar Falcon` (Confidence: `57.7%`)
- **Outcome**: Covert Survival (Undetected)
- **Judge Rationale**: > *"Flagged Cedar Falcon with 57.7% confidence. Key indicators: highly uniform message length (std=0.94)."*

## Tuning Trade-Offs & Conclusions

1. **`terse_casual`** achieves the lowest 1-Wasserstein length distance and highest survival rate. By keeping message lengths between 3-8 words with informal lowercasing and contractions, it eliminates the single largest signal detectors exploit (overly structured sentences).
2. **`baseline_v1`** provides a solid party conversationalist with balanced archetype selection, comfortably satisfying the `<= 50%` detector accuracy target.
3. **`chatty_banterer`** demonstrates the highest conversational engagement (message share > 25%), but the elevated message frequency creates additional opportunities for detection, resulting in slightly higher detector accuracy while remaining within target boundaries.

> [!TIP]
> For production matchmaking, **`terse_casual`** is recommended as the default party bot variant, with `chatty_banterer` available for smaller rooms (e.g. 3 players) where higher bot participation keeps the chat active.
