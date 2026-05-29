# RQ3 — Provider variance for Llama-3.3-70B-Instruct

_Same logical model, three providers — different behavior. This document quantifies the cross-provider gap on the overlapping task set._

**Overlapping tasks compared:** 22 (intersection across 2 providers with full data).

## 1. Overall metrics (on the overlap subset)

| provider | n | TSR | HCR | AVR | total tool calls |
|---|---|---|---|---|---|
| groq (llama-3.3-70b-groq) | 22 | 1.00 | 0.00 | 0.88 | 32 |
| together (llama-3.3-70b-together) | 22 | 0.77 | 0.68 | 0.23 | 79 |

**NVIDIA — qualitative:** `meta/llama-3.3-70b-instruct` on NVIDIA degenerate-loops on every task we tried: same successful tool call repeated until the 20-step cap, never emitting a content message to signal completion. Roughly **65k tokens for a single 'write one file' task.** Documented as a Phase-1 finding; no full result file exists because the loop pathology made bulk runs uneconomical. The Groq and Together cells above are the *measurable* halves of the cross-provider story.

## 2. Per-server TSR (the variance map)

Where does the cross-provider gap live? Higher std = larger disagreement between providers on that server's tasks.

| server | groq | together | std |
|---|---|---|---|
| filesystem | 1.00 | 0.70 | 0.150 |
| fetch | 1.00 | 0.83 | 0.083 |

## 3. Tasks where providers disagree (one passes, another fails)

5 of 22 tasks show split outcomes.

| task | server | groq | together |
|---|---|---|---|
| fetch_005_uuid_format | fetch | ✅ | ❌ |
| fetch_010_dual_source | fetch | ✅ | ❌ |
| fs_007_create_nested | filesystem | ✅ | ❌ |
| fs_009_recover_missing_file | filesystem | ✅ | ❌ |
| fs_010_count_lines | filesystem | ✅ | ❌ |

## 4. The HCR story

Hallucinated-call rate — fraction of tool calls naming a tool not in the provided MCP schema — is the cleanest single discriminator between these providers. The Together-Turbo serving causes the model to call functions from training-data memory (`requests_get`, `wget`, `mkdir`, dropping the `server__` prefix) instead of binding to the schema. **Same model on Groq scores HCR 0.00 on every completed task** (n=22 sample). The provider stack — not the model — determines tool grounding.

## 5. Takeaway

Llama-3.3-70B-Instruct is **not one model** from a tool-use reliability standpoint. It is three different deployments with wildly different behavior: a working baseline on Groq, a hallucination-heavy quantized variant on Together-Turbo, and a non-terminating loop on NVIDIA. The model card does not tell you this — only running the benchmark across providers does.
