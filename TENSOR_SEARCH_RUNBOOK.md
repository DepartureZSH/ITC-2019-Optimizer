# Tensor Gradient Search Runbook

This repository can run Phase 2 tensor gradient search directly from existing
solution XMLs in `data/solutions`. It does not require Gurobi.

## Setup

```bash
pip install -r requirements.txt
```

Install the CUDA-enabled PyTorch build that matches the target GPU machine if
the default `pip install torch` does not provide CUDA support.

## Run

```bash
python main.py --method tensor_search --instance muni-fsps-spr17c --device cuda:0
```

Useful smaller smoke test:

```bash
python main.py --method tensor_search --instance yach-fal17 --device cuda:0
```

If CUDA is requested but unavailable, `main.py` falls back to CPU.

## Configuration

Tensor-search parameters live in `config.yaml` under `tensor_search`.

Important knobs:

- `steps`: gradient optimization iterations.
- `lr`: Adam learning rate for logits.
- `temperature`, `cooling`, `min_temperature`: class-wise softmax schedule.
- `eval_every`: discrete projection frequency.
- `hard_surrogate`: defaults to `none` to avoid a full `hard_dist_tensor @ x`
  sparse multiply on large instances.
- `hard_weight`: penalty for relaxed hard-constraint violations. Use this only
  with `hard_surrogate: full_sparse` on small instances or GPUs with enough
  headroom.
- `sample_count`, `sample_noise`: stochastic projection probes.
- `max_gradient_moves`: number of gradient-guided class moves tested per probe.

With the default `hard_surrogate: none`, the continuous loss optimizes the
time/room/distribution objective. Hard feasibility is still protected by the
discrete probe path: a candidate replaces the incumbent only after the
official-aligned local validator says it is feasible.

## Memory

See `TensorSearch显存估算.md` and
`output/analysis/tensor_search_memory_estimate.csv`.

High-risk instances with the current explicit room-conflict tensor:

- `lums-spr18`: recommended GPU memory about 22.79 GiB.
- `muni-fsps-spr17c`: the old full hard sparse surrogate OOMed on a 24 GiB GPU:
  the process already used about 21.01 GiB, then `torch.sparse.mm` requested
  another 5.03 GiB. Treat that mode as a 32 GiB+ run.

The current `ConstraintsResolver_v2` also has Python-side CPU overhead while
building room-capacity conflicts, so system RAM can be the first bottleneck on
large instances.

For 24 GiB GPUs, keep `hard_surrogate: none` and consider:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

## Official Validator

Official validation is optional. Credentials are not stored in the repository.

```bash
export ITC2019_EMAIL="..."
export ITC2019_PASSWORD="..."
```

On PowerShell:

```powershell
$env:ITC2019_EMAIL="..."
$env:ITC2019_PASSWORD="..."
```
