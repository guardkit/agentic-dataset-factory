root@6150ec61761e:/workspace# python scripts/train_gemma4_moe.py \
  --epochs 1 \
  --save-steps 200 \
  --lr 2e-4
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
Loading weights: 100%|█████████████████████████████████████████████████████████████████████████| 1013/1013 [03:57<00:00,  4.26it/s]
Unsloth: Detected MoE model with num_experts = 128 and target_modules = '(?:.*?(?:language|text).*?(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense).*?(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear).*?)|(?:\\bmodel\\.layers\\.[\\d]{1,}\\.(?:self_attn|attention|attn|mlp|feed_forward|ffn|dense)\\.(?:(?:q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|proj|linear)))'. Enabling LoRA on MoE parameters: ['experts.gate_up_proj', 'experts.down_proj']
Chat template: gemma-4-thinking
  First record keys: ['messages', 'metadata']
  First message keys: ['role', 'content']
Loaded 1736 training examples from /workspace/data/train.jsonl
  First example: 3 turns, roles: ['system', 'user', 'assistant']
  First user msg (truncated): You are an expert GCSE English tutor supporting a Year 10 student studying the AQA specification.
Your role is to guide ...
Unsloth: Standardizing formats (num_proc=24): 100%|███████████████████████████████████| 1736/1736 [00:01<00:00, 1463.74 examples/s]
Map: 100%|███████████████████████████████████████████████████████████████████████████| 1736/1736 [00:00<00:00, 19831.60 examples/s]

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

Unsloth: Tokenizing ["text"] (num_proc=24): 100%|███████████████████████████████████████| 1736/1736 [00:51<00:00, 33.91 examples/s]
Map (num_proc=24): 100%|██████████████████████████████████████████████████████████████| 1736/1736 [00:00<00:00, 1890.61 examples/s]
Filter (num_proc=24): 100%|███████████████████████████████████████████████████████████| 1736/1736 [00:00<00:00, 1908.61 examples/s]
Verifying response-only masking...
  Masked tokens: 223/404 (55.2% masked)

============================================================
Starting training...
  Epochs: 1
  Effective batch size: 4
  Learning rate: 0.0002
  Output: /workspace/output/gcse-tutor-gemma4-26b-moe
============================================================

