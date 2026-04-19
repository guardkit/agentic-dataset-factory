richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory$ docker start -ai 6150ec61761e
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
Loading weights: 100%|█████████████████████████████████████████████████████████████████████████| 1013/1013 [04:24<00:00,  3.83it/s]
Unsloth: Detected MoE model with num_experts = 128 and target_modules = '(?:.*?(?:language|text).*?(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense).*?(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear).*?)|(?:\\bmodel\\.layers\\.[\\d]{1,}\\.(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense)\\.(?:(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear)))'. Enabling LoRA on MoE parameters: ['experts.gate_up_proj', 'experts.down_proj']
Chat template: gemma-4-thinking
  First record keys: ['messages', 'metadata']
  First message keys: ['role', 'content']
Loaded 1736 training examples from /workspace/data/train.jsonl
  First example: 3 turns, roles: ['system', 'user', 'assistant']
  First user msg (truncated): You are an expert GCSE English tutor supporting a Year 10 student studying the AQA specification.
Your role is to guide ...
Unsloth: Standardizing formats (num_proc=24): 100%|███████████████████████████████████| 1736/1736 [00:01<00:00, 1462.55 examples/s]
Map: 100%|███████████████████████████████████████████████████████████████████████████| 1736/1736 [00:00<00:00, 18538.50 examples/s]

--- Sample formatted text (first 500 chars) ---
<|turn>user
You are an expert GCSE English tutor supporting a Year 10 student studying the AQA specification.
Your role is to guide the student using Socratic questioning — help them discover answers
rather than providing them directly. You have deep knowledge of:
- AQA English Language (8700): Paper 1 and Paper 2 question types
- AQA English Literature (8702): Set texts including Macbeth, A Christmas Carol,
  An Inspector Calls, and the Power and Conflict poetry anthology
- The AO1–AO6 assessme
--- End sample ---

Unsloth: Tokenizing ["text"] (num_proc=24): 100%|███████████████████████████████████████| 1736/1736 [00:51<00:00, 33.76 examples/s]
Map (num_proc=24): 100%|██████████████████████████████████████████████████████████████| 1736/1736 [00:00<00:00, 1774.10 examples/s]
Filter (num_proc=24): 100%|███████████████████████████████████████████████████████████| 1736/1736 [00:01<00:00, 1720.03 examples/s]
Verifying response-only masking...
  Masked tokens: 223/404 (55.2% masked)

============================================================
Starting training...
  Max steps: 30
  Effective batch size: 4
  Learning rate: 0.0002
  Output: /workspace/output/gcse-tutor-gemma4-26b-moe
============================================================

The tokenizer has new PAD/BOS/EOS tokens that differ from the model config and generation config. The model config and generation config were aligned accordingly, being updated with the tokenizer's values. Updated tokens: {'bos_token_id': 2}.
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 1,736 | Num Epochs = 1 | Total steps = 30
O^O/ \_/ \    Batch size per device = 1 | Gradient accumulation steps = 4
\        /    Data Parallel GPUs = 1 | Total batch size (1 x 4 x 1) = 4
 "-____-"     Trainable parameters = 494,376,960 of 26,300,310,832 (1.88% trained)
  0%|                                                                                                       | 0/30 [00:00<?, ?it/s]Unsloth: Will smartly offload gradients to save VRAM!
{'loss': '2.161', 'grad_norm': '10.78', 'learning_rate': '0', 'epoch': '0.002304'}                                                 
{'loss': '2.352', 'grad_norm': '3.877', 'learning_rate': '2e-05', 'epoch': '0.004608'}                                             
{'loss': '2.338', 'grad_norm': '5.601', 'learning_rate': '4e-05', 'epoch': '0.006912'}                                             
{'loss': '2.352', 'grad_norm': '6.402', 'learning_rate': '6e-05', 'epoch': '0.009217'}                                             
{'loss': '2.692', 'grad_norm': '3.782', 'learning_rate': '8e-05', 'epoch': '0.01152'}                                              
{'loss': '2.253', 'grad_norm': '3.881', 'learning_rate': '0.0001', 'epoch': '0.01382'}                                             
{'loss': '2.179', 'grad_norm': '2.496', 'learning_rate': '0.00012', 'epoch': '0.01613'}                                            
{'loss': '2.248', 'grad_norm': '3.432', 'learning_rate': '0.00014', 'epoch': '0.01843'}                                            
{'loss': '1.9', 'grad_norm': '2.54', 'learning_rate': '0.00016', 'epoch': '0.02074'}                                               
{'loss': '1.571', 'grad_norm': '2.282', 'learning_rate': '0.00018', 'epoch': '0.02304'}                                            
{'loss': '1.472', 'grad_norm': '3.412', 'learning_rate': '0.0002', 'epoch': '0.02535'}                                             
{'loss': '1.442', 'grad_norm': '11.26', 'learning_rate': '0.00019', 'epoch': '0.02765'}                                            
{'loss': '1.611', 'grad_norm': '1.562', 'learning_rate': '0.00018', 'epoch': '0.02995'}                                            
{'loss': '1.689', 'grad_norm': '5.429', 'learning_rate': '0.00017', 'epoch': '0.03226'}                                            
{'loss': '1.606', 'grad_norm': '1.622', 'learning_rate': '0.00016', 'epoch': '0.03456'}                                            
{'loss': '1.541', 'grad_norm': '1.023', 'learning_rate': '0.00015', 'epoch': '0.03687'}                                            
{'loss': '1.422', 'grad_norm': '0.89', 'learning_rate': '0.00014', 'epoch': '0.03917'}                                             
{'loss': '1.4', 'grad_norm': '0.7669', 'learning_rate': '0.00013', 'epoch': '0.04147'}                                             
{'loss': '1.312', 'grad_norm': '0.7297', 'learning_rate': '0.00012', 'epoch': '0.04378'}                                           
{'loss': '1.315', 'grad_norm': '0.7016', 'learning_rate': '0.00011', 'epoch': '0.04608'}                                           
{'loss': '1.207', 'grad_norm': '0.6173', 'learning_rate': '0.0001', 'epoch': '0.04839'}                                            
{'loss': '1.182', 'grad_norm': '0.4722', 'learning_rate': '9e-05', 'epoch': '0.05069'}                                             
{'loss': '1.025', 'grad_norm': '0.3802', 'learning_rate': '8e-05', 'epoch': '0.053'}                                               
{'loss': '1.16', 'grad_norm': '0.5837', 'learning_rate': '7e-05', 'epoch': '0.0553'}                                               
{'loss': '1.203', 'grad_norm': '0.4736', 'learning_rate': '6e-05', 'epoch': '0.0576'}                                              
{'loss': '1.103', 'grad_norm': '0.6776', 'learning_rate': '5e-05', 'epoch': '0.05991'}                                             
{'loss': '0.9461', 'grad_norm': '0.6886', 'learning_rate': '4e-05', 'epoch': '0.06221'}                                            
{'loss': '1.204', 'grad_norm': '0.7354', 'learning_rate': '3e-05', 'epoch': '0.06452'}                                             
{'loss': '1.384', 'grad_norm': '0.8488', 'learning_rate': '2e-05', 'epoch': '0.06682'}                                             
{'loss': '1.147', 'grad_norm': '0.672', 'learning_rate': '1e-05', 'epoch': '0.06912'}                                              
{'train_runtime': '342.8', 'train_samples_per_second': '0.35', 'train_steps_per_second': '0.088', 'train_loss': '1.614', 'epoch': '0.06912'}
100%|██████████████████████████████████████████████████████████████████████████████████████████████| 30/30 [05:42<00:00, 11.43s/it]

