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
- `hard_weight`: penalty for relaxed hard-constraint violations.
- `sample_count`, `sample_noise`: stochastic projection probes.
- `max_gradient_moves`: number of gradient-guided class moves tested per probe.

## Memory

See `TensorSearch显存估算.md` and
`output/analysis/tensor_search_memory_estimate.csv`.

High-risk instances with the current explicit room-conflict tensor:

- `lums-spr18`: recommended GPU memory about 22.79 GiB.
- `muni-fsps-spr17c`: recommended GPU memory about 13.99 GiB.

The current `ConstraintsResolver_v2` also has Python-side CPU overhead while
building room-capacity conflicts, so system RAM can be the first bottleneck on
large instances.

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