The tokenizer has new PAD/BOS/EOS tokens that differ from the model config and generation config. The model config and generation config were aligned accordingly, being updated with the tokenizer's values. Updated tokens: {'bos_token_id': 2}.
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 1,736 | Num Epochs = 1 | Total steps = 434
O^O/ \_/ \    Batch size per device = 1 | Gradient accumulation steps = 4
\        /    Data Parallel GPUs = 1 | Total batch size (1 x 4 x 1) = 4
 "-____-"     Trainable parameters = 494,376,960 of 26,300,310,832 (1.88% trained)
  0%|                                                                                                      | 0/434 [00:00<?, ?it/s]Unsloth: Will smartly offload gradients to save VRAM!
{'loss': '2.161', 'grad_norm': '10.78', 'learning_rate': '0', 'epoch': '0.002304'}                                                 
{'loss': '2.352', 'grad_norm': '3.894', 'learning_rate': '2e-05', 'epoch': '0.004608'}                                             
{'loss': '2.342', 'grad_norm': '1.991', 'learning_rate': '4e-05', 'epoch': '0.006912'}                                             
{'loss': '2.343', 'grad_norm': '2.653', 'learning_rate': '6e-05', 'epoch': '0.009217'}                                             
{'loss': '2.683', 'grad_norm': '6.399', 'learning_rate': '8e-05', 'epoch': '0.01152'}                                              
{'loss': '2.241', 'grad_norm': '2.574', 'learning_rate': '0.0001', 'epoch': '0.01382'}                                             
{'loss': '2.185', 'grad_norm': '2.968', 'learning_rate': '0.00012', 'epoch': '0.01613'}                                            
{'loss': '2.202', 'grad_norm': '3.065', 'learning_rate': '0.00014', 'epoch': '0.01843'}                                            
{'loss': '1.895', 'grad_norm': '1.593', 'learning_rate': '0.00016', 'epoch': '0.02074'}                                            
{'loss': '1.566', 'grad_norm': '1.374', 'learning_rate': '0.00018', 'epoch': '0.02304'}                                            
{'loss': '1.463', 'grad_norm': '0.7789', 'learning_rate': '0.0002', 'epoch': '0.02535'}                                            
{'loss': '1.433', 'grad_norm': '3.999', 'learning_rate': '0.0001995', 'epoch': '0.02765'}                                          
{'loss': '1.577', 'grad_norm': '2.818', 'learning_rate': '0.0001991', 'epoch': '0.02995'}                                          
{'loss': '1.678', 'grad_norm': '1.822', 'learning_rate': '0.0001986', 'epoch': '0.03226'}                                          
{'loss': '1.591', 'grad_norm': '1.899', 'learning_rate': '0.0001981', 'epoch': '0.03456'}                                          
{'loss': '1.529', 'grad_norm': '1.238', 'learning_rate': '0.0001976', 'epoch': '0.03687'}                                          
{'loss': '1.39', 'grad_norm': '2.107', 'learning_rate': '0.0001972', 'epoch': '0.03917'}                                           
{'loss': '1.364', 'grad_norm': '0.7427', 'learning_rate': '0.0001967', 'epoch': '0.04147'}                                         
{'loss': '1.266', 'grad_norm': '0.7301', 'learning_rate': '0.0001962', 'epoch': '0.04378'}                                         
{'loss': '1.292', 'grad_norm': '0.7001', 'learning_rate': '0.0001958', 'epoch': '0.04608'}                                         
{'loss': '1.158', 'grad_norm': '1.029', 'learning_rate': '0.0001953', 'epoch': '0.04839'}                                          
{'loss': '1.14', 'grad_norm': '0.4599', 'learning_rate': '0.0001948', 'epoch': '0.05069'}                                          
{'loss': '0.9909', 'grad_norm': '0.8172', 'learning_rate': '0.0001943', 'epoch': '0.053'}                                          
{'loss': '1.092', 'grad_norm': '0.8712', 'learning_rate': '0.0001939', 'epoch': '0.0553'}                                          
{'loss': '1.149', 'grad_norm': '7.689', 'learning_rate': '0.0001934', 'epoch': '0.0576'}                                           
{'loss': '1.038', 'grad_norm': '34.4', 'learning_rate': '0.0001929', 'epoch': '0.05991'}                                           
{'loss': '0.8619', 'grad_norm': '0.9653', 'learning_rate': '0.0001925', 'epoch': '0.06221'}                                        
{'loss': '1.127', 'grad_norm': '0.9458', 'learning_rate': '0.000192', 'epoch': '0.06452'}                                          
{'loss': '1.323', 'grad_norm': '2.183', 'learning_rate': '0.0001915', 'epoch': '0.06682'}                                          
{'loss': '1.044', 'grad_norm': '2.602', 'learning_rate': '0.000191', 'epoch': '0.06912'}                                           
{'loss': '1.121', 'grad_norm': '0.7006', 'learning_rate': '0.0001906', 'epoch': '0.07143'}                                         
{'loss': '1.056', 'grad_norm': '0.5708', 'learning_rate': '0.0001901', 'epoch': '0.07373'}                                         
{'loss': '1.053', 'grad_norm': '0.8394', 'learning_rate': '0.0001896', 'epoch': '0.07604'}                                         
{'loss': '1.321', 'grad_norm': '0.8169', 'learning_rate': '0.0001892', 'epoch': '0.07834'}                                         
{'loss': '0.9737', 'grad_norm': '0.5985', 'learning_rate': '0.0001887', 'epoch': '0.08065'}                                        
{'loss': '0.9687', 'grad_norm': '0.4873', 'learning_rate': '0.0001882', 'epoch': '0.08295'}                                        
{'loss': '1.026', 'grad_norm': '0.4936', 'learning_rate': '0.0001877', 'epoch': '0.08525'}                                         
{'loss': '0.9062', 'grad_norm': '0.5829', 'learning_rate': '0.0001873', 'epoch': '0.08756'}                                        
{'loss': '0.821', 'grad_norm': '0.675', 'learning_rate': '0.0001868', 'epoch': '0.08986'}                                          
{'loss': '1.043', 'grad_norm': '0.5499', 'learning_rate': '0.0001863', 'epoch': '0.09217'}                                         
{'loss': '0.9738', 'grad_norm': '0.3991', 'learning_rate': '0.0001858', 'epoch': '0.09447'}                                        
{'loss': '0.9565', 'grad_norm': '0.5177', 'learning_rate': '0.0001854', 'epoch': '0.09677'}                                        
{'loss': '0.8896', 'grad_norm': '0.4682', 'learning_rate': '0.0001849', 'epoch': '0.09908'}                                        
{'loss': '0.9582', 'grad_norm': '0.4308', 'learning_rate': '0.0001844', 'epoch': '0.1014'}                                         
{'loss': '0.907', 'grad_norm': '1.765', 'learning_rate': '0.000184', 'epoch': '0.1037'}                                            
{'loss': '0.919', 'grad_norm': '0.5797', 'learning_rate': '0.0001835', 'epoch': '0.106'}                                           
{'loss': '0.9852', 'grad_norm': '0.6589', 'learning_rate': '0.000183', 'epoch': '0.1083'}                                          
{'loss': '0.8242', 'grad_norm': '0.6714', 'learning_rate': '0.0001825', 'epoch': '0.1106'}                                         
{'loss': '0.966', 'grad_norm': '0.8512', 'learning_rate': '0.0001821', 'epoch': '0.1129'}                                          
{'loss': '0.9162', 'grad_norm': '0.7037', 'learning_rate': '0.0001816', 'epoch': '0.1152'}                                         
{'loss': '0.8966', 'grad_norm': '0.5915', 'learning_rate': '0.0001811', 'epoch': '0.1175'}                                         
{'loss': '0.8814', 'grad_norm': '0.5484', 'learning_rate': '0.0001807', 'epoch': '0.1198'}                                         
{'loss': '0.8779', 'grad_norm': '0.5624', 'learning_rate': '0.0001802', 'epoch': '0.1221'}                                         
{'loss': '0.866', 'grad_norm': '0.5332', 'learning_rate': '0.0001797', 'epoch': '0.1244'}                                          
{'loss': '0.8499', 'grad_norm': '0.6571', 'learning_rate': '0.0001792', 'epoch': '0.1267'}                                         
{'loss': '0.8033', 'grad_norm': '0.5062', 'learning_rate': '0.0001788', 'epoch': '0.129'}                                          
{'loss': '0.7995', 'grad_norm': '0.5534', 'learning_rate': '0.0001783', 'epoch': '0.1313'}                                         
{'loss': '0.8301', 'grad_norm': '0.5824', 'learning_rate': '0.0001778', 'epoch': '0.1336'}                                         
{'loss': '0.8902', 'grad_norm': '0.7245', 'learning_rate': '0.0001774', 'epoch': '0.1359'}                                         
{'loss': '0.8056', 'grad_norm': '0.5845', 'learning_rate': '0.0001769', 'epoch': '0.1382'}                                         
{'loss': '0.981', 'grad_norm': '0.6608', 'learning_rate': '0.0001764', 'epoch': '0.1406'}                                          
{'loss': '0.8221', 'grad_norm': '0.7092', 'learning_rate': '0.0001759', 'epoch': '0.1429'}                                         
{'loss': '0.8819', 'grad_norm': '0.5884', 'learning_rate': '0.0001755', 'epoch': '0.1452'}                                         
{'loss': '0.7979', 'grad_norm': '0.7071', 'learning_rate': '0.000175', 'epoch': '0.1475'}                                          
{'loss': '0.8438', 'grad_norm': '0.4961', 'learning_rate': '0.0001745', 'epoch': '0.1498'}                                         
{'loss': '0.7704', 'grad_norm': '0.6735', 'learning_rate': '0.0001741', 'epoch': '0.1521'}                                         
{'loss': '0.7813', 'grad_norm': '0.623', 'learning_rate': '0.0001736', 'epoch': '0.1544'}                                          
{'loss': '0.9117', 'grad_norm': '0.8534', 'learning_rate': '0.0001731', 'epoch': '0.1567'}                                         
{'loss': '0.8359', 'grad_norm': '1.474', 'learning_rate': '0.0001726', 'epoch': '0.159'}                                           
{'loss': '0.8627', 'grad_norm': '0.6823', 'learning_rate': '0.0001722', 'epoch': '0.1613'}                                         
{'loss': '0.812', 'grad_norm': '0.5694', 'learning_rate': '0.0001717', 'epoch': '0.1636'}                                          
{'loss': '0.7369', 'grad_norm': '0.7233', 'learning_rate': '0.0001712', 'epoch': '0.1659'}                                         
{'loss': '0.7186', 'grad_norm': '0.6657', 'learning_rate': '0.0001708', 'epoch': '0.1682'}                                         
{'loss': '0.9498', 'grad_norm': '90.91', 'learning_rate': '0.0001703', 'epoch': '0.1705'}                                          
{'loss': '0.9278', 'grad_norm': '0.6249', 'learning_rate': '0.0001698', 'epoch': '0.1728'}                                         
{'loss': '0.7554', 'grad_norm': '0.7436', 'learning_rate': '0.0001693', 'epoch': '0.1751'}                                         
{'loss': '0.7337', 'grad_norm': '0.6853', 'learning_rate': '0.0001689', 'epoch': '0.1774'}                                         
{'loss': '0.8052', 'grad_norm': '0.7028', 'learning_rate': '0.0001684', 'epoch': '0.1797'}                                         
{'loss': '0.815', 'grad_norm': '0.6275', 'learning_rate': '0.0001679', 'epoch': '0.182'}                                           
{'loss': '1.167', 'grad_norm': '0.978', 'learning_rate': '0.0001675', 'epoch': '0.1843'}                                           
{'loss': '0.8994', 'grad_norm': '0.7069', 'learning_rate': '0.000167', 'epoch': '0.1866'}                                          
{'loss': '0.8547', 'grad_norm': '0.5695', 'learning_rate': '0.0001665', 'epoch': '0.1889'}                                         
{'loss': '0.7685', 'grad_norm': '0.5538', 'learning_rate': '0.000166', 'epoch': '0.1912'}                                          
{'loss': '0.8621', 'grad_norm': '0.5865', 'learning_rate': '0.0001656', 'epoch': '0.1935'}                                         
{'loss': '0.7599', 'grad_norm': '0.5255', 'learning_rate': '0.0001651', 'epoch': '0.1959'}                                         
{'loss': '0.813', 'grad_norm': '0.5409', 'learning_rate': '0.0001646', 'epoch': '0.1982'}                                          
{'loss': '0.8009', 'grad_norm': '0.7568', 'learning_rate': '0.0001642', 'epoch': '0.2005'}                                         
{'loss': '0.7555', 'grad_norm': '5.999', 'learning_rate': '0.0001637', 'epoch': '0.2028'}                                          
{'loss': '0.7337', 'grad_norm': '0.7181', 'learning_rate': '0.0001632', 'epoch': '0.2051'}                                         
{'loss': '1.115', 'grad_norm': '0.7373', 'learning_rate': '0.0001627', 'epoch': '0.2074'}                                          
{'loss': '0.7428', 'grad_norm': '0.6179', 'learning_rate': '0.0001623', 'epoch': '0.2097'}                                         
{'loss': '0.8194', 'grad_norm': '0.634', 'learning_rate': '0.0001618', 'epoch': '0.212'}                                           
{'loss': '0.6419', 'grad_norm': '0.6178', 'learning_rate': '0.0001613', 'epoch': '0.2143'}                                         
{'loss': '0.8367', 'grad_norm': '0.6013', 'learning_rate': '0.0001608', 'epoch': '0.2166'}                                         
{'loss': '0.8822', 'grad_norm': '1.744', 'learning_rate': '0.0001604', 'epoch': '0.2189'}                                          
{'loss': '0.7577', 'grad_norm': '0.5872', 'learning_rate': '0.0001599', 'epoch': '0.2212'}                                         
{'loss': '0.8281', 'grad_norm': '0.6671', 'learning_rate': '0.0001594', 'epoch': '0.2235'}                                         
{'loss': '0.7958', 'grad_norm': '0.731', 'learning_rate': '0.000159', 'epoch': '0.2258'}                                           
{'loss': '0.9954', 'grad_norm': '0.7777', 'learning_rate': '0.0001585', 'epoch': '0.2281'}                                         
{'loss': '0.8697', 'grad_norm': '0.7342', 'learning_rate': '0.000158', 'epoch': '0.2304'}                                          
{'loss': '0.6825', 'grad_norm': '0.6267', 'learning_rate': '0.0001575', 'epoch': '0.2327'}                                         
{'loss': '0.6774', 'grad_norm': '0.593', 'learning_rate': '0.0001571', 'epoch': '0.235'}                                           
{'loss': '0.8134', 'grad_norm': '0.9689', 'learning_rate': '0.0001566', 'epoch': '0.2373'}                                         
{'loss': '0.6931', 'grad_norm': '0.6487', 'learning_rate': '0.0001561', 'epoch': '0.2396'}                                         
{'loss': '0.8132', 'grad_norm': '1.106', 'learning_rate': '0.0001557', 'epoch': '0.2419'}                                          
{'loss': '0.808', 'grad_norm': '0.4959', 'learning_rate': '0.0001552', 'epoch': '0.2442'}                                          
{'loss': '0.8651', 'grad_norm': '0.6356', 'learning_rate': '0.0001547', 'epoch': '0.2465'}                                         
{'loss': '0.6879', 'grad_norm': '0.6064', 'learning_rate': '0.0001542', 'epoch': '0.2488'}                                         
{'loss': '0.6723', 'grad_norm': '1.49', 'learning_rate': '0.0001538', 'epoch': '0.2512'}                                           
{'loss': '0.809', 'grad_norm': '0.6521', 'learning_rate': '0.0001533', 'epoch': '0.2535'}                                          
{'loss': '0.7133', 'grad_norm': '0.6212', 'learning_rate': '0.0001528', 'epoch': '0.2558'}                                         
{'loss': '0.7179', 'grad_norm': '0.6313', 'learning_rate': '0.0001524', 'epoch': '0.2581'}                                         
{'loss': '0.7811', 'grad_norm': '0.8279', 'learning_rate': '0.0001519', 'epoch': '0.2604'}                                         
{'loss': '0.6669', 'grad_norm': '4.545', 'learning_rate': '0.0001514', 'epoch': '0.2627'}                                          
{'loss': '0.7445', 'grad_norm': '0.8967', 'learning_rate': '0.0001509', 'epoch': '0.265'}                                          
{'loss': '0.6391', 'grad_norm': '3.084', 'learning_rate': '0.0001505', 'epoch': '0.2673'}                                          
{'loss': '0.6347', 'grad_norm': '0.9091', 'learning_rate': '0.00015', 'epoch': '0.2696'}                                           
{'loss': '0.8575', 'grad_norm': '0.5974', 'learning_rate': '0.0001495', 'epoch': '0.2719'}                                         
{'loss': '0.6068', 'grad_norm': '3.526', 'learning_rate': '0.0001491', 'epoch': '0.2742'}                                          
{'loss': '0.6964', 'grad_norm': '0.6733', 'learning_rate': '0.0001486', 'epoch': '0.2765'}                                         
{'loss': '0.7812', 'grad_norm': '0.7931', 'learning_rate': '0.0001481', 'epoch': '0.2788'}                                         
{'loss': '0.7119', 'grad_norm': '0.6957', 'learning_rate': '0.0001476', 'epoch': '0.2811'}                                         
{'loss': '0.7424', 'grad_norm': '0.7186', 'learning_rate': '0.0001472', 'epoch': '0.2834'}                                         
{'loss': '0.6509', 'grad_norm': '0.7799', 'learning_rate': '0.0001467', 'epoch': '0.2857'}                                         
{'loss': '0.7383', 'grad_norm': '1.765', 'learning_rate': '0.0001462', 'epoch': '0.288'}                                           
{'loss': '0.784', 'grad_norm': '0.6944', 'learning_rate': '0.0001458', 'epoch': '0.2903'}                                          
{'loss': '0.8013', 'grad_norm': '0.6153', 'learning_rate': '0.0001453', 'epoch': '0.2926'}                                         
{'loss': '0.7633', 'grad_norm': '1.127', 'learning_rate': '0.0001448', 'epoch': '0.2949'}                                          
{'loss': '0.8394', 'grad_norm': '0.6915', 'learning_rate': '0.0001443', 'epoch': '0.2972'}                                         
{'loss': '0.7189', 'grad_norm': '0.7345', 'learning_rate': '0.0001439', 'epoch': '0.2995'}                                         
{'loss': '0.8663', 'grad_norm': '0.534', 'learning_rate': '0.0001434', 'epoch': '0.3018'}                                          
{'loss': '0.7634', 'grad_norm': '0.6317', 'learning_rate': '0.0001429', 'epoch': '0.3041'}                                         
{'loss': '0.6971', 'grad_norm': '0.7177', 'learning_rate': '0.0001425', 'epoch': '0.3065'}                                         
{'loss': '0.6897', 'grad_norm': '0.9138', 'learning_rate': '0.000142', 'epoch': '0.3088'}                                          
{'loss': '0.6841', 'grad_norm': '0.6346', 'learning_rate': '0.0001415', 'epoch': '0.3111'}                                         
{'loss': '0.7981', 'grad_norm': '1.92', 'learning_rate': '0.000141', 'epoch': '0.3134'}                                            
{'loss': '0.6902', 'grad_norm': '0.6517', 'learning_rate': '0.0001406', 'epoch': '0.3157'}                                         
{'loss': '0.6974', 'grad_norm': '0.6293', 'learning_rate': '0.0001401', 'epoch': '0.318'}                                          
{'loss': '0.7129', 'grad_norm': '0.6866', 'learning_rate': '0.0001396', 'epoch': '0.3203'}                                         
{'loss': '0.7388', 'grad_norm': '0.8076', 'learning_rate': '0.0001392', 'epoch': '0.3226'}                                         
{'loss': '0.701', 'grad_norm': '0.8143', 'learning_rate': '0.0001387', 'epoch': '0.3249'}                                          
{'loss': '0.7216', 'grad_norm': '0.7038', 'learning_rate': '0.0001382', 'epoch': '0.3272'}                                         
{'loss': '0.9073', 'grad_norm': '0.9581', 'learning_rate': '0.0001377', 'epoch': '0.3295'}                                         
{'loss': '0.6811', 'grad_norm': '2.702', 'learning_rate': '0.0001373', 'epoch': '0.3318'}                                          
{'loss': '0.7283', 'grad_norm': '0.6991', 'learning_rate': '0.0001368', 'epoch': '0.3341'}                                         
{'loss': '0.6455', 'grad_norm': '0.7042', 'learning_rate': '0.0001363', 'epoch': '0.3364'}                                         
{'loss': '0.7353', 'grad_norm': '0.8221', 'learning_rate': '0.0001358', 'epoch': '0.3387'}                                         
{'loss': '0.6323', 'grad_norm': '0.7078', 'learning_rate': '0.0001354', 'epoch': '0.341'}                                          
{'loss': '0.7291', 'grad_norm': '0.6076', 'learning_rate': '0.0001349', 'epoch': '0.3433'}                                         
{'loss': '0.7119', 'grad_norm': '0.832', 'learning_rate': '0.0001344', 'epoch': '0.3456'}                                          
{'loss': '0.8468', 'grad_norm': '0.7864', 'learning_rate': '0.000134', 'epoch': '0.3479'}                                          
{'loss': '0.7502', 'grad_norm': '0.6693', 'learning_rate': '0.0001335', 'epoch': '0.3502'}                                         
{'loss': '0.8146', 'grad_norm': '0.7551', 'learning_rate': '0.000133', 'epoch': '0.3525'}                                          
{'loss': '0.7089', 'grad_norm': '1.174', 'learning_rate': '0.0001325', 'epoch': '0.3548'}                                          
{'loss': '0.744', 'grad_norm': '0.7283', 'learning_rate': '0.0001321', 'epoch': '0.3571'}                                          
{'loss': '0.6625', 'grad_norm': '0.6605', 'learning_rate': '0.0001316', 'epoch': '0.3594'}                                         
{'loss': '0.7577', 'grad_norm': '0.7157', 'learning_rate': '0.0001311', 'epoch': '0.3618'}                                         
{'loss': '0.7565', 'grad_norm': '0.6369', 'learning_rate': '0.0001307', 'epoch': '0.3641'}                                         
{'loss': '0.7232', 'grad_norm': '0.7473', 'learning_rate': '0.0001302', 'epoch': '0.3664'}                                         
{'loss': '0.6529', 'grad_norm': '0.8033', 'learning_rate': '0.0001297', 'epoch': '0.3687'}                                         
{'loss': '0.6751', 'grad_norm': '0.5666', 'learning_rate': '0.0001292', 'epoch': '0.371'}                                          
{'loss': '0.7196', 'grad_norm': '0.6843', 'learning_rate': '0.0001288', 'epoch': '0.3733'}                                         
{'loss': '0.7188', 'grad_norm': '0.5663', 'learning_rate': '0.0001283', 'epoch': '0.3756'}                                         
{'loss': '0.6426', 'grad_norm': '0.6938', 'learning_rate': '0.0001278', 'epoch': '0.3779'}                                         
{'loss': '0.8217', 'grad_norm': '0.828', 'learning_rate': '0.0001274', 'epoch': '0.3802'}                                          
{'loss': '0.679', 'grad_norm': '0.6295', 'learning_rate': '0.0001269', 'epoch': '0.3825'}                                          
{'loss': '0.652', 'grad_norm': '0.622', 'learning_rate': '0.0001264', 'epoch': '0.3848'}                                           
{'loss': '0.8229', 'grad_norm': '0.6351', 'learning_rate': '0.0001259', 'epoch': '0.3871'}                                         
{'loss': '0.8084', 'grad_norm': '0.623', 'learning_rate': '0.0001255', 'epoch': '0.3894'}                                          
{'loss': '0.6852', 'grad_norm': '0.617', 'learning_rate': '0.000125', 'epoch': '0.3917'}                                           
{'loss': '0.8136', 'grad_norm': '0.6617', 'learning_rate': '0.0001245', 'epoch': '0.394'}                                          
{'loss': '0.792', 'grad_norm': '0.6133', 'learning_rate': '0.0001241', 'epoch': '0.3963'}                                          
{'loss': '0.767', 'grad_norm': '0.6618', 'learning_rate': '0.0001236', 'epoch': '0.3986'}                                          
{'loss': '0.6261', 'grad_norm': '1.066', 'learning_rate': '0.0001231', 'epoch': '0.4009'}                                          
{'loss': '0.691', 'grad_norm': '0.6826', 'learning_rate': '0.0001226', 'epoch': '0.4032'}                                          
{'loss': '0.7585', 'grad_norm': '0.6991', 'learning_rate': '0.0001222', 'epoch': '0.4055'}                                         
{'loss': '0.6425', 'grad_norm': '0.7169', 'learning_rate': '0.0001217', 'epoch': '0.4078'}                                         
{'loss': '0.8036', 'grad_norm': '1.386', 'learning_rate': '0.0001212', 'epoch': '0.4101'}                                          
{'loss': '0.707', 'grad_norm': '0.785', 'learning_rate': '0.0001208', 'epoch': '0.4124'}                                           
{'loss': '0.7674', 'grad_norm': '0.7232', 'learning_rate': '0.0001203', 'epoch': '0.4147'}                                         
{'loss': '0.6521', 'grad_norm': '0.7017', 'learning_rate': '0.0001198', 'epoch': '0.4171'}                                         
{'loss': '0.7318', 'grad_norm': '0.653', 'learning_rate': '0.0001193', 'epoch': '0.4194'}                                          
{'loss': '0.7062', 'grad_norm': '0.6925', 'learning_rate': '0.0001189', 'epoch': '0.4217'}                                         
{'loss': '0.6661', 'grad_norm': '0.9202', 'learning_rate': '0.0001184', 'epoch': '0.424'}                                          
{'loss': '0.7226', 'grad_norm': '0.5722', 'learning_rate': '0.0001179', 'epoch': '0.4263'}                                         
{'loss': '0.6641', 'grad_norm': '0.6503', 'learning_rate': '0.0001175', 'epoch': '0.4286'}                                         
{'loss': '0.7591', 'grad_norm': '0.7961', 'learning_rate': '0.000117', 'epoch': '0.4309'}                                          
{'loss': '0.6511', 'grad_norm': '0.6442', 'learning_rate': '0.0001165', 'epoch': '0.4332'}                                         
{'loss': '0.6513', 'grad_norm': '0.6748', 'learning_rate': '0.000116', 'epoch': '0.4355'}                                          
{'loss': '0.6367', 'grad_norm': '0.7333', 'learning_rate': '0.0001156', 'epoch': '0.4378'}                                         
{'loss': '0.6795', 'grad_norm': '0.7909', 'learning_rate': '0.0001151', 'epoch': '0.4401'}                                         
{'loss': '0.6215', 'grad_norm': '0.8097', 'learning_rate': '0.0001146', 'epoch': '0.4424'}                                         
{'loss': '0.7073', 'grad_norm': '0.7307', 'learning_rate': '0.0001142', 'epoch': '0.4447'}                                         
{'loss': '0.6737', 'grad_norm': '0.7868', 'learning_rate': '0.0001137', 'epoch': '0.447'}                                          
{'loss': '0.7272', 'grad_norm': '0.793', 'learning_rate': '0.0001132', 'epoch': '0.4493'}                                          
{'loss': '0.9008', 'grad_norm': '0.6936', 'learning_rate': '0.0001127', 'epoch': '0.4516'}                                         
{'loss': '0.8439', 'grad_norm': '0.8113', 'learning_rate': '0.0001123', 'epoch': '0.4539'}                                         
{'loss': '0.6559', 'grad_norm': '1.052', 'learning_rate': '0.0001118', 'epoch': '0.4562'}                                          
{'loss': '0.6562', 'grad_norm': '0.692', 'learning_rate': '0.0001113', 'epoch': '0.4585'}                                          
{'loss': '0.5864', 'grad_norm': '0.7826', 'learning_rate': '0.0001108', 'epoch': '0.4608'}                                         
{'loss': '0.6933', 'grad_norm': '0.7045', 'learning_rate': '0.0001104', 'epoch': '0.4631'}                                         
{'loss': '0.8787', 'grad_norm': '0.6587', 'learning_rate': '0.0001099', 'epoch': '0.4654'}                                         
{'loss': '0.6858', 'grad_norm': '0.7311', 'learning_rate': '0.0001094', 'epoch': '0.4677'}                                         
{'loss': '0.7952', 'grad_norm': '0.6425', 'learning_rate': '0.000109', 'epoch': '0.47'}                                            
{'loss': '0.5821', 'grad_norm': '0.7321', 'learning_rate': '0.0001085', 'epoch': '0.4724'}                                         
{'loss': '0.6084', 'grad_norm': '0.6681', 'learning_rate': '0.000108', 'epoch': '0.4747'}                                          
{'loss': '0.6926', 'grad_norm': '0.7361', 'learning_rate': '0.0001075', 'epoch': '0.477'}                                          
{'loss': '0.769', 'grad_norm': '0.7784', 'learning_rate': '0.0001071', 'epoch': '0.4793'}                                          
{'loss': '0.6193', 'grad_norm': '0.7239', 'learning_rate': '0.0001066', 'epoch': '0.4816'}                                         
{'loss': '0.721', 'grad_norm': '0.5652', 'learning_rate': '0.0001061', 'epoch': '0.4839'}                                          
{'loss': '0.6875', 'grad_norm': '0.5473', 'learning_rate': '0.0001057', 'epoch': '0.4862'}                                         
{'loss': '0.6461', 'grad_norm': '0.7835', 'learning_rate': '0.0001052', 'epoch': '0.4885'}                                         
{'loss': '0.732', 'grad_norm': '0.6096', 'learning_rate': '0.0001047', 'epoch': '0.4908'}                                          
{'loss': '0.6869', 'grad_norm': '0.6146', 'learning_rate': '0.0001042', 'epoch': '0.4931'}                                         
{'loss': '0.8226', 'grad_norm': '0.6885', 'learning_rate': '0.0001038', 'epoch': '0.4954'}                                         
{'loss': '0.6765', 'grad_norm': '0.6845', 'learning_rate': '0.0001033', 'epoch': '0.4977'}                                         
{'loss': '0.6878', 'grad_norm': '0.8312', 'learning_rate': '0.0001028', 'epoch': '0.5'}                                            
{'loss': '0.7242', 'grad_norm': '0.7341', 'learning_rate': '0.0001024', 'epoch': '0.5023'}                                         
{'loss': '0.7184', 'grad_norm': '0.6222', 'learning_rate': '0.0001019', 'epoch': '0.5046'}                                         
{'loss': '0.7643', 'grad_norm': '0.7454', 'learning_rate': '0.0001014', 'epoch': '0.5069'}                                         
{'loss': '0.7284', 'grad_norm': '0.6249', 'learning_rate': '0.0001009', 'epoch': '0.5092'}                                         
{'loss': '0.599', 'grad_norm': '0.7636', 'learning_rate': '0.0001005', 'epoch': '0.5115'}                                          
{'loss': '0.6944', 'grad_norm': '0.7066', 'learning_rate': '0.0001', 'epoch': '0.5138'}                                            
{'loss': '0.5576', 'grad_norm': '0.7851', 'learning_rate': '9.953e-05', 'epoch': '0.5161'}                                         
{'loss': '0.6246', 'grad_norm': '0.65', 'learning_rate': '9.906e-05', 'epoch': '0.5184'}                                           
{'loss': '0.7547', 'grad_norm': '0.6075', 'learning_rate': '9.858e-05', 'epoch': '0.5207'}                                         
{'loss': '0.7326', 'grad_norm': '0.5822', 'learning_rate': '9.811e-05', 'epoch': '0.523'}                                          
{'loss': '0.6771', 'grad_norm': '0.6504', 'learning_rate': '9.764e-05', 'epoch': '0.5253'}                                         
{'loss': '0.7189', 'grad_norm': '0.739', 'learning_rate': '9.717e-05', 'epoch': '0.5276'}                                          
{'loss': '0.6214', 'grad_norm': '0.6615', 'learning_rate': '9.67e-05', 'epoch': '0.53'}                                            
{'loss': '0.6544', 'grad_norm': '1.077', 'learning_rate': '9.623e-05', 'epoch': '0.5323'}                                          
{'loss': '0.8527', 'grad_norm': '3.823', 'learning_rate': '9.575e-05', 'epoch': '0.5346'}                                          
{'loss': '0.6811', 'grad_norm': '0.7891', 'learning_rate': '9.528e-05', 'epoch': '0.5369'}                                         
{'loss': '0.7011', 'grad_norm': '0.6397', 'learning_rate': '9.481e-05', 'epoch': '0.5392'}                                         
{'loss': '0.809', 'grad_norm': '0.6586', 'learning_rate': '9.434e-05', 'epoch': '0.5415'}                                          
{'loss': '0.6201', 'grad_norm': '0.6831', 'learning_rate': '9.387e-05', 'epoch': '0.5438'}                                         
{'loss': '0.703', 'grad_norm': '0.6679', 'learning_rate': '9.34e-05', 'epoch': '0.5461'}                                           
{'loss': '0.8684', 'grad_norm': '0.6877', 'learning_rate': '9.292e-05', 'epoch': '0.5484'}                                         
{'loss': '0.5709', 'grad_norm': '0.6925', 'learning_rate': '9.245e-05', 'epoch': '0.5507'}                                         
{'loss': '0.7519', 'grad_norm': '0.7641', 'learning_rate': '9.198e-05', 'epoch': '0.553'}                                          
{'loss': '0.632', 'grad_norm': '0.6665', 'learning_rate': '9.151e-05', 'epoch': '0.5553'}                                          
{'loss': '0.7295', 'grad_norm': '0.8433', 'learning_rate': '9.104e-05', 'epoch': '0.5576'}                                         
{'loss': '0.6557', 'grad_norm': '0.7089', 'learning_rate': '9.057e-05', 'epoch': '0.5599'}                                         
{'loss': '0.5308', 'grad_norm': '0.7193', 'learning_rate': '9.009e-05', 'epoch': '0.5622'}                                         
{'loss': '0.6856', 'grad_norm': '0.7277', 'learning_rate': '8.962e-05', 'epoch': '0.5645'}                                         
{'loss': '0.6976', 'grad_norm': '0.7926', 'learning_rate': '8.915e-05', 'epoch': '0.5668'}                                         
{'loss': '0.5538', 'grad_norm': '0.6679', 'learning_rate': '8.868e-05', 'epoch': '0.5691'}                                         
{'loss': '0.7617', 'grad_norm': '0.5591', 'learning_rate': '8.821e-05', 'epoch': '0.5714'}                                         
{'loss': '0.5602', 'grad_norm': '0.7026', 'learning_rate': '8.774e-05', 'epoch': '0.5737'}                                         
{'loss': '0.7675', 'grad_norm': '0.9408', 'learning_rate': '8.726e-05', 'epoch': '0.576'}                                          
{'loss': '0.607', 'grad_norm': '0.7887', 'learning_rate': '8.679e-05', 'epoch': '0.5783'}                                          
{'loss': '0.7002', 'grad_norm': '0.6858', 'learning_rate': '8.632e-05', 'epoch': '0.5806'}                                         
{'loss': '0.7368', 'grad_norm': '0.8483', 'learning_rate': '8.585e-05', 'epoch': '0.5829'}                                         
{'loss': '0.6901', 'grad_norm': '0.6141', 'learning_rate': '8.538e-05', 'epoch': '0.5853'}                                         
{'loss': '0.6917', 'grad_norm': '0.7585', 'learning_rate': '8.491e-05', 'epoch': '0.5876'}                                         
{'loss': '0.6417', 'grad_norm': '0.7734', 'learning_rate': '8.443e-05', 'epoch': '0.5899'}                                         
{'loss': '0.605', 'grad_norm': '0.7792', 'learning_rate': '8.396e-05', 'epoch': '0.5922'}                                          
{'loss': '0.7263', 'grad_norm': '0.7753', 'learning_rate': '8.349e-05', 'epoch': '0.5945'}                                         
{'loss': '0.6926', 'grad_norm': '0.8041', 'learning_rate': '8.302e-05', 'epoch': '0.5968'}                                         
{'loss': '0.6201', 'grad_norm': '0.718', 'learning_rate': '8.255e-05', 'epoch': '0.5991'}                                          
{'loss': '0.6167', 'grad_norm': '0.7869', 'learning_rate': '8.208e-05', 'epoch': '0.6014'}                                         
{'loss': '0.7094', 'grad_norm': '0.5089', 'learning_rate': '8.16e-05', 'epoch': '0.6037'}                                          
{'loss': '0.7396', 'grad_norm': '0.6099', 'learning_rate': '8.113e-05', 'epoch': '0.606'}                                          
{'loss': '0.7937', 'grad_norm': '0.8118', 'learning_rate': '8.066e-05', 'epoch': '0.6083'}                                         
{'loss': '0.6828', 'grad_norm': '0.5821', 'learning_rate': '8.019e-05', 'epoch': '0.6106'}                                         
{'loss': '0.6929', 'grad_norm': '0.7661', 'learning_rate': '7.972e-05', 'epoch': '0.6129'}                                         
{'loss': '0.59', 'grad_norm': '0.7415', 'learning_rate': '7.925e-05', 'epoch': '0.6152'}                                           
{'loss': '0.7025', 'grad_norm': '0.6986', 'learning_rate': '7.877e-05', 'epoch': '0.6175'}                                         
{'loss': '0.6089', 'grad_norm': '0.7253', 'learning_rate': '7.83e-05', 'epoch': '0.6198'}                                          
{'loss': '0.645', 'grad_norm': '0.7664', 'learning_rate': '7.783e-05', 'epoch': '0.6221'}                                          
{'loss': '0.8001', 'grad_norm': '0.6798', 'learning_rate': '7.736e-05', 'epoch': '0.6244'}                                         
{'loss': '0.6112', 'grad_norm': '0.6818', 'learning_rate': '7.689e-05', 'epoch': '0.6267'}                                         
{'loss': '0.6234', 'grad_norm': '0.7829', 'learning_rate': '7.642e-05', 'epoch': '0.629'}                                          
{'loss': '0.6791', 'grad_norm': '0.9646', 'learning_rate': '7.594e-05', 'epoch': '0.6313'}                                         
{'loss': '0.6999', 'grad_norm': '0.7682', 'learning_rate': '7.547e-05', 'epoch': '0.6336'}                                         
{'loss': '0.9651', 'grad_norm': '0.8329', 'learning_rate': '7.5e-05', 'epoch': '0.6359'}                                           
{'loss': '0.6345', 'grad_norm': '0.7451', 'learning_rate': '7.453e-05', 'epoch': '0.6382'}                                         
{'loss': '0.744', 'grad_norm': '0.7939', 'learning_rate': '7.406e-05', 'epoch': '0.6406'}                                          
{'loss': '0.6384', 'grad_norm': '0.8346', 'learning_rate': '7.358e-05', 'epoch': '0.6429'}                                         
{'loss': '0.6932', 'grad_norm': '0.8997', 'learning_rate': '7.311e-05', 'epoch': '0.6452'}                                         
{'loss': '0.664', 'grad_norm': '0.754', 'learning_rate': '7.264e-05', 'epoch': '0.6475'}                                           
{'loss': '0.7317', 'grad_norm': '0.6258', 'learning_rate': '7.217e-05', 'epoch': '0.6498'}                                         
{'loss': '0.6652', 'grad_norm': '0.6909', 'learning_rate': '7.17e-05', 'epoch': '0.6521'}                                          
{'loss': '0.7684', 'grad_norm': '0.8586', 'learning_rate': '7.123e-05', 'epoch': '0.6544'}                                         
{'loss': '0.6168', 'grad_norm': '0.6556', 'learning_rate': '7.075e-05', 'epoch': '0.6567'}                                         
{'loss': '0.7547', 'grad_norm': '2.138', 'learning_rate': '7.028e-05', 'epoch': '0.659'}                                           
{'loss': '0.6589', 'grad_norm': '0.6164', 'learning_rate': '6.981e-05', 'epoch': '0.6613'}                                         
{'loss': '0.8303', 'grad_norm': '0.7958', 'learning_rate': '6.934e-05', 'epoch': '0.6636'}                                         
{'loss': '0.6346', 'grad_norm': '0.6643', 'learning_rate': '6.887e-05', 'epoch': '0.6659'}                                         
{'loss': '0.7927', 'grad_norm': '0.7637', 'learning_rate': '6.84e-05', 'epoch': '0.6682'}                                          
{'loss': '0.5396', 'grad_norm': '0.7794', 'learning_rate': '6.792e-05', 'epoch': '0.6705'}                                         
{'loss': '0.7402', 'grad_norm': '0.9226', 'learning_rate': '6.745e-05', 'epoch': '0.6728'}                                         
{'loss': '0.5718', 'grad_norm': '0.716', 'learning_rate': '6.698e-05', 'epoch': '0.6751'}                                          
{'loss': '0.7497', 'grad_norm': '0.78', 'learning_rate': '6.651e-05', 'epoch': '0.6774'}                                           
{'loss': '0.7002', 'grad_norm': '0.8666', 'learning_rate': '6.604e-05', 'epoch': '0.6797'}                                         
{'loss': '0.682', 'grad_norm': '0.6172', 'learning_rate': '6.557e-05', 'epoch': '0.682'}                                           
{'loss': '0.7231', 'grad_norm': '0.755', 'learning_rate': '6.509e-05', 'epoch': '0.6843'}                                          
{'loss': '0.7529', 'grad_norm': '0.8031', 'learning_rate': '6.462e-05', 'epoch': '0.6866'}                                         
{'loss': '0.6923', 'grad_norm': '1.036', 'learning_rate': '6.415e-05', 'epoch': '0.6889'}                                          
{'loss': '0.6313', 'grad_norm': '0.6406', 'learning_rate': '6.368e-05', 'epoch': '0.6912'}                                         
{'loss': '0.5629', 'grad_norm': '0.8021', 'learning_rate': '6.321e-05', 'epoch': '0.6935'}                                         
{'loss': '0.5742', 'grad_norm': '0.778', 'learning_rate': '6.274e-05', 'epoch': '0.6959'}                                          
{'loss': '0.6129', 'grad_norm': '0.7146', 'learning_rate': '6.226e-05', 'epoch': '0.6982'}                                         
{'loss': '0.6361', 'grad_norm': '0.6199', 'learning_rate': '6.179e-05', 'epoch': '0.7005'}                                         
{'loss': '0.697', 'grad_norm': '0.7804', 'learning_rate': '6.132e-05', 'epoch': '0.7028'}                                          
{'loss': '0.7702', 'grad_norm': '0.9301', 'learning_rate': '6.085e-05', 'epoch': '0.7051'}                                         
{'loss': '0.7402', 'grad_norm': '0.6158', 'learning_rate': '6.038e-05', 'epoch': '0.7074'}                                         
{'loss': '0.6888', 'grad_norm': '0.8029', 'learning_rate': '5.991e-05', 'epoch': '0.7097'}                                         
{'loss': '0.6505', 'grad_norm': '0.7134', 'learning_rate': '5.943e-05', 'epoch': '0.712'}                                          
{'loss': '0.757', 'grad_norm': '0.7019', 'learning_rate': '5.896e-05', 'epoch': '0.7143'}                                          
{'loss': '0.7168', 'grad_norm': '0.6269', 'learning_rate': '5.849e-05', 'epoch': '0.7166'}                                         
{'loss': '0.7137', 'grad_norm': '0.6716', 'learning_rate': '5.802e-05', 'epoch': '0.7189'}                                         
{'loss': '0.7503', 'grad_norm': '0.602', 'learning_rate': '5.755e-05', 'epoch': '0.7212'}                                          
{'loss': '0.695', 'grad_norm': '0.7795', 'learning_rate': '5.708e-05', 'epoch': '0.7235'}                                          
{'loss': '0.7953', 'grad_norm': '0.8304', 'learning_rate': '5.66e-05', 'epoch': '0.7258'}                                          
{'loss': '0.6439', 'grad_norm': '0.787', 'learning_rate': '5.613e-05', 'epoch': '0.7281'}                                          
{'loss': '0.6194', 'grad_norm': '0.7845', 'learning_rate': '5.566e-05', 'epoch': '0.7304'}                                         
{'loss': '0.6059', 'grad_norm': '0.7715', 'learning_rate': '5.519e-05', 'epoch': '0.7327'}                                         
{'loss': '0.6572', 'grad_norm': '0.6325', 'learning_rate': '5.472e-05', 'epoch': '0.735'}                                          
{'loss': '0.7355', 'grad_norm': '0.6121', 'learning_rate': '5.425e-05', 'epoch': '0.7373'}                                         
{'loss': '0.6701', 'grad_norm': '0.7244', 'learning_rate': '5.377e-05', 'epoch': '0.7396'}                                         
{'loss': '0.6104', 'grad_norm': '0.6672', 'learning_rate': '5.33e-05', 'epoch': '0.7419'}                                          
{'loss': '0.7776', 'grad_norm': '0.6407', 'learning_rate': '5.283e-05', 'epoch': '0.7442'}                                         
{'loss': '0.7708', 'grad_norm': '0.6343', 'learning_rate': '5.236e-05', 'epoch': '0.7465'}                                         
{'loss': '0.6555', 'grad_norm': '0.6734', 'learning_rate': '5.189e-05', 'epoch': '0.7488'}                                         
{'loss': '0.6743', 'grad_norm': '0.7834', 'learning_rate': '5.142e-05', 'epoch': '0.7512'}                                         
{'loss': '0.7079', 'grad_norm': '0.9508', 'learning_rate': '5.094e-05', 'epoch': '0.7535'}                                         
{'loss': '0.7466', 'grad_norm': '0.7823', 'learning_rate': '5.047e-05', 'epoch': '0.7558'}                                         
{'loss': '0.6686', 'grad_norm': '0.7012', 'learning_rate': '5e-05', 'epoch': '0.7581'}                                             
{'loss': '0.7185', 'grad_norm': '0.6235', 'learning_rate': '4.953e-05', 'epoch': '0.7604'}                                         
{'loss': '0.5861', 'grad_norm': '0.8139', 'learning_rate': '4.906e-05', 'epoch': '0.7627'}                                         
{'loss': '0.679', 'grad_norm': '0.7595', 'learning_rate': '4.858e-05', 'epoch': '0.765'}                                           
{'loss': '0.7146', 'grad_norm': '0.7735', 'learning_rate': '4.811e-05', 'epoch': '0.7673'}                                         
{'loss': '0.6891', 'grad_norm': '0.6664', 'learning_rate': '4.764e-05', 'epoch': '0.7696'}                                         
{'loss': '0.6547', 'grad_norm': '0.6523', 'learning_rate': '4.717e-05', 'epoch': '0.7719'}                                         
{'loss': '0.5791', 'grad_norm': '0.814', 'learning_rate': '4.67e-05', 'epoch': '0.7742'}                                           
{'loss': '0.6666', 'grad_norm': '0.6031', 'learning_rate': '4.623e-05', 'epoch': '0.7765'}                                         
{'loss': '0.5546', 'grad_norm': '0.7153', 'learning_rate': '4.575e-05', 'epoch': '0.7788'}                                         
{'loss': '0.6376', 'grad_norm': '0.7127', 'learning_rate': '4.528e-05', 'epoch': '0.7811'}                                         
{'loss': '0.6256', 'grad_norm': '0.7281', 'learning_rate': '4.481e-05', 'epoch': '0.7834'}                                         
{'loss': '0.6856', 'grad_norm': '0.5837', 'learning_rate': '4.434e-05', 'epoch': '0.7857'}                                         
{'loss': '0.668', 'grad_norm': '0.8757', 'learning_rate': '4.387e-05', 'epoch': '0.788'}                                           
{'loss': '0.6784', 'grad_norm': '0.6944', 'learning_rate': '4.34e-05', 'epoch': '0.7903'}                                          
{'loss': '0.7091', 'grad_norm': '0.6807', 'learning_rate': '4.292e-05', 'epoch': '0.7926'}                                         
{'loss': '0.6272', 'grad_norm': '0.7341', 'learning_rate': '4.245e-05', 'epoch': '0.7949'}                                         
{'loss': '0.5943', 'grad_norm': '0.667', 'learning_rate': '4.198e-05', 'epoch': '0.7972'}                                          
{'loss': '0.7094', 'grad_norm': '0.5606', 'learning_rate': '4.151e-05', 'epoch': '0.7995'}                                         
{'loss': '0.7076', 'grad_norm': '0.6964', 'learning_rate': '4.104e-05', 'epoch': '0.8018'}                                         
{'loss': '0.7084', 'grad_norm': '2.244', 'learning_rate': '4.057e-05', 'epoch': '0.8041'}                                          
{'loss': '0.5905', 'grad_norm': '0.7718', 'learning_rate': '4.009e-05', 'epoch': '0.8065'}                                         
{'loss': '0.6067', 'grad_norm': '2.471', 'learning_rate': '3.962e-05', 'epoch': '0.8088'}                                          
{'loss': '0.6087', 'grad_norm': '0.7983', 'learning_rate': '3.915e-05', 'epoch': '0.8111'}                                         
{'loss': '0.5813', 'grad_norm': '0.828', 'learning_rate': '3.868e-05', 'epoch': '0.8134'}                                          
{'loss': '0.6389', 'grad_norm': '0.651', 'learning_rate': '3.821e-05', 'epoch': '0.8157'}                                          
{'loss': '0.6189', 'grad_norm': '0.564', 'learning_rate': '3.774e-05', 'epoch': '0.818'}                                           
{'loss': '0.5612', 'grad_norm': '0.8186', 'learning_rate': '3.726e-05', 'epoch': '0.8203'}                                         
{'loss': '0.6114', 'grad_norm': '0.7783', 'learning_rate': '3.679e-05', 'epoch': '0.8226'}                                         
{'loss': '0.6141', 'grad_norm': '0.5669', 'learning_rate': '3.632e-05', 'epoch': '0.8249'}                                         
{'loss': '0.7132', 'grad_norm': '0.6893', 'learning_rate': '3.585e-05', 'epoch': '0.8272'}                                         
{'loss': '0.7852', 'grad_norm': '0.7602', 'learning_rate': '3.538e-05', 'epoch': '0.8295'}                                         
{'loss': '0.6061', 'grad_norm': '0.7809', 'learning_rate': '3.491e-05', 'epoch': '0.8318'}                                         
{'loss': '0.7177', 'grad_norm': '0.5799', 'learning_rate': '3.443e-05', 'epoch': '0.8341'}                                         
{'loss': '0.6242', 'grad_norm': '0.8146', 'learning_rate': '3.396e-05', 'epoch': '0.8364'}                                         
{'loss': '0.5499', 'grad_norm': '0.7695', 'learning_rate': '3.349e-05', 'epoch': '0.8387'}                                         
{'loss': '0.5043', 'grad_norm': '0.9844', 'learning_rate': '3.302e-05', 'epoch': '0.841'}                                          
{'loss': '0.5589', 'grad_norm': '0.7948', 'learning_rate': '3.255e-05', 'epoch': '0.8433'}                                         
{'loss': '0.5735', 'grad_norm': '0.767', 'learning_rate': '3.208e-05', 'epoch': '0.8456'}                                          
{'loss': '0.5694', 'grad_norm': '0.7302', 'learning_rate': '3.16e-05', 'epoch': '0.8479'}                                          
{'loss': '0.816', 'grad_norm': '0.9441', 'learning_rate': '3.113e-05', 'epoch': '0.8502'}                                          
{'loss': '0.6635', 'grad_norm': '0.8226', 'learning_rate': '3.066e-05', 'epoch': '0.8525'}                                         
{'loss': '0.6808', 'grad_norm': '0.6174', 'learning_rate': '3.019e-05', 'epoch': '0.8548'}                                         
{'loss': '0.6569', 'grad_norm': '0.8516', 'learning_rate': '2.972e-05', 'epoch': '0.8571'}                                         
{'loss': '0.6142', 'grad_norm': '0.8613', 'learning_rate': '2.925e-05', 'epoch': '0.8594'}                                         
{'loss': '0.6065', 'grad_norm': '0.7659', 'learning_rate': '2.877e-05', 'epoch': '0.8618'}                                         
{'loss': '0.7156', 'grad_norm': '0.8187', 'learning_rate': '2.83e-05', 'epoch': '0.8641'}                                          
{'loss': '0.6545', 'grad_norm': '0.6516', 'learning_rate': '2.783e-05', 'epoch': '0.8664'}                                         
{'loss': '0.6559', 'grad_norm': '0.8116', 'learning_rate': '2.736e-05', 'epoch': '0.8687'}                                         
{'loss': '0.6905', 'grad_norm': '0.7929', 'learning_rate': '2.689e-05', 'epoch': '0.871'}                                          
{'loss': '0.6429', 'grad_norm': '0.7965', 'learning_rate': '2.642e-05', 'epoch': '0.8733'}                                         
{'loss': '0.7024', 'grad_norm': '0.7021', 'learning_rate': '2.594e-05', 'epoch': '0.8756'}                                         
{'loss': '0.62', 'grad_norm': '0.6393', 'learning_rate': '2.547e-05', 'epoch': '0.8779'}                                           
{'loss': '0.6851', 'grad_norm': '0.5572', 'learning_rate': '2.5e-05', 'epoch': '0.8802'}                                           
{'loss': '0.6225', 'grad_norm': '0.7876', 'learning_rate': '2.453e-05', 'epoch': '0.8825'}                                         
{'loss': '0.7011', 'grad_norm': '0.7235', 'learning_rate': '2.406e-05', 'epoch': '0.8848'}                                         
{'loss': '0.7344', 'grad_norm': '0.7355', 'learning_rate': '2.358e-05', 'epoch': '0.8871'}                                         
{'loss': '0.7058', 'grad_norm': '4.238', 'learning_rate': '2.311e-05', 'epoch': '0.8894'}                                          
{'loss': '0.5529', 'grad_norm': '0.7393', 'learning_rate': '2.264e-05', 'epoch': '0.8917'}                                         
{'loss': '0.6312', 'grad_norm': '0.773', 'learning_rate': '2.217e-05', 'epoch': '0.894'}                                           
{'loss': '0.7087', 'grad_norm': '0.7699', 'learning_rate': '2.17e-05', 'epoch': '0.8963'}                                          
{'loss': '0.6033', 'grad_norm': '0.7031', 'learning_rate': '2.123e-05', 'epoch': '0.8986'}                                         
{'loss': '0.665', 'grad_norm': '0.901', 'learning_rate': '2.075e-05', 'epoch': '0.9009'}                                           
{'loss': '0.5973', 'grad_norm': '0.7955', 'learning_rate': '2.028e-05', 'epoch': '0.9032'}                                         
{'loss': '0.669', 'grad_norm': '5.277', 'learning_rate': '1.981e-05', 'epoch': '0.9055'}                                           
{'loss': '0.6031', 'grad_norm': '0.7428', 'learning_rate': '1.934e-05', 'epoch': '0.9078'}                                         
{'loss': '0.5883', 'grad_norm': '0.8059', 'learning_rate': '1.887e-05', 'epoch': '0.9101'}                                         
{'loss': '0.6266', 'grad_norm': '1.003', 'learning_rate': '1.84e-05', 'epoch': '0.9124'}                                           
{'loss': '0.6649', 'grad_norm': '0.633', 'learning_rate': '1.792e-05', 'epoch': '0.9147'}                                          
{'loss': '0.6763', 'grad_norm': '0.9387', 'learning_rate': '1.745e-05', 'epoch': '0.9171'}                                         
{'loss': '0.5819', 'grad_norm': '0.685', 'learning_rate': '1.698e-05', 'epoch': '0.9194'}                                          
{'loss': '0.6167', 'grad_norm': '0.7491', 'learning_rate': '1.651e-05', 'epoch': '0.9217'}                                         
{'loss': '0.6095', 'grad_norm': '0.7192', 'learning_rate': '1.604e-05', 'epoch': '0.924'}                                          
{'loss': '0.6267', 'grad_norm': '0.8756', 'learning_rate': '1.557e-05', 'epoch': '0.9263'}                                         
{'loss': '0.6185', 'grad_norm': '0.65', 'learning_rate': '1.509e-05', 'epoch': '0.9286'}                                           
{'loss': '0.6397', 'grad_norm': '0.8801', 'learning_rate': '1.462e-05', 'epoch': '0.9309'}                                         
{'loss': '0.6977', 'grad_norm': '0.9298', 'learning_rate': '1.415e-05', 'epoch': '0.9332'}                                         
{'loss': '0.6846', 'grad_norm': '0.5926', 'learning_rate': '1.368e-05', 'epoch': '0.9355'}                                         
{'loss': '0.6673', 'grad_norm': '0.6751', 'learning_rate': '1.321e-05', 'epoch': '0.9378'}                                         
{'loss': '0.6824', 'grad_norm': '0.659', 'learning_rate': '1.274e-05', 'epoch': '0.9401'}                                          
{'loss': '0.6393', 'grad_norm': '1.433', 'learning_rate': '1.226e-05', 'epoch': '0.9424'}                                          
{'loss': '0.699', 'grad_norm': '0.6385', 'learning_rate': '1.179e-05', 'epoch': '0.9447'}                                          
{'loss': '0.607', 'grad_norm': '0.7569', 'learning_rate': '1.132e-05', 'epoch': '0.947'}                                           
{'loss': '0.6425', 'grad_norm': '0.5841', 'learning_rate': '1.085e-05', 'epoch': '0.9493'}                                         
{'loss': '0.6065', 'grad_norm': '0.72', 'learning_rate': '1.038e-05', 'epoch': '0.9516'}                                           
{'loss': '0.679', 'grad_norm': '0.8723', 'learning_rate': '9.906e-06', 'epoch': '0.9539'}                                          
{'loss': '0.6513', 'grad_norm': '0.6482', 'learning_rate': '9.434e-06', 'epoch': '0.9562'}                                         
{'loss': '0.6345', 'grad_norm': '3.27', 'learning_rate': '8.962e-06', 'epoch': '0.9585'}                                           
{'loss': '0.8097', 'grad_norm': '0.6729', 'learning_rate': '8.491e-06', 'epoch': '0.9608'}                                         
{'loss': '0.6993', 'grad_norm': '0.8738', 'learning_rate': '8.019e-06', 'epoch': '0.9631'}                                         
{'loss': '0.736', 'grad_norm': '0.7564', 'learning_rate': '7.547e-06', 'epoch': '0.9654'}                                          
{'loss': '0.562', 'grad_norm': '0.7635', 'learning_rate': '7.075e-06', 'epoch': '0.9677'}                                          
{'loss': '0.6131', 'grad_norm': '0.7943', 'learning_rate': '6.604e-06', 'epoch': '0.97'}                                           
{'loss': '0.6493', 'grad_norm': '0.8371', 'learning_rate': '6.132e-06', 'epoch': '0.9724'}                                         
{'loss': '0.6181', 'grad_norm': '0.7575', 'learning_rate': '5.66e-06', 'epoch': '0.9747'}                                          
{'loss': '0.7093', 'grad_norm': '3.453', 'learning_rate': '5.189e-06', 'epoch': '0.977'}                                           
{'loss': '0.6356', 'grad_norm': '0.7428', 'learning_rate': '4.717e-06', 'epoch': '0.9793'}                                         
{'loss': '0.6366', 'grad_norm': '0.6544', 'learning_rate': '4.245e-06', 'epoch': '0.9816'}                                         
{'loss': '0.6439', 'grad_norm': '0.9207', 'learning_rate': '3.774e-06', 'epoch': '0.9839'}                                         
{'loss': '0.6669', 'grad_norm': '2.832', 'learning_rate': '3.302e-06', 'epoch': '0.9862'}                                          
{'loss': '0.6141', 'grad_norm': '0.7491', 'learning_rate': '2.83e-06', 'epoch': '0.9885'}                                          
{'loss': '0.7003', 'grad_norm': '0.7141', 'learning_rate': '2.358e-06', 'epoch': '0.9908'}                                         
{'loss': '0.6681', 'grad_norm': '0.8635', 'learning_rate': '1.887e-06', 'epoch': '0.9931'}                                         
{'loss': '0.6477', 'grad_norm': '0.7991', 'learning_rate': '1.415e-06', 'epoch': '0.9954'}                                         
{'loss': '0.5517', 'grad_norm': '0.7154', 'learning_rate': '9.434e-07', 'epoch': '0.9977'}                                         
{'loss': '0.7304', 'grad_norm': '0.9191', 'learning_rate': '4.717e-07', 'epoch': '1'}                                              
{'train_runtime': '4414', 'train_samples_per_second': '0.393', 'train_steps_per_second': '0.098', 'train_loss': '0.7804', 'epoch': '1'}
100%|██████████████████████████████████████████████████████████████████████████████████████████| 434/434 [1:13:33<00:00, 10.17s/it]

