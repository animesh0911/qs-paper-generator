# Eval report

## generation

| arm | model | config | trials | $/run mean±std | wall ms p50 | call ms p95 | tok in/out | accuracy highlights |
|---|---|---|---|---|---|---|---|---|
| grounded | deepseek-v4-flash | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0037±0.0000 | 134973 | 134958 | 14018/13504 | yield=1.00 cite_support=0.67 self_containedness=4.8 ncert_fidelity=4.7 qtype_conformity=4.9 answer_correctness=5.0 difficulty_plausibility=3.9 Δhuman[self_containedness]=0.00 Δhuman[ncert_fidelity]=1.20 Δhuman[qtype_conformity]=0.00 Δhuman[answer_correctness]=1.00 Δhuman[difficulty_plausibility]=1.20 |
| grounded | deepseek-v4-flash | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0062±0.0000 | 231317 | 231300 | 13994/27654 | yield=1.00 cite_support=0.67 self_containedness=5.0 ncert_fidelity=4.8 qtype_conformity=4.6 answer_correctness=4.8 difficulty_plausibility=3.8 Δhuman[self_containedness]=0.00 Δhuman[ncert_fidelity]=0.20 Δhuman[qtype_conformity]=0.00 Δhuman[answer_correctness]=0.40 Δhuman[difficulty_plausibility]=0.60 |
| grounded | deepseek-v4-pro | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0129±0.0000 | 135498 | 135477 | 13425/8074 | yield=1.00 cite_support=0.73 |
| grounded | deepseek-v4-pro | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0250±0.0000 | 411336 | 410602 | 14018/21687 | yield=1.00 cite_support=0.70 |
| grounded | google/gemini-3.1-flash-lite | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0159±0.0000 | 26920 | 26903 | 16812/7813 | yield=1.00 cite_support=0.80 |
| grounded | google/gemini-3.1-flash-lite | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0103±0.0000 | 16546 | 16529 | 16818/4058 | yield=0.33 cite_support=0.50 |
| grounded | google/gemini-3.5-flash | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.1401±0.0000 | 54809 | 54791 | 16812/12765 | yield=1.00 cite_support=0.80 self_containedness=5.0 ncert_fidelity=5.0 qtype_conformity=5.0 answer_correctness=5.0 difficulty_plausibility=4.6 Δhuman[self_containedness]=0.60 Δhuman[ncert_fidelity]=0.00 Δhuman[qtype_conformity]=0.00 Δhuman[answer_correctness]=0.00 Δhuman[difficulty_plausibility]=1.00 |
| grounded | google/gemini-3.5-flash | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.2180±0.0000 | 82475 | 81962 | 16818/21419 | yield=1.00 cite_support=0.63 self_containedness=5.0 ncert_fidelity=5.0 qtype_conformity=4.6 answer_correctness=5.0 difficulty_plausibility=4.4 Δhuman[self_containedness]=0.00 Δhuman[ncert_fidelity]=0.20 Δhuman[qtype_conformity]=0.20 Δhuman[answer_correctness]=0.20 Δhuman[difficulty_plausibility]=0.40 |
| grounded | gpt-oss-120b | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0022±0.0000 | 191271 | 191246 | 13492/9769 | yield=1.00 cite_support=0.40 |
| grounded | gpt-oss-120b | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0023±0.0000 | 188349 | 187695 | 13492/10104 | yield=0.80 cite_support=0.08 |
| grounded | gpt-oss-20b | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0012±0.0000 | 56142 | 56130 | 13492/5687 | yield=0.00 |
| grounded | gpt-oss-20b | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 0) | 0.0016±0.0000 | 85036 | 85018 | 13481/8954 | yield=0.00 |
| grounded | qwen-3.7-max | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 1) | unpriced | 0 | 0 | 0/0 | unscored |
| grounded | qwen-3.7-max | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 1) | unpriced | 0 | 0 | 0/0 | unscored |
| grounded | qwen-3.7-plus | batch_size=15,fixture_id=carbon-compounds-grounded | 1 (fail 1) | unpriced | 0 | 0 | 0/0 | unscored |
| grounded | qwen-3.7-plus | batch_size=30,fixture_id=carbon-compounds-grounded | 1 (fail 1) | unpriced | 0 | 0 | 0/0 | unscored |

## Per-user monthly cost (profile: brief_defaults)

| scenario | arm | model | runs/mo | $/run | $/mo | ₹/mo |
|---|---|---|---|---|---|---|
| generation | grounded | deepseek-v4-flash | 1 | 0.0062 | 0.0062 | 0.55 |
| generation | grounded | deepseek-v4-pro | 1 | 0.0250 | 0.0250 | 2.20 |
| generation | grounded | google/gemini-3.1-flash-lite | 1 | 0.0103 | 0.0103 | 0.91 |
| generation | grounded | google/gemini-3.5-flash | 1 | 0.2180 | 0.2180 | 19.18 |
| generation | grounded | gpt-oss-120b | 1 | 0.0023 | 0.0023 | 0.20 |
| generation | grounded | gpt-oss-20b | 1 | 0.0016 | 0.0016 | 0.14 |
