# Review Report: TASK-REV-G4R1

## Executive Summary

The MoE sanity run crash is caused by a **version mismatch between PEFT and the NVIDIA container's bundled torchao**. PEFT's LoRA dispatcher unconditionally checks `is_torchao_available()` for every LoRA module, which raises `ImportError` when torchao is installed but below 0.16.0. The NVIDIA `pytorch:25.11-py3` container ships torchao 0.14.0+git. The fix is a one-line monkey-patch added to the training script before `get_peft_model()` is called. The Dense path is latently vulnerable to the same crash.

## Review Details

- **Mode**: Decision (root cause + fix recommendation)
- **Depth**: Standard
- **Task**: TASK-REV-G4R1 (parent: TASK-G4MOE-004)
- **Scope**: torchao/PEFT version gate in `nvcr.io/nvidia/pytorch:25.11-py3`

## Finding 1: Root Cause — PEFT's `is_torchao_available()` raises instead of returning False

**Severity**: Blocking (crash)

The PEFT LoRA dispatcher chain calls `dispatch_torchao` for **every** LoRA module during `_create_new_module`. The function's logic is:

1. Check `is_torchao_available()` — if torchao is **not installed**, returns `False` (graceful skip)
2. But if torchao **is installed** and version < 0.16.0, **raises `ImportError`** instead of returning `False`

The NVIDIA container ships torchao 0.14.0+git (installed but old), so the raise path triggers. This is a design quirk in PEFT's `import_utils.py:143` — the "old version" path is treated as a hard error rather than a graceful degradation.

**Evidence**: Stack trace in [run-1.md](../../docs/reviews/training-gemma4-moe/run-1.md) lines 63-68:
```
File ".../peft/tuners/lora/torchao.py", line 142, in dispatch_torchao
    if not is_torchao_available():
File ".../peft/import_utils.py", line 143, in is_torchao_available
    raise ImportError(
ImportError: Found an incompatible version of torchao. Found version 0.14.0+git,
but only versions above 0.16.0 are supported
```

## Finding 2: Which package introduced the torchao >= 0.16.0 requirement

**Severity**: Informational

The `TORCHAO_MINIMUM_VERSION = "0.16.0"` gate was introduced in a recent PEFT release (post-0.14.x). The Step 3 install command `pip install peft` (unpinned) pulls the latest PEFT, which includes this gate. The Dense training run likely succeeded because it was executed earlier when `pip install peft` resolved to an older version without this gate.

**Implication**: This is not a code bug in `train_gemma4_moe.py` — it's a dependency resolution issue. The same crash would occur if you re-ran the Dense script today with the same unpinned `pip install peft`.

## Finding 3: Dense path is latently vulnerable

**Severity**: Medium (latent)

The Dense script (`train_gemma4_dense.py`) uses `load_in_4bit=True` (QLoRA via bitsandbytes). However, the PEFT torchao dispatcher is invoked for **all** LoRA modules regardless of quantisation mode — it's part of the dispatcher chain in `_create_new_module`, not conditional on quantisation. The Dense path only survived because it was run with an older PEFT version.

If the Dense run is repeated with the current unpinned `pip install peft`, it will hit the identical crash.

## Finding 4: torchao is not needed for this workload

**Severity**: Informational

The torchao dispatcher (`dispatch_torchao`) creates `TorchaoLoraLinear` modules only when the target weight is a `TorchAOBaseTensor`. Neither the MoE 16-bit path nor the Dense QLoRA 4-bit path uses torchao quantisation — they use bfloat16/bitsandbytes respectively. The dispatcher would return `None` and fall through to `dispatch_default` if it could get past the version check.

## Finding 5: Step 3 dependency list gap

**Severity**: Medium

The TASK-G4MOE-004 Step 3 install command does not pin PEFT or mention torchao:
```bash
pip install transformers peft hf_transfer "datasets==4.3.0" "trl==0.26.1"
```

This is fragile — `peft` resolves to whatever is latest on PyPI at install time, creating non-reproducible environments.

## Recommendations

### Recommendation 1 (RECOMMENDED): Monkey-patch `is_torchao_available` in training scripts

Add the following to both training scripts before `FastModel.get_peft_model()`.

**IMPORTANT**: You must patch **both** the source module (`peft.import_utils`) and the
importing module (`peft.tuners.lora.torchao`). The `from ... import` in torchao.py
creates a local reference that is not affected by patching the source alone. Run 2
confirmed that patching only `peft.import_utils` does NOT work.

```python
# Workaround: PEFT's torchao dispatcher raises ImportError when torchao is
# installed but < 0.16.0 (NVIDIA container ships 0.14.0+git). We don't use
# torchao quantisation, so bypass the check.
# Must patch both the source module AND the importing module, because
# `from peft.import_utils import is_torchao_available` creates a local
# reference that isn't affected by patching the source alone.
import peft.import_utils
import peft.tuners.lora.torchao
peft.import_utils.is_torchao_available = lambda: False
peft.tuners.lora.torchao.is_torchao_available = lambda: False
```

| Attribute | Assessment |
|-----------|------------|
| Risk | Very low — only affects torchao LoRA dispatch, which we don't use |
| Reversibility | Trivial — remove the lines when PEFT/container versions align |
| Scope | Both `train_gemma4_moe.py` and `train_gemma4_dense.py` |
| Side effects | None — `dispatch_torchao` returns `None`, falls through to `dispatch_default` |
| Run 2 note | Initial single-module patch failed; dual-module patch required |