Training complete!
  Total steps: 434
  Final loss: 0.7804

Saving LoRA adapter to /workspace/output/gcse-tutor-gemma4-26b-moe/lora-adapter...
Saving merged 16-bit model to /workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|█████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 633.01it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files...         | 0/1 [00:00<?, ?it/s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`: 100%|█| 2/2 [00:54<00:00, 27.26s
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`█| 2/2 [00:54<00:00, 22.86s
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|█████████████████████████████████████████████████| 2/2 [00:00<00:00, 135300.13it/s]
Download complete: : 0.00B [00:54, ?B/s]s:   0%|                                                             | 0/2 [00:00<?, ?it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████████████████████████████████| 2/2 [05:57<00:00, 178.86s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-26b-moe/merged-16bit`| 2/2 [05:57<00:00, 149.68s/it]
Exporting GGUF to /workspace/output/gcse-tutor-gemma4-26b-moe/gguf...
Unsloth: Merging model weights to 16-bit format...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|████████████████████████████████████████████████████████████████████████████| 1/1 [00:00<00:00, 1192.92it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files...         | 0/1 [00:00<?, ?it/s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`: 100%|█████| 2/2 [01:12<00:00, 36.34s/it]
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`█████| 2/2 [01:12<00:00, 30.37s/it]
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|██████████████████████████████████████████████████| 2/2 [00:00<00:00, 88301.14it/s]
Download complete: : 0.00B [01:12, ?B/s]s:   0%|                                                             | 0/2 [00:00<?, ?it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████████████████████████████████| 2/2 [05:55<00:00, 177.59s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-26b-moe/gguf`████████| 2/2 [05:55<00:00, 148.71s/it]
Unsloth: Converting to GGUF format...
==((====))==  Unsloth: Conversion from HF to GGUF information
   \\   /|    [0] Installing llama.cpp might take 3 minutes.
O^O/ \_/ \    [1] Converting HF to GGUF bf16 might take 3 minutes.
\        /    [2] Converting GGUF bf16 to ['q4_k_m'] might take 10 minutes each.
 "-____-"     In total, you will have to wait at least 16 minutes.

Unsloth: llama.cpp found in the system. Skipping installation.
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

