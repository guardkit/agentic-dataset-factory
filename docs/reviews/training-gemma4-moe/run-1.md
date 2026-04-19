root@23247b24e8f6:/workspace# pip show unsloth | grep -i version
Version: 2026.4.6
root@23247b24e8f6:/workspace# cd /workspace
root@23247b24e8f6:/workspace# python scripts/train_gemma4_moe.py --max-steps 30
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
model.safetensors.index.json: 103kB [00:00, 102MB/s]
Fetching 2 files: 100%|█████████████████████████████████████████████████████████████████████████████| 2/2 [18:11<00:00, 545.80s/it]
Download complete: 100%|██████████████████████████████████████████████████████████████████████| 51.6G/51.6G [18:11<00:00, 47.3MB/s]
Loading weights: 100%|█████████████████████████████████████████████████████████████████████████| 1013/1013 [01:51<00:00,  9.13it/s]
generation_config.json: 100%|█████████████████████████████████████████████████████████████████████| 208/208 [00:00<00:00, 2.13MB/s]
[accelerate.big_modeling|WARNING]Some parameters are on the meta device because they were offloaded to the cpu.
processor_config.json: 1.69kB [00:00, 513kB/s]
chat_template.jinja: 16.4kB [00:00, 42.0MB/s]
tokenizer_config.json: 19.5kB [00:00, 91.5MB/s]
tokenizer.json: 100%|█████████████████████████████████████████████████████████████████████████| 32.2M/32.2M [00:01<00:00, 22.9MB/s]
Unsloth: Detected MoE model with num_experts = 128 and target_modules = '(?:.*?(?:language|text).*?(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense).*?(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear).*?)|(?:\\bmodel\\.layers\\.[\\d]{1,}\\.(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense)\\.(?:(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear)))'. Enabling LoRA on MoE parameters: ['experts.gate_up_proj', 'experts.down_proj']
Traceback (most recent call last):
  File "/workspace/scripts/train_gemma4_moe.py", line 397, in <module>
    main()
  File "/workspace/scripts/train_gemma4_moe.py", line 241, in main
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
root@23247b24e8f6:/workspace# 

