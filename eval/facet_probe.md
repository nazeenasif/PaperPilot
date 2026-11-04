# Facet retrieval probe (2026-11-04)

`python scripts/probe_facets.py`; 0 model requests. Each facet's current query, k = 4,
within one paper, on the 5 papers in `papers/`. Queries not changed. In **Mark**: `n/4` is how many
passages come from an obvious section (Problem: Abstract, Introduction; Limitations: Limitations,
Conclusion, Discussion), `MISS` means none, and `no such section` means the paper has none under
those names. The other facets are not marked. **Related Work** counts passages from Related Work
sections (target 0). **Gate** is `below` when the top score is under 0.58: the section would
then read Not reported, with no request.

| Paper | Facet | Top score | Gate | Sections (passages) | Related Work | Mark |
|---|---|---|---|---|---|---|
| Attention | Problem | 0.699 | ok | Front Matter (1), Results (2), Background (1) | 0 | MISS |
| Attention | Method | 0.703 | ok | Introduction (1), Model Architecture (1), Abstract (1), Results (1) | 0 |  |
| Attention | Data | 0.752 | ok | Training (1), Results (3) | 0 |  |
| Attention | Results | 0.713 | ok | Results (4) | 0 |  |
| Attention | Limitations | 0.584 | ok | Results (2), Why Self-Attention (1), Model Architecture (1) | 0 | MISS |
| BERT | Problem | 0.644 | ok | Experiments (3), Related Work (1) | 1 | MISS |
| BERT | Method | 0.724 | ok | BERT (1), Ablation Studies (2), Related Work (1) | 1 |  |
| BERT | Data | 0.745 | ok | Experiments (3), Related Work (1) | 1 |  |
| BERT | Results | 0.697 | ok | Experiments (4) | 0 |  |
| BERT | Limitations | 0.601 | ok | Ablation Studies (1), Experiments (2), Related Work (1) | 1 | MISS |
| LoRA | Problem | 0.642 | ok | Understanding the Low-Rank Updates (4) | 0 | MISS |
| LoRA | Method | 0.715 | ok | Introduction (1), Our Method (2), Aren’t Existing Solutions Good Enough? (1) | 0 |  |
| LoRA | Data | 0.736 | ok | Empirical Experiments (2), Problem Statement (1), Understanding the Low-Rank Updates (1) | 0 |  |
| LoRA | Results | 0.707 | ok | Empirical Experiments (3), Understanding the Low-Rank Updates (1) | 0 |  |
| LoRA | Limitations | 0.608 | ok | Understanding the Low-Rank Updates (1), Our Method (1), Empirical Experiments (2) | 0 | MISS |
| Lost in the Middle | Problem | 0.695 | ok | Multi-Document Question Answering (2), Front Matter (1), Introduction (1) | 0 | 1/4 |
| Lost in the Middle | Method | 0.722 | ok | Why Are Language Models Not Robust (1), Conclusion (1), Introduction (2) | 0 |  |
| Lost in the Middle | Data | 0.734 | ok | Multi-Document Question Answering (1), Why Are Language Models Not Robust (2), Is More Context Is Always Better? (1) | 0 |  |
| Lost in the Middle | Results | 0.731 | ok | Multi-Document Question Answering (1), How Well Can Language Models (1), Why Are Language Models Not Robust (2) | 0 |  |
| Lost in the Middle | Limitations | 0.639 | ok | Introduction (2), Multi-Document Question Answering (2) | 0 | MISS |
| RAG | Problem | 0.698 | ok | Discussion (1), Results (2), Experiments (1) | 0 | MISS |
| RAG | Method | 0.707 | ok | Related Work (2), Results (1), Introduction (1) | 2 |  |
| RAG | Data | 0.747 | ok | Experiments (2), Methods (1), Results (1) | 0 |  |
| RAG | Results | 0.709 | ok | Results (4) | 0 |  |
| RAG | Limitations | 0.634 | ok | Results (2), Experiments (1), Discussion (1) | 0 | 1/4 |

## Sections per paper (passages)

- **Attention**: Front Matter (1), Abstract (2), Introduction (2), Background (2), Model Architecture (10), Why Self-Attention (3), Training (5), Results (7), Conclusion (1)
- **BERT**: Abstract (1), Introduction (3), Related Work (4), BERT (10), Experiments (12), Ablation Studies (11), Conclusion (1)
- **LoRA**: Front Matter (1), Abstract (1), Introduction (5), Problem Statement (2), Aren’t Existing Solutions Good Enough? (5), Our Method (7), Empirical Experiments (14), Related Works (5), Understanding the Low-Rank Updates (15), Conclusion and Future Work (1)
- **Lost in the Middle**: Front Matter (1), Abstract (1), Introduction (9), Multi-Document Question Answering (14), How Well Can Language Models (5), Why Are Language Models Not Robust (10), Is More Context Is Always Better? (3), Related Work (3), Conclusion (2)
- **RAG**: Front Matter (1), Abstract (1), Introduction (5), Methods (6), Experiments (6), Results (17), Related Work (4), Discussion (4)