### Recommendation 2 (ALTERNATIVE): Uninstall torchao from the container

```bash
pip uninstall -y torchao
```

If torchao is not installed at all, `is_torchao_available()` returns `False` (no raise). However, other NVIDIA container components may depend on torchao — needs testing.

| Attribute | Assessment |
|-----------|------------|
| Risk | Low-medium — may break other container functionality |
| Reversibility | `pip install torchao==0.14.0` to restore |
| Scope | Container-level, affects all workloads |

### Recommendation 3 (ALTERNATIVE): Pin PEFT to a version before the torchao gate

```bash
pip install "peft<0.15.0"
```

Avoids the torchao check entirely by using an older PEFT. However, this may miss bug fixes and Gemma 4 MoE support improvements in newer PEFT.

| Attribute | Assessment |
|-----------|------------|
| Risk | Medium — may miss important fixes for Gemma 4 MoE |
| Reversibility | Change the pin |
| Scope | Install command only |

### Recommendation 4 (HOUSEKEEPING): Pin PEFT version in Step 3

Regardless of which fix is chosen, pin PEFT in the install command to prevent future surprises:

```bash
pip install transformers "peft>=0.15.0,<1.0" hf_transfer "datasets==4.3.0" "trl==0.26.1"
```

### Recommendation 5 (HOUSEKEEPING): Apply fix to Dense script too

The monkey-patch should be added to `train_gemma4_dense.py` as well, since it has the same latent vulnerability.

## Decision Matrix

| Option | Risk | Effort | Compatibility | Recommendation |
|--------|------|--------|---------------|----------------|
| 1. Monkey-patch `is_torchao_available` | Very Low | 2 lines per script | Preserves latest PEFT | **RECOMMENDED** |
| 2. Uninstall torchao | Low-Med | 1 pip command | May break container | Alternative |
| 3. Pin older PEFT | Medium | 1 version pin | May miss Gemma 4 fixes | Not recommended |
| 4. Upgrade torchao >= 0.16.0 | High | Untested | PyTorch 2.10 compat unknown | Not recommended |
| 5. Newer NVIDIA base image | Unknown | Container rebuild | May not exist yet | Future option |

## Specific Fix for TASK-G4MOE-004

### Updated Step 3 (install command):

```bash
pip install transformers peft hf_transfer "datasets==4.3.0" "trl==0.26.1"
pip install --no-deps unsloth unsloth_zoo bitsandbytes
pip show unsloth | grep -i version
pip show peft | grep -i version    # NEW: record PEFT version too
```

### Code change in `train_gemma4_moe.py` (before `get_peft_model`):

```python
# --- Workaround: PEFT torchao version gate (TASK-REV-G4R1) ----------------
# PEFT's LoRA dispatcher raises ImportError when torchao is installed but
# below 0.16.0. The NVIDIA pytorch:25.11-py3 container ships 0.14.0+git.
# We don't use torchao quantisation, so bypass the check.
# Must patch both the source module AND the importing module, because
# `from peft.import_utils import is_torchao_available` creates a local
# reference that isn't affected by patching the source alone.
import peft.import_utils
import peft.tuners.lora.torchao
peft.import_utils.is_torchao_available = lambda: False
peft.tuners.lora.torchao.is_torchao_available = lambda: False
# ---------------------------------------------------------------------------
```

**Run 2 lesson**: Patching only `peft.import_utils` is insufficient because
`peft/tuners/lora/torchao.py` uses `from peft.import_utils import is_torchao_available`,
which binds the function to a local name in the torchao module's namespace. Both
references must be overwritten.

### Same change in `train_gemma4_dense.py` (before the equivalent `get_peft_model` call):

Same dual-module monkey-patch block, protecting against the latent vulnerability.

## Acceptance Criteria Assessment

| Criterion | Status |
|-----------|--------|
| Root cause identified | Yes — PEFT `is_torchao_available()` raises on torchao 0.14.0+git < 0.16.0 |
| Recommended fix with specific commands | Yes — monkey-patch (Rec 1) + version pin (Rec 4) |
| Updated Step 3 dependency install | Yes — add `pip show peft` to log, consider pinning |
| Assessment of Dense path impact | Yes — latently vulnerable, same fix needed (Rec 5) |
| Fix doesn't break PyTorch/CUDA/Unsloth | Yes — monkey-patch only affects unused torchao dispatch path |

## Appendix

### Environment snapshot from run-1.md

| Component | Version |
|-----------|---------|
| Unsloth | 2026.4.6 |
| Transformers | 5.5.4 |
| PyTorch | 2.10.0a0+b558c986e8.nv25.11 |
| CUDA | 12.1 |
| CUDA Toolkit | 13.0 |
| Triton | 3.5.0 |
| torchao | 0.14.0+git (container-bundled) |
| PEFT | unpinned (latest from PyPI) |
| Container | nvcr.io/nvidia/pytorch:25.11-py3 |
| Hardware | NVIDIA GB10, 121.6 GB max memory |

### Unsloth patch interaction

Unsloth 2026.4.6 patches PEFT's `_create_and_replace` at `vision.py:1469`, wrapping it as `_patched_car` which calls `_original_car`. The patch does NOT interact with the torchao dispatcher — it wraps the outer `_create_and_replace`, while the torchao check happens inside `_create_new_module` called by the original function. The monkey-patch of `is_torchao_available` is orthogonal to Unsloth's patching.
