# Checkpoint 7 claims, v4 (2026-11-08)

LoRA summary regenerated in full after the 8,192-token limit, repeated table headers and the kept
complete summary (prompt version 8). 6 planned requests, 0 retries; all 6 parts verified, none cut off.
A full run replaced the planned 2-request retry, because re-processing LoRA deleted the partial v3
summary. The first report's claim 14 is claim 15 here.

Hand check (FR-027, SC-002): verify at least five claims from each source against the PDFs.
**Verdict**: correct / wrong / partly. **Fault** (for wrong or partly): retrieval (the right
passage was not retrieved) or model (the cited passage does not say it).

| # | Source | Part | Claim | Cited passages | Verdict | Fault |
|---|---|---|---|---|---|---|
| 1 | LoRA summary | tldr | LoRA freezes pretrained weights and learns low-rank updates for attention matrices, enabling parameter-efficient adaptation with no added inference latency [3, 7, 5]. | [3] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 2: “when deployed, introducing no inference latency compared to a fully ﬁne-tuned model, by construction. • LoRA is orthogonal to many prior methods and can be combined with many of them, such as preﬁx-tu…”<br>[7] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “2They represent a negligible number of parameters compared to weights. 3An inevitability when adapting to hard tasks. guarantees that we do not introduce any additional latency during inference compar…”<br>[5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 2 | LoRA summary | tldr | It matches or exceeds fine-tuning on GPT-3 175B across three datasets, with best accuracy when adapting Wq and Wv, though batching different tasks with merged LoRA matrices is not straightforward [13, 14, 15]. | [13] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Understanding the Low-Rank Updates, p. 10: “Weight Type Wq Wk Wv Wo Wq, Wk Wq, Wv Wq, Wk, Wv, Wo Rank r 8 8 8 8 4 4 2 WikiSQL (±0.5%) 70.4 70.0 73.0 73.2 71.4 73.7 73.7 MultiNLI (±0.1%) 91.0 90.8 91.0 91.3 91.3 91.3 91.7 Table 5: Validation acc…”<br>[14] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 8: “5.5 SCALING UP TO GPT-3 175B As a ﬁnal stress test for LoRA, we scale up to GPT-3 with 175 billion parameters. Due to the high training cost, we only report the typical standard deviation for a given …”<br>[15] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “on machines that store the pre-trained weights in VRAM. We also observe a 25% speedup during training on GPT-3 175B compared to full ﬁne-tuning5 as we do not need to calculate the gradient for the vas…” |  |  |
| 3 | LoRA summary | problem | Fine-tuning large pre-trained language models updates all parameters, creating critical deployment challenges for models like GPT-3 with 175 billion parameters [4]. | [4] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 1: “Many applications in natural language processing rely on adapting one large-scale, pre-trained language model to multiple downstream applications. Such adaptation is usually done via ﬁne-tuning, which…” |  |  |
| 4 | LoRA summary | problem | Existing parameter-efficient adaptation methods that modify only some parameters or add external modules often fail to match fine-tuning performance, forcing a trade-off between efficiency and model quality [1, 4]. | [1] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 2: “usable sequence length (Li & Liang, 2021; Lester et al., 2021; Hambardzumyan et al., 2020; Liu et al., 2021) (Section 3). More importantly, these method often fail to match the ﬁne-tuning baselines, p…”<br>[4] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 1: “Many applications in natural language processing rely on adapting one large-scale, pre-trained language model to multiple downstream applications. Such adaptation is usually done via ﬁne-tuning, which…” |  |  |
| 5 | LoRA summary | method | LoRA freezes pretrained weights W0 and learns low-rank updates ΔW = BA with rank r, applied to attention projection matrices (Wq, Wk, Wv, Wo) while freezing MLP modules for simplicity and parameter-efficiency [3, 7]. | [3] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 2: “when deployed, introducing no inference latency compared to a fully ﬁne-tuned model, by construction. • LoRA is orthogonal to many prior methods and can be combined with many of them, such as preﬁx-tu…”<br>[7] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “2They represent a negligible number of parameters compared to weights. 3An inevitability when adapting to hard tasks. guarantees that we do not introduce any additional latency during inference compar…” |  |  |
| 6 | LoRA summary | method | During deployment, merged weights W = W0 + BA are used for inference with no added latency [5]. | [5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 7 | LoRA summary | method | Switching tasks requires only subtracting BA and adding a new B′A′ [5]. | [5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 8 | LoRA summary | method | The method is orthogonal to other efficient adaptation techniques [3]. | [3] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 2: “when deployed, introducing no inference latency compared to a fully ﬁne-tuned model, by construction. • LoRA is orthogonal to many prior methods and can be combined with many of them, such as preﬁx-tu…” |  |  |
| 9 | LoRA summary | data | Experiments evaluate LoRA on RoBERTa, DeBERTa, GPT-2, and GPT-3 175B using the GLUE benchmark for NLU, and WikiSQL (NL to SQL) and SAMSum (conversation summarization) for NLG on GPT-3 [8]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…” |  |  |
| 10 | LoRA summary | data | The setup follows Li & Liang (2021) for GPT-2 and replicates Houlsby et al. |  |  |  |
| 11 | LoRA summary | data | (2019) and Pfeiffer et al. |  |  |  |
| 12 | LoRA summary | data | (2021) for adapters, using a fixed batch size, sequence length 128, and pre-trained initialization for MRPC, RTE, and STS-B [8,10]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…”<br>[10] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 7: “RoBERTa (Liu et al., 2019) optimized the pre-training recipe originally proposed in BERT (Devlin et al., 2019a) and boosted the latter’s task performance without introducing many more trainable parame…” |  |  |
| 13 | LoRA summary | data | All experiments run on NVIDIA Tesla V100 GPUs [8]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…” |  |  |
| 14 | LoRA summary | results | LoRA matches or exceeds fine-tuning on GPT-3 175B across three datasets [14]. | [14] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 8: “5.5 SCALING UP TO GPT-3 175B As a ﬁnal stress test for LoRA, we scale up to GPT-3 with 175 billion parameters. Due to the high training cost, we only report the typical standard deviation for a given …” |  |  |
| 15 | LoRA summary | results | In attention-weight ablations, adapting both Wq and Wv achieves the best validation accuracy: 73.7% on WikiSQL (±0.5%) and 91.7% on MultiNLI (±0.1%) [13]. | [13] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Understanding the Low-Rank Updates, p. 10: “Weight Type Wq Wk Wv Wo Wq, Wk Wq, Wv Wq, Wk, Wv, Wo Rank r 8 8 8 8 4 4 2 WikiSQL (±0.5%) 70.4 70.0 73.0 73.2 71.4 73.7 73.7 MultiNLI (±0.1%) 91.0 90.8 91.0 91.3 91.3 91.3 91.7 Table 5: Validation acc…” |  |  |
| 16 | LoRA summary | results | Using more than 256 special tokens for prefix-embedding tuning or more than 32 for prefix-layer tuning causes significant performance drops [14]. | [14] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 8: “5.5 SCALING UP TO GPT-3 175B As a ﬁnal stress test for LoRA, we scale up to GPT-3 with 175 billion parameters. Due to the high training cost, we only report the typical standard deviation for a given …” |  |  |
| 17 | LoRA summary | limitations | The authors note that LoRA has limitations: it is not straightforward to batch inputs from different tasks with distinct LoRA matrices (A and B) in a single forward pass if the matrices are merged into the base weights to avoid inference latency, though dynamically selecting LoRA modules per sample is possible when latency is not critical [15]. | [15] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “on machines that store the pre-trained weights in VRAM. We also observe a 25% speedup during training on GPT-3 175B compared to full ﬁne-tuning5 as we do not need to calculate the gradient for the vas…” |  |  |

## Tokens per part (limit 8,192, reasoning included)

| Part | State | Input | Output | Reasoning | Visible |
|---|---|---|---|---|---|
| TL;DR | verified | 807 | 2,114 | 2,020 | 94 |
| Problem | verified | 1,582 | 731 | 657 | 74 |
| Method | verified | 1,370 | 802 | 692 | 110 |
| Data | verified | 1,772 | 1,960 | 1,791 | 169 |
| Results | verified | 1,385 | 1,817 | 1,704 | 113 |
| Limitations | verified | 1,431 | 1,138 | 1,069 | 69 |

## Checked before the hand check

Flags from reading the stored passages and `papers/2106.09685.pdf`, not verdicts, so the columns above
stay empty. All of these passed validation.

- **Claim 15, the number is still wrong.** It gives "both Wq and Wv" 91.7 on MultiNLI. Table 5 gives
  Wq, Wv 91.3, and 91.7 is the Wq, Wk, Wv, Wo column. Passage [13] now holds the header row, so the
  missing header was not the whole cause: the model had the labels and still paired the caption's "Wq
  and Wv gives the best performance overall" with the column's highest number. The number check cannot
  catch this, because 91.7 is in the passage. 73.7 is right for Wq, Wv.
- **Claim 2 keeps the GPT-3 scope** ("on GPT-3 175B across three datasets"). This is one run, and Results
  had no GLUE numbers to extend it to (next flag), so it is not evidence that the scope rule works.
- **Results read no Table 2 rows.** Passage [12] is only the second piece of the split table: the header
  row plus the end of the caption. The piece with the rows was not retrieved, so the DeBERTa and RoBERTa
  results of v2 are gone.
- **Claim 9, scope blur.** It lists GPT-2 and GPT-3 175B with "the GLUE benchmark"; [8] names GLUE for
  RoBERTa and DeBERTa only.
- **Claims 10-12 are one sentence, cut at "et al."** The validator's sentence rule splits there, so claims
  10 and 11 show no passage and are listed as uncited, although the sentence cites [8,10]. The section card
  would wrongly say 2 sentences have no citation. A TL;DR with "et al." would be held back for the same
  reason.
- **Claim 5, citations partly elsewhere.** "ΔW = BA" and the frozen weights are not all in [3] or [7]; [5]
  and [1] hold the rest.
