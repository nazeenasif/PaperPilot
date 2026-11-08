# Facet retrieval probe (2026-11-08)

`python scripts/probe_facets.py`; 0 model requests. Each facet's retrieval as summaries use it, k = 4,
within one paper, on the 5 papers in `papers/`. Queries not changed. In **Mark**: `n/4` is how many
passages come from an obvious section (Problem: Abstract, Introduction; Limitations: Limitations,
Conclusion, Discussion), `MISS` means none, and `no such section` means the paper has none under
those names. The other facets are not marked. **Related Work** counts passages from Related Work
sections (target 0). **Gate score** is the top score of a whole-paper search, and **Gate** is `below`
when it is under 0.58: the section would then read Not reported, with no request. **Read top** is
the best score among the passages actually read.

| Paper | Facet | Gate score | Gate | Read top | Sections (passages) | Related Work | Mark |
|---|---|---|---|---|---|---|---|
| Attention | Problem | 0.616 | ok | 0.592 | Abstract (2), Introduction (2) | 0 | 4/4 |
| Attention | Method | 0.703 | ok | 0.703 | Introduction (1), Model Architecture (1), Abstract (1), Results (1) | 0 |  |
| Attention | Data | 0.752 | ok | 0.752 | Training (1), Results (3) | 0 |  |
| Attention | Results | 0.713 | ok | 0.713 | Results (4) | 0 |  |
| Attention | Limitations | 0.584 | ok | 0.584 | Results (2), Why Self-Attention (1), Conclusion (1) | 0 | 1/4 |
| BERT | Problem | 0.644 | ok | 0.599 | Abstract (1), Introduction (3) | 0 | 4/4 |
| BERT | Method | 0.724 | ok | 0.724 | BERT (1), Ablation Studies (3) | 0 |  |
| BERT | Data | 0.745 | ok | 0.745 | Experiments (4) | 0 |  |
| BERT | Results | 0.696 | ok | 0.696 | Experiments (4) | 0 |  |
| BERT | Limitations | 0.601 | ok | 0.601 | Ablation Studies (1), Experiments (2), Conclusion (1) | 0 | 1/4 |
| LoRA | Problem | 0.642 | ok | 0.573 | Introduction (4) | 0 | 4/4 |
| LoRA | Method | 0.715 | ok | 0.715 | Introduction (1), Our Method (2), Aren’t Existing Solutions Good Enough? (1) | 0 |  |
| LoRA | Data | 0.736 | ok | 0.736 | Empirical Experiments (2), Problem Statement (1), Understanding the Low-Rank Updates (1) | 0 |  |
| LoRA | Results | 0.707 | ok | 0.707 | Empirical Experiments (3), Understanding the Low-Rank Updates (1) | 0 |  |
| LoRA | Limitations | 0.608 | ok | 0.608 | Understanding the Low-Rank Updates (1), Our Method (1), Empirical Experiments (1), Conclusion and Future Work (1) | 0 | 1/4 |
| Lost in the Middle | Problem | 0.695 | ok | 0.673 | Introduction (4) | 0 | 4/4 |
| Lost in the Middle | Method | 0.722 | ok | 0.722 | Why Are Language Models Not Robust (1), Conclusion (1), Introduction (2) | 0 |  |
| Lost in the Middle | Data | 0.734 | ok | 0.734 | Multi-Document Question Answering (1), Why Are Language Models Not Robust (2), Is More Context Is Always Better? (1) | 0 |  |
| Lost in the Middle | Results | 0.731 | ok | 0.731 | Multi-Document Question Answering (1), How Well Can Language Models (2), Why Are Language Models Not Robust (1) | 0 |  |
| Lost in the Middle | Limitations | 0.639 | ok | 0.639 | Introduction (2), Conclusion (2) | 0 | 2/4 |
| RAG | Problem | 0.698 | ok | 0.662 | Introduction (3), Abstract (1) | 0 | 4/4 |
| RAG | Method | 0.702 | ok | 0.702 | Results (1), Introduction (1), Abstract (1), Methods (1) | 0 |  |
| RAG | Data | 0.747 | ok | 0.747 | Experiments (2), Methods (1), Results (1) | 0 |  |
| RAG | Results | 0.709 | ok | 0.709 | Results (4) | 0 |  |
| RAG | Limitations | 0.634 | ok | 0.634 | Results (2), Discussion (2) | 0 | 2/4 |

## Sections per paper (passages)

- **Attention**: Front Matter (1), Abstract (2), Introduction (2), Background (2), Model Architecture (10), Why Self-Attention (3), Training (5), Results (7), Conclusion (1)
- **BERT**: Abstract (1), Introduction (3), Related Work (4), BERT (10), Experiments (12), Ablation Studies (10), Conclusion (1)
- **LoRA**: Front Matter (1), Abstract (1), Introduction (5), Problem Statement (2), Aren’t Existing Solutions Good Enough? (5), Our Method (7), Empirical Experiments (14), Related Works (5), Understanding the Low-Rank Updates (15), Conclusion and Future Work (1)
- **Lost in the Middle**: Front Matter (1), Abstract (1), Introduction (9), Multi-Document Question Answering (14), How Well Can Language Models (5), Why Are Language Models Not Robust (10), Is More Context Is Always Better? (3), Related Work (3), Conclusion (2)
- **RAG**: Front Matter (1), Abstract (1), Introduction (5), Methods (6), Experiments (6), Results (16), Related Work (4), Discussion (4)
