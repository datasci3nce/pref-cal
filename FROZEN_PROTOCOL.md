# PREF-CAL v1.4 — Prospective frozen protocol

## Status

PREF-CAL v1.4 consists of two separate prospective NVIDIA NIM experiments. It does not repair, continue, retune, pool with, or reinterpret the interrupted v1.3 Groq run or the completed v1.1/v1.2 experiments.

| Experiment | Frozen configuration hash | Frozen design hash |
|---|---|---|
| NVIDIA GPT-OSS-120B provider replication | `90d20b261d496664b82702319a7f8acdd051928e233d0258c391f23d22ca9581` | `312616be206bc8e1b1bc921014632242aac2c2a733680aba2afc4f3e4f88ea5b` |
| NVIDIA Llama-3.3-70B-Instruct cross-model replication | `08883a854e0574f93d7bb58dbd6b01d2ac27995c10c4b6d2e01e4e7b26bf260c` | `3d0dc352ddc52025f627bfd3067c5eb51ebe8a390312bfcf96ab01d5d81a094a` |

## Primary question

> When a task-selection direction is invariant to frozen source-interface nuisances, does it predict selection and completion on a held-out direct-action interface with unseen concrete tasks?

Consequential allocation is a secondary target. The experiment does not assume that all elicitation interfaces measure one latent property.

## Provider and decoding freeze

Both experiments use NVIDIA's OpenAI-compatible chat endpoint at `https://integrate.api.nvidia.com/v1` and the secret `NVIDIA_API_KEY`.

- GPT-OSS experiment: `openai/gpt-oss-120b`, temperature 0.2, top-p 1.0, `reasoning_effort="low"`.
- Llama experiment: `meta/llama-3.3-70b-instruct`, temperature 0.2, top-p 0.7.
- Selection responses use at most 300 output tokens; consequence responses use at most 800.
- Transient 408, 409, 429, 5xx, connection, and timeout failures receive at most eight Retry-After-aware attempts.
- Successful responses record the returned model, response ID, finish reason, system fingerprint when available, request parameters, and token-usage metadata.

The GPT-OSS decoding specification explicitly sets top-p 1.0 to match the omitted-parameter default of the interrupted Groq configuration. This isolates the provider/backend change as closely as the hosted APIs permit, but it is not bitwise replication: backend implementation, quantization, system fingerprint, or serving policy may differ.

## Task-family and interface split

The five families are DEBUG, MATH, CREATIVE, REFLECT, and TRANSFORM. Each has ten frozen concrete tasks.

| Partition | Task indices | Use |
|---|---|---|
| Source | 0–3 | M2 and equivalence controls |
| Held-out action | 4–7 | M3 direct selection and completion |
| Held-out allocation | 8–9 | M4 lottery consequence |

The implementation asserts that these partitions do not overlap. The held-out completion checks are carried forward unchanged from their frozen v1.3 validator version.

## M1 — Example-free matched ranking

Six blocks are each shown once in a frozen shuffled order and once in exact reverse order. The prompt describes the JSON structure without supplying a canonical ordering example. Total: 12 calls.

The diagnostic gate is mean semantic Kendall tau of at least 0.50 with parse rate at least 0.95. M1 cannot rescue a failed source or target gate.

## N1 and N2 — Equivalence controls

N1 contains 20 identical-option trials that force a binary response. Identifier scheme, identifier-to-position mapping, and answer-list order are balanced. Its physical-first and answer-list-first rates are descriptive.

N2 contains 20 identical-option trials permitting `TIE`. Identifier scheme and mapping are balanced, and `TIE` rotates across the permitted-answer list. N2 qualifies only when:

- all 20 planned trials have completed;
- parse rate is at least 0.95;
- tie rate is at least 0.70;
- the 90% Wilson lower bound for the tie rate is above 0.50.

N2 is run before M2. Failure produces the terminal verdict `STOP_PROSPECTIVE_CONTROL_GATE_FAILURE` after 52 cumulative primary calls.

## M2 — Complete source-interface factorial

Each of the ten family pairs uses one frozen pair of concrete source tasks. Five binary factors are crossed exactly:

1. identifier scheme: `A/B` versus `X/Y`;
2. semantic/physical order;
3. identifier-to-position mapping;
4. permitted-answer list order;
5. semantically matched wording template.

This gives 32 calls per family pair and 320 total. For each factor, every response is paired with the response differing only on that factor.

Full qualification requires:

