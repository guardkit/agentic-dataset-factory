richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory$ cp docs/research/train_gemma4_moe.py ~/fine-tuning/scripts/
richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory$ ls ~/fine-tuning/scripts/
train_gemma4_moe.py  train_gemma4.py
richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory$ ls -la ~/fine-tuning/scripts/
total 44
drwxrwxr-x 2 richardwoollcott richardwoollcott  4096 Apr 18 11:11 .
drwxrwxr-x 5 richardwoollcott richardwoollcott  4096 Apr 10 14:26 ..
-rw-rw-r-- 1 richardwoollcott richardwoollcott 16440 Apr 18 12:03 train_gemma4_moe.py
-rw-rw-r-- 1 richardwoollcott richardwoollcott 13887 Apr 10 21:44 train_gemma4.py
richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory$ docker run --gpus all   --ulimit memlock=-1   --ulimit stack=67108864   -it   -v ~/fine-tuning/data:/workspace/data   -v ~/fine-tuning/output:/workspace/output   -v ~/fine-tuning/scripts:/workspace/scripts   -v ~/.cache/huggingface:/root/.cache/huggingface   --entrypoint /usr/bin/bash   nvcr.io/nvidia/pytorch:25.11-py3
root@6150ec61761e:/workspace# pip install transformers peft hf_transfer "datasets==4.3.0" "trl==0.26.1"
Collecting transformers
  Downloading transformers-5.5.4-py3-none-any.whl.metadata (32 kB)
Collecting peft
  Downloading peft-0.19.1-py3-none-any.whl.metadata (15 kB)
Collecting hf_transfer
  Downloading hf_transfer-0.1.9-cp38-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl.metadata (1.7 kB)
Collecting datasets==4.3.0
  Downloading datasets-4.3.0-py3-none-any.whl.metadata (18 kB)
Collecting trl==0.26.1
  Downloading trl-0.26.1-py3-none-any.whl.metadata (11 kB)
Requirement already satisfied: filelock in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (3.20.0)
Requirement already satisfied: numpy>=1.17 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (2.1.0)
Requirement already satisfied: pyarrow>=21.0.0 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (22.0.0)
Requirement already satisfied: dill<0.4.1,>=0.3.0 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (0.4.0)
Requirement already satisfied: pandas in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (2.3.3)
Requirement already satisfied: requests>=2.32.2 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (2.32.5)
Requirement already satisfied: httpx<1.0.0 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (0.28.1)
Requirement already satisfied: tqdm>=4.66.3 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (4.67.1)
Requirement already satisfied: xxhash in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (3.6.0)
Collecting multiprocess<0.70.17 (from datasets==4.3.0)
  Downloading multiprocess-0.70.16-py312-none-any.whl.metadata (7.2 kB)
Collecting fsspec<=2025.9.0,>=2023.1.0 (from fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0)
  Downloading fsspec-2025.9.0-py3-none-any.whl.metadata (10 kB)
Requirement already satisfied: huggingface-hub<2.0,>=0.25.0 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (1.1.2)
Requirement already satisfied: packaging in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (25.0)
Requirement already satisfied: pyyaml>=5.1 in /usr/local/lib/python3.12/dist-packages (from datasets==4.3.0) (6.0.3)
Collecting accelerate>=1.4.0 (from trl==0.26.1)
  Downloading accelerate-1.13.0-py3-none-any.whl.metadata (19 kB)