Training complete!
  Total steps: 30
  Final loss: 1.6140

Saving LoRA adapter to /workspace/output/gcse-tutor-gemma4-26b-moe/lora-adapter...
Saving merged 16-bit model to /workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  2.76it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files...█| 1/1 [00:00<00:00,  2.76it/s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`: 100%|█| 2/2 [00:44<00:00, 22.39s
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`█| 2/2 [00:44<00:00, 18.75s
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|█████████████████████████████████████████████████| 2/2 [00:00<00:00, 106184.91it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████████████████████████████████| 2/2 [06:02<00:00, 181.13s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`| 2/2 [06:02<00:00, 151.58s/it]
Download complete: : 0.00B [06:50, ?B/s]
Exporting GGUF to /workspace/output/gcse-tutor-gemma4-26b-moe/gguf...
Unsloth: Merging model weights to 16-bit format...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|██████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00,  3.12it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files...█| 1/1 [00:00<00:00,  3.12it/s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`: 100%|█████| 2/2 [01:08<00:00, 34.32s/it]
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`█████| 2/2 [01:08<00:00, 28.79s/it]
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|█████████████████████████████████████████████████| 2/2 [00:00<00:00, 101067.57it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████████████████████████████████| 2/2 [05:58<00:00, 179.10s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`████████| 2/2 [05:58<00:00, 150.02s/it]
Download complete: : 0.00B [07:11, ?B/s]
Unsloth: Converting to GGUF format...
==((====))==  Unsloth: Conversion from HF to GGUF information
   \\   /|    [0] Installing llama.cpp might take 3 minutes.
O^O/ \_/ \    [1] Converting HF to GGUF bf16 might take 3 minutes.
\        /    [2] Converting GGUF bf16 to ['q4_k_m'] might take 10 minutes each.
 "-____-"     In total, you will have to wait at least 16 minutes.

Unsloth: Installing llama.cpp. This might take 3 minutes...
Unsloth: Updating system package directories
Unsloth: Cloning llama.cpp repository...
Unsloth: Building llama.cpp - please wait 1 to 3 minutes
Unsloth: Successfully installed llama.cpp!
Unsloth: Preparing converter script...
[unsloth_zoo.llama_cpp|WARNING]Unsloth: Qwen2MoE num_experts patch target not found.
Unsloth: [1] Converting model into bf16 GGUF format.
This might take 3 minutes...
Found 2 sharded output files for text model
Unsloth: Initial conversion completed! Files: ['/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-00001-of-00002.gguf', '/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf', '/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-mmproj.gguf']
Unsloth: [2] Converting GGUF bf16 into q4_k_m. This might take 10 minutes...
Unsloth: Model files cleanup...
Unsloth: All GGUF conversions completed successfully!
Generated files: ['/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf', '/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-mmproj.gguf', '/workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf']


Unsloth: example usage for Multimodal LLMs: /root/.unsloth/llama.cpp/llama-mtmd-cli -m /workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf --mmproj /workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.BF16-00002-of-00002.gguf
Unsloth: load image inside llama.cpp runner: /image test_image.jpg
Unsloth: Prompt model to describe the image
Unsloth: Saved Ollama Modelfile to /workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/Modelfile
Unsloth: convert model to ollama format by running - ollama create model_name -f /workspace/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/Modelfile
  Exported: q4_k_m

============================================================
All done! Next steps:
  1. Test with vLLM:  vllm serve /workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit
  2. Or use GGUF:     ls /workspace/output/gcse-tutor-gemma4-26b-moe/gguf/
  3. LoRA adapter:    /workspace/output/gcse-tutor-gemma4-26b-moe/lora-adapter/
============================================================

root@6150ec61761e:/workspace# 