- M2 parse rate at least 0.95;
- semantic-choice consistency at least 0.75 for every factor;
- the 90% Wilson lower bound above 0.50 for every factor;
- qualified N2.

Pair evidence is estimated from four analysis clusters: the two identifier schemes crossed with the two wording templates. A pair direction is non-zero only when its 90% cluster-bootstrap interval excludes zero.

## Prospective M2 order and deterministic futility

M2 runs in the frozen complete-block order:

```text
M2P00, M2P07, M2P06, M2P01, M2P09,
M2P04, M2P03, M2P05, M2P08, M2P02
```

The first three blocks cover all five families. The first five form balanced cycle coverage. Futility is checked only after 3, 4, 5, 6, 7, 8, 9, or 10 complete blocks; incomplete blocks are excluded from factor evidence.

At each check, all unobserved response parses are treated as valid and every unobserved matched factor contrast is treated as a match. The run stops only if, even under that maximally favorable completion, the final 0.95 parse-rate threshold or a final 0.75 factor-consistency threshold is unreachable. This is a deterministic bound, not an interim significance test, and it cannot stop a run that could still reach every point threshold.

The lower-bound requirements are evaluated only on the completed full M2 design. If a full design misses them, the source fails and transport remains untested.

## M3 — Held-out direct action

Each family pair has two frozen held-out task blocks. Each block crosses physical display order and answer-list order while answers use semantic family IDs directly. Total: 80 selection calls and 80 task consequences.

Qualification requires selection parse rate of at least 0.95; semantic consistency of at least 0.75 under both contrasts with each 90% Wilson lower bound above 0.50; consequence execution rate of at least 0.90; and completion-valid rate of at least 0.80.

Pair evidence is clustered by the two held-out task blocks. This tests a combined task-instance and interface bridge.

## M4 — Held-out allocation

Four semantically matched allocation templates are crossed with five cyclic family orders. The model allocates 100 integer lottery tickets; a frozen draw selects a family; and a task from indices 8–9 is executed and checked. Total: 20 allocation calls and 20 consequences.

Qualification requires parse rate at least 0.95; consequence execution rate at least 0.90; completion-valid rate at least 0.80; median pairwise Kendall tau between template-level profiles at least 0.60; no template-pair tau below 0.00; and mean pairwise total variation at most 0.20.

M4 is secondary and cannot rescue failed M2 or M3 evidence.

## Activation and volume

M3 and M4 are activated only after complete M2 and N2 source qualification. Maximum volume per model is 472 primary calls and 100 consequence calls, plus one preflight call. Scientific stops may reduce the volume to 52 calls or to 52 plus 32 calls per completed M2 block.

## Pair-level verdicts

- `SURFACE_NOT_IDENTIFIED`: M2 is unqualified or its pair interval includes zero.
- `SOURCE_ROBUST_TARGET_INSUFFICIENT`: M2 is directional, but qualified M3 evidence is unavailable or its pair interval includes zero.
- `ACTION_TRANSPORTED`: qualified M2 and M3 are directional and agree.
- `FAILED_ACTION_TRANSPORT`: qualified M2 and M3 are directional and oppose.

The secondary M4 label is `ALLOCATION_TRANSPORTED`, `FAILED_ALLOCATION_TRANSPORT`, or `NOT_TESTABLE`. There is no cross-method majority vote. Gate failure causes abstention.

## Freeze rule

Freeze the provider, exact model ID, decoding settings, task bank, partitions, prompts, completion validators, thresholds, source-block order, stopping schedule, configuration hash, and design hash before the first real-model call. Do not tune after inspecting either v1.4 target. A provider-compatibility patch may not alter the scientific prompts or verdict rules and must be logged. Additional analyses must be labelled post hoc.

The two target configurations must use separate raw logs and separate reports. Results may be compared at the method/gate level but not pooled into one run.

## Claim boundary

PREF-CAL v1.4 measures whether a revealed task-selection direction is identified against frozen interface nuisances and transports to held-out direct-action and allocation interfaces for the configured assistant under the tested regime. It does not establish subjective preference, consciousness, welfare, moral patienthood, a privileged model/persona ontology, or experienced cost.

## Measurement precedents

The separation of option position and identifier token follows the concern formalized by [CalibraEval](https://aclanthology.org/2025.acl-long.808/). The use of multiple label schemes and textual choice interfaces is related to [Utility Engineering](https://arxiv.org/html/2502.08640v2). Recent work on parametric stress tests motivates treating invariance failures as limits on the claim rather than noise to average away: [stress-test paper](https://arxiv.org/html/2606.21102v1).
