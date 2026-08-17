# Why run PREF-CAL v1.4 on NVIDIA NIM

## Prior evidence

The completed GPT-OSS-120B v1.2 run remains a valid negative calibration result. Its forced-choice surface was dominated by the first response identifier, M2 and M3 were unqualified, M4 varied sharply by template despite passing the older gate, and no task-family pair earned identification.

The Groq v1.3 run was stopped after 206 successful primary episodes because of token limits and prohibitive elapsed time. It is preserved as an interrupted run. Its observed results must not be used to change v1.4 prompts, gates, ordering, or target-specific decoding.

## Why v1.4 is separate

v1.4 preserves the held-out-interface estimand but adds a prospectively frozen staged decision process. The source construct must be identified before expensive held-out action and allocation consequences receive any calls. Deterministic futility checks stop only when perfect remaining outcomes could no longer reach a frozen point gate.

This makes failure informative while bounding wasted calls. It does not turn partial blocks into evidence, relax uncertainty gates, or peek repeatedly at significance.

## Why these two targets

The first experiment repeats `openai/gpt-oss-120b` through NVIDIA NIM. Because the model family and prompt/task design are held fixed while the hosted provider changes, it is the closest available test of provider/backend transport. It is not bitwise replication because hosted implementation details may differ.

The second experiment uses `meta/llama-3.3-70b-instruct`. It asks whether the measurement outcome transports to a different instruction-tuned model family under its published NVIDIA decoding recommendation.

The previously considered hosted `qwen/qwen3.5-397b-a17b` target is not used because NVIDIA currently labels its free hosted endpoint deprecated. Substituting Llama is recorded before either v1.4 run and has its own configuration and design hash.

## Decision rule

- Preserve v1.1, v1.2, and the partial v1.3 run unchanged.
- Run the NVIDIA GPT-OSS configuration first.
- Save its complete target-specific bundle before starting Llama.
- Run Llama in a different directory with no shared raw log.
- Accept any prospective stop as the terminal result for that target.
- Compare models at the level of frozen gates, source qualification, and transport verdicts; do not pool episode rows.
- Do not add or choose a third model after seeing which of these two gives a more attractive answer. A later extension needs a new, separately labelled decision rule.

## Interpretation

A positive M2-to-M3 bridge would show that a revealed task-selection direction survived the frozen source nuisances and predicted held-out direct selection and valid completion under that exact assistant configuration. A provider difference would be evidence of deployment sensitivity, not proof that either provider reveals a truer preference. No outcome establishes subjective preference, consciousness, welfare, moral patienthood, model identity, or experienced cost.