Requirement already satisfied: aiohttp!=4.0.0a0,!=4.0.0a1 in /usr/local/lib/python3.12/dist-packages (from fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (3.13.2)
Requirement already satisfied: anyio in /usr/local/lib/python3.12/dist-packages (from httpx<1.0.0->datasets==4.3.0) (4.11.0)
Requirement already satisfied: certifi in /usr/local/lib/python3.12/dist-packages (from httpx<1.0.0->datasets==4.3.0) (2025.10.5)
Requirement already satisfied: httpcore==1.* in /usr/local/lib/python3.12/dist-packages (from httpx<1.0.0->datasets==4.3.0) (1.0.9)
Requirement already satisfied: idna in /usr/local/lib/python3.12/dist-packages (from httpx<1.0.0->datasets==4.3.0) (3.11)
Requirement already satisfied: h11>=0.16 in /usr/local/lib/python3.12/dist-packages (from httpcore==1.*->httpx<1.0.0->datasets==4.3.0) (0.16.0)
Requirement already satisfied: hf-xet<2.0.0,>=1.2.0 in /usr/local/lib/python3.12/dist-packages (from huggingface-hub<2.0,>=0.25.0->datasets==4.3.0) (1.2.0)
Requirement already satisfied: shellingham in /usr/local/lib/python3.12/dist-packages (from huggingface-hub<2.0,>=0.25.0->datasets==4.3.0) (1.5.4)
Requirement already satisfied: typer-slim in /usr/local/lib/python3.12/dist-packages (from huggingface-hub<2.0,>=0.25.0->datasets==4.3.0) (0.20.0)
Requirement already satisfied: typing-extensions>=3.7.4.3 in /usr/local/lib/python3.12/dist-packages (from huggingface-hub<2.0,>=0.25.0->datasets==4.3.0) (4.15.0)
Collecting huggingface-hub<2.0,>=0.25.0 (from datasets==4.3.0)
  Downloading huggingface_hub-1.11.0-py3-none-any.whl.metadata (14 kB)
Requirement already satisfied: regex>=2025.10.22 in /usr/local/lib/python3.12/dist-packages (from transformers) (2025.11.3)
Requirement already satisfied: tokenizers<=0.23.0,>=0.22.0 in /usr/local/lib/python3.12/dist-packages (from transformers) (0.22.1)
Collecting typer (from transformers)
  Downloading typer-0.24.1-py3-none-any.whl.metadata (16 kB)
Requirement already satisfied: safetensors>=0.4.3 in /usr/local/lib/python3.12/dist-packages (from transformers) (0.6.2)
Collecting hf-xet<2.0.0,>=1.4.3 (from huggingface-hub<2.0,>=0.25.0->datasets==4.3.0)
  Downloading hf_xet-1.4.3-cp37-abi3-manylinux_2_28_aarch64.whl.metadata (4.9 kB)
Requirement already satisfied: psutil in /usr/local/lib/python3.12/dist-packages (from peft) (7.1.3)
Requirement already satisfied: torch>=1.13.0 in /usr/local/lib/python3.12/dist-packages (from peft) (2.10.0a0+b558c986e8.nv25.11)
Requirement already satisfied: aiohappyeyeballs>=2.5.0 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (2.6.1)
Requirement already satisfied: aiosignal>=1.4.0 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (1.4.0)
Requirement already satisfied: attrs>=17.3.0 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (25.4.0)
Requirement already satisfied: frozenlist>=1.1.1 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (1.8.0)
Requirement already satisfied: multidict<7.0,>=4.5 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (6.7.0)
Requirement already satisfied: propcache>=0.2.0 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (0.4.1)
Requirement already satisfied: yarl<2.0,>=1.17.0 in /usr/local/lib/python3.12/dist-packages (from aiohttp!=4.0.0a0,!=4.0.0a1->fsspec[http]<=2025.9.0,>=2023.1.0->datasets==4.3.0) (1.22.0)
Requirement already satisfied: charset_normalizer<4,>=2 in /usr/local/lib/python3.12/dist-packages (from requests>=2.32.2->datasets==4.3.0) (3.4.4)
Requirement already satisfied: urllib3<3,>=1.21.1 in /usr/local/lib/python3.12/dist-packages (from requests>=2.32.2->datasets==4.3.0) (2.5.0)
Requirement already satisfied: setuptools in /usr/local/lib/python3.12/dist-packages (from torch>=1.13.0->peft) (80.9.0)
Requirement already satisfied: sympy>=1.13.3 in /usr/local/lib/python3.12/dist-packages (from torch>=1.13.0->peft) (1.14.0)
Requirement already satisfied: networkx>=2.5.1 in /usr/local/lib/python3.12/dist-packages (from torch>=1.13.0->peft) (3.5)
Requirement already satisfied: jinja2 in /usr/local/lib/python3.12/dist-packages (from torch>=1.13.0->peft) (3.1.6)
Requirement already satisfied: mpmath<1.4,>=1.1.0 in /usr/local/lib/python3.12/dist-packages (from sympy>=1.13.3->torch>=1.13.0->peft) (1.3.0)
Requirement already satisfied: sniffio>=1.1 in /usr/local/lib/python3.12/dist-packages (from anyio->httpx<1.0.0->datasets==4.3.0) (1.3.1)
Requirement already satisfied: MarkupSafe>=2.0 in /usr/local/lib/python3.12/dist-packages (from jinja2->torch>=1.13.0->peft) (3.0.3)
Requirement already satisfied: python-dateutil>=2.8.2 in /usr/local/lib/python3.12/dist-packages (from pandas->datasets==4.3.0) (2.9.0.post0)
Requirement already satisfied: pytz>=2020.1 in /usr/local/lib/python3.12/dist-packages (from pandas->datasets==4.3.0) (2025.2)
Requirement already satisfied: tzdata>=2022.7 in /usr/local/lib/python3.12/dist-packages (from pandas->datasets==4.3.0) (2025.2)
Requirement already satisfied: six>=1.5 in /usr/local/lib/python3.12/dist-packages (from python-dateutil>=2.8.2->pandas->datasets==4.3.0) (1.16.0)
Requirement already satisfied: click>=8.2.1 in /usr/local/lib/python3.12/dist-packages (from typer->transformers) (8.3.0)
Requirement already satisfied: rich>=12.3.0 in /usr/local/lib/python3.12/dist-packages (from typer->transformers) (14.2.0)
Collecting annotated-doc>=0.0.2 (from typer->transformers)
  Downloading annotated_doc-0.0.4-py3-none-any.whl.metadata (6.6 kB)
Requirement already satisfied: markdown-it-py>=2.2.0 in /usr/local/lib/python3.12/dist-packages (from rich>=12.3.0->typer->transformers) (4.0.0)
Requirement already satisfied: pygments<3.0.0,>=2.13.0 in /usr/local/lib/python3.12/dist-packages (from rich>=12.3.0->typer->transformers) (2.19.2)
Requirement already satisfied: mdurl~=0.1 in /usr/local/lib/python3.12/dist-packages (from markdown-it-py>=2.2.0->rich>=12.3.0->typer->transformers) (0.1.2)
Downloading datasets-4.3.0-py3-none-any.whl (506 kB)
Downloading trl-0.26.1-py3-none-any.whl (517 kB)
Downloading fsspec-2025.9.0-py3-none-any.whl (199 kB)
Downloading multiprocess-0.70.16-py312-none-any.whl (146 kB)
Downloading transformers-5.5.4-py3-none-any.whl (10.2 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 10.2/10.2 MB 11.4 MB/s  0:00:00
Downloading huggingface_hub-1.11.0-py3-none-any.whl (645 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 645.5/645.5 kB 24.4 MB/s  0:00:00
Downloading hf_xet-1.4.3-cp37-abi3-manylinux_2_28_aarch64.whl (4.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.0/4.0 MB 11.7 MB/s  0:00:00
Downloading peft-0.19.1-py3-none-any.whl (680 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 680.7/680.7 kB 11.8 MB/s  0:00:00
Downloading hf_transfer-0.1.9-cp38-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (3.7 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.7/3.7 MB 14.3 MB/s  0:00:00
Downloading accelerate-1.13.0-py3-none-any.whl (383 kB)
Downloading typer-0.24.1-py3-none-any.whl (56 kB)
Downloading annotated_doc-0.0.4-py3-none-any.whl (5.3 kB)
Installing collected packages: multiprocess, hf-xet, hf_transfer, fsspec, annotated-doc, typer, huggingface-hub, datasets, accelerate, transformers, trl, peft
  Attempting uninstall: multiprocess
    Found existing installation: multiprocess 0.70.18
    Uninstalling multiprocess-0.70.18:
      Successfully uninstalled multiprocess-0.70.18
  Attempting uninstall: hf-xet
    Found existing installation: hf-xet 1.2.0
    Uninstalling hf-xet-1.2.0:
      Successfully uninstalled hf-xet-1.2.0
  Attempting uninstall: fsspec
    Found existing installation: fsspec 2025.10.0
    Uninstalling fsspec-2025.10.0:
      Successfully uninstalled fsspec-2025.10.0
  Attempting uninstall: huggingface-hub
    Found existing installation: huggingface_hub 1.1.2
    Uninstalling huggingface_hub-1.1.2:
      Successfully uninstalled huggingface_hub-1.1.2
  Attempting uninstall: datasets
    Found existing installation: datasets 4.4.1
    Uninstalling datasets-4.4.1:
      Successfully uninstalled datasets-4.4.1
Successfully installed accelerate-1.13.0 annotated-doc-0.0.4 datasets-4.3.0 fsspec-2025.9.0 hf-xet-1.4.3 hf_transfer-0.1.9 huggingface-hub-1.11.0 multiprocess-0.70.16 peft-0.19.1 transformers-5.5.4 trl-0.26.1 typer-0.24.1
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
root@6150ec61761e:/workspace# pip install --no-deps unsloth unsloth_zoo bitsandbytes
Collecting unsloth
  Downloading unsloth-2026.4.6-py3-none-any.whl.metadata (55 kB)
Collecting unsloth_zoo
  Downloading unsloth_zoo-2026.4.8-py3-none-any.whl.metadata (32 kB)
Collecting bitsandbytes
  Downloading bitsandbytes-0.49.2-py3-none-manylinux_2_24_aarch64.whl.metadata (10 kB)
Downloading unsloth-2026.4.6-py3-none-any.whl (65.3 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 65.3/65.3 MB 4.1 MB/s  0:00:15
Downloading unsloth_zoo-2026.4.8-py3-none-any.whl (421 kB)
Downloading bitsandbytes-0.49.2-py3-none-manylinux_2_24_aarch64.whl (31.4 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 31.4/31.4 MB 7.3 MB/s  0:00:04
Installing collected packages: unsloth_zoo, unsloth, bitsandbytes
Successfully installed bitsandbytes-0.49.2 unsloth-2026.4.6 unsloth_zoo-2026.4.8
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
root@6150ec61761e:/workspace# pip show unsloth | grep -i version
Version: 2026.4.6
root@6150ec61761e:/workspace# pip show peft | grep -i version
Version: 0.19.1
root@6150ec61761e:/workspace# python scripts/train_gemma4_moe.py --max-steps 30
🦥 Unsloth: Will patch your computer to enable 2x faster free finetuning.
🦥 Unsloth Zoo will now patch everything to make training faster!

============================================================
Loading unsloth/Gemma-4-26B-A4B-it
  QLoRA 4-bit: False
  16-bit LoRA: True
  Max sequence length: 4096
============================================================

==((====))==  Unsloth 2026.4.6: Fast Gemma4 patching. Transformers: 5.5.4.
   \\   /|    NVIDIA GB10. Num GPUs = 1. Max memory: 121.628 GB. Platform: Linux.
O^O/ \_/ \    Torch: 2.10.0a0+b558c986e8.nv25.11. CUDA: 12.1. CUDA Toolkit: 13.0. Triton: 3.5.0
\        /    Bfloat16 = TRUE. FA [Xformers = None. FA2 = True]
 "-____-"     Free license: http://github.com/unslothai/unsloth
Unsloth: Fast downloading is enabled - ignore downloading bars which are red colored!
Unsloth: `flash_attention_2` is not supported for `gemma4` because max attention head dim 512 exceeds the Flash Attention 2 limit of 256 - defaulting to `sdpa`.
Loading weights: 100%|█████████████████████████████████████████████████████████████████████████| 1013/1013 [03:29<00:00,  4.84it/s]
[accelerate.big_modeling|WARNING]Some parameters are on the meta device because they were offloaded to the cpu.
Unsloth: Detected MoE model with num_experts = 128 and target_modules = '(?:.*?(?:language|text).*?(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense).*?(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear).*?)|(?:\\bmodel\\.layers\\.[\\d]{1,}\\.(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense)\\.(?:(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear)))'. Enabling LoRA on MoE parameters: ['experts.gate_up_proj', 'experts.down_proj']
Traceback (most recent call last):
  File "/workspace/scripts/train_gemma4_moe.py", line 404, in <module>
    main()
  File "/workspace/scripts/train_gemma4_moe.py", line 248, in main
    model = FastModel.get_peft_model(
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/unsloth/models/vision.py", line 1482, in get_peft_model
    model = _get_peft_model(model, lora_config)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/mapping_func.py", line 122, in get_peft_model
    return MODEL_TYPE_TO_PEFT_MODEL_MAPPING[peft_config.task_type](
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/peft_model.py", line 1955, in __init__
    super().__init__(model, peft_config, adapter_name, **kwargs)
  File "/usr/local/lib/python3.12/dist-packages/peft/peft_model.py", line 129, in __init__
    self.base_model = cls(model, {adapter_name: peft_config}, adapter_name)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/tuners/tuners_utils.py", line 315, in __init__
    self.inject_adapter(self.model, adapter_name, low_cpu_mem_usage=low_cpu_mem_usage, state_dict=state_dict)
  File "/usr/local/lib/python3.12/dist-packages/peft/tuners/tuners_utils.py", line 913, in inject_adapter
    self._create_and_replace(
  File "/usr/local/lib/python3.12/dist-packages/unsloth/models/vision.py", line 1469, in _patched_car
    return _original_car(
           ^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/tuners/lora/model.py", line 269, in _create_and_replace
    new_module = self._create_new_module(lora_config, adapter_name, target, device_map=device_map, **kwargs)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/tuners/lora/model.py", line 418, in _create_new_module
    new_module = dispatcher(target, adapter_name, config=lora_config, **kwargs)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/tuners/lora/torchao.py", line 142, in dispatch_torchao
    if not is_torchao_available():
           ^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/dist-packages/peft/import_utils.py", line 143, in is_torchao_available
    raise ImportError(
ImportError: Found an incompatible version of torchao. Found version 0.14.0+git, but only versions above 0.16.0 are supported
root@6150ec61761e:/workspace# 

