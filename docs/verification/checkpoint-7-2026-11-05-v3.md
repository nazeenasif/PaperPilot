# Checkpoint 7 claims, v3 (2026-11-05)

LoRA summary regenerated after the table header fix, the scope rule and the top-up (prompt version 8).
6 planned requests, 0 retries. **Checkpoint result: FAIL.** The Results section was cut off at the
4,096-token limit, so it has no text and no claims here, and the TL;DR was built without Results. The
other 5 parts verified.

Failed parts keep no token counts, so why Results ran out is not known. It read 2,607 tokens in v2 from
different passages: this time [13] carries Table 5's header row and [12] is a different slice of Table 2.
One run cannot separate those from ordinary variation in the model's reasoning length.

Hand check (FR-027, SC-002): verify at least five claims from each source against the PDFs.
**Verdict**: correct / wrong / partly. **Fault** (for wrong or partly): retrieval (the right
passage was not retrieved) or model (the cited passage does not say it).

| # | Source | Part | Claim | Cited passages | Verdict | Fault |
|---|---|---|---|---|---|---|
| 1 | LoRA summary | tldr | LoRA fine-tunes large models by learning low-rank updates to attention projection matrices, keeping other weights frozen and adding no inference latency [7,5]. | [7] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “2They represent a negligible number of parameters compared to weights. 3An inevitability when adapting to hard tasks. guarantees that we do not introduce any additional latency during inference compar…”<br>[5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 2 | LoRA summary | tldr | It is evaluated on GLUE, WikiSQL, and SAMSum for RoBERTa, DeBERTa, and GPT-3 [8,10]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…”<br>[10] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 7: “RoBERTa (Liu et al., 2019) optimized the pre-training recipe originally proposed in BERT (Devlin et al., 2019a) and boosted the latter’s task performance without introducing many more trainable parame…” |  |  |
| 3 | LoRA summary | tldr | However, batching inputs for different tasks with distinct LoRA modules is not straightforward when weights are merged [15]. | [15] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “on machines that store the pre-trained weights in VRAM. We also observe a 25% speedup during training on GPT-3 175B compared to full ﬁne-tuning5 as we do not need to calculate the gradient for the vas…” |  |  |
| 4 | LoRA summary | problem | Fine-tuning large pre-trained models like GPT-3 (175B parameters) requires updating all parameters, creating a critical deployment challenge as model sizes grow [4]. | [4] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 1: “Many applications in natural language processing rely on adapting one large-scale, pre-trained language model to multiple downstream applications. Such adaptation is usually done via ﬁne-tuning, which…” |  |  |
| 5 | LoRA summary | problem | Existing parameter-efficient methods that adapt only a subset of parameters or learn external modules often fail to match full fine-tuning performance, forcing a trade-off between efficiency and model quality [1]. | [1] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Introduction, p. 2: “usable sequence length (Li & Liang, 2021; Lester et al., 2021; Hambardzumyan et al., 2020; Liu et al., 2021) (Section 3). More importantly, these method often fail to match the ﬁne-tuning baselines, p…” |  |  |
| 6 | LoRA summary | method | LoRA adapts pretrained models by learning low-rank matrices B and A such that the weight update ΔW = BA is added to frozen pretrained weights W0. |  |  |  |
| 7 | LoRA summary | method | The approach targets the self-attention projection matrices (Wq, Wk, Wv, Wo) while keeping MLP modules fixed [7]. | [7] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “2They represent a negligible number of parameters compared to weights. 3An inevitability when adapting to hard tasks. guarantees that we do not introduce any additional latency during inference compar…” |  |  |
| 8 | LoRA summary | method | During inference, the merged weight W = W0 + BA is used directly, adding no latency [5]. | [5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 9 | LoRA summary | method | Switching tasks requires only replacing BA with a different low-rank update B'A' [5]. | [5] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 4: “In other words, as we increase the number of trainable parameters 3, training LoRA roughly converges to training the original model, while adapter-based methods converges to an MLP and preﬁx-based met…” |  |  |
| 10 | LoRA summary | data | Experiments evaluate on GLUE for RoBERTa and DeBERTa, and add WikiSQL and SAMSum for GPT-3, while GPT-2 follows the Li & Liang (2021) setup [8]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…” |  |  |
| 11 | LoRA summary | data | Pre-trained RoBERTa base (125M) and large (355M) are taken from HuggingFace Transformers [10]. | [10] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 7: “RoBERTa (Liu et al., 2019) optimized the pre-training recipe originally proposed in BERT (Devlin et al., 2019a) and boosted the latter’s task performance without introducing many more trainable parame…” |  |  |
| 12 | LoRA summary | data | All experiments run on NVIDIA Tesla V100 [8]. | [8] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 5: “We evaluate the downstream task performance of LoRA on RoBERTa (Liu et al., 2019), DeBERTa (He et al., 2021), and GPT-2 (Radford et al., b), before scaling up to GPT-3 175B (Brown et al., 2020). Our e…” |  |  |
| 13 | LoRA summary | data | For fair adapter comparison, a uniform batch size and sequence length of 128 are used, and models are initialized to pre-trained weights for MRPC, RTE, and STS-B rather than an MNLI-adapted model [10]. | [10] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Empirical Experiments, p. 7: “RoBERTa (Liu et al., 2019) optimized the pre-training recipe originally proposed in BERT (Devlin et al., 2019a) and boosted the latter’s task performance without introducing many more trainable parame…” |  |  |
| 14 | LoRA summary | limitations | The authors note that LoRA has limitations: it is not straightforward to batch inputs for different tasks with distinct A and B matrices in a single forward pass if the weights are merged into W to remove inference latency, though dynamically selecting LoRA modules per sample is possible when latency is not critical [15]. | [15] LORA: LOW-RANK ADAPTATION OF LARGE LANGU, Our Method, p. 5: “on machines that store the pre-trained weights in VRAM. We also observe a 25% speedup during training on GPT-3 175B compared to full ﬁne-tuning5 as we do not need to calculate the gradient for the vas…” |  |  |

## Checked before the hand check

Flags from reading the stored passages, not verdicts, so the columns above stay empty.

- **v2's claim 14 cannot be re-judged.** With Results cut off, no number was stated. The input is fixed:
  passage [13] now starts "Weight Type Wq Wk Wv Wo Wq, Wk Wq, Wv Wq, Wk, Wv, Wo Rank r ...", so the model
  can see that 91.7 belongs to the all-weights column. Whether it now states this is untested.
- **The TL;DR's GPT-3 scope is untested.** It makes no performance claim, because it had no Results
  section to draw on, so the scope rule was not exercised on the sentence F2 keeps producing.
- **Claim 2 loses the pairing.** "GLUE, WikiSQL, and SAMSum for RoBERTa, DeBERTa, and GPT-3" merges what
  Data kept separate (claim 10: GLUE for RoBERTa and DeBERTa, WikiSQL and SAMSum for GPT-3), and drops
  GPT-2. The citations are valid.
- **Claim 6 has no citation.** The API lists it in `uncited_sentences`, so the section card now flags it.
- **Claim 1 wording.** "LoRA fine-tunes large models": the paper presents LoRA as an alternative to full
  fine-tuning.
- **Table 2 is still split.** Passage [12] starts mid-row with no header row (`docs/known-limitations.md`).
