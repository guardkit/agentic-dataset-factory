root@15f5227647c4:/workspace# python scripts/train_gemma4.py --epochs 1 --save-steps 200 --lr 2e-4
🦥 Unsloth: Will patch your computer to enable 2x faster free finetuning.
🦥 Unsloth Zoo will now patch everything to make training faster!
usage: train_gemma4.py [-h] [--model-name MODEL_NAME] [--max-seq-length MAX_SEQ_LENGTH] [--no-4bit]
                       [--lora-r LORA_R] [--lora-alpha LORA_ALPHA] [--lr LR]
                       [--batch-size BATCH_SIZE] [--grad-accum GRAD_ACCUM] [--max-steps MAX_STEPS]
                       [--epochs EPOCHS] [--data-path DATA_PATH] [--output-dir OUTPUT_DIR]
                       [--chat-template {gemma-4-thinking,gemma-4}]
                       [--report-to {none,wandb,tensorboard}] [--resume] [--skip-export]
train_gemma4.py: error: unrecognized arguments: --save-steps 200
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# sed -i '/--skip-export/i\    p.add_argument("--save-steps", type=int, default=100)' /workspace/scripts/train_gemma4.py
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# 
root@15f5227647c4:/workspace# python scripts/train_gemma4.py --epochs 1 --save-steps 200 --lr 2e-4
🦥 Unsloth: Will patch your computer to enable 2x faster free finetuning.
🦥 Unsloth Zoo will now patch everything to make training faster!

============================================================
Loading unsloth/gemma-4-31B-it
  QLoRA 4-bit: True
  Max sequence length: 8192
============================================================

==((====))==  Unsloth 2026.4.4: Fast Gemma4 patching. Transformers: 5.5.3.
   \\   /|    NVIDIA GB10. Num GPUs = 1. Max memory: 121.628 GB. Platform: Linux.
O^O/ \_/ \    Torch: 2.10.0a0+b558c986e8.nv25.11. CUDA: 12.1. CUDA Toolkit: 13.0. Triton: 3.5.0
\        /    Bfloat16 = TRUE. FA [Xformers = None. FA2 = True]
 "-____-"     Free license: http://github.com/unslothai/unsloth
Unsloth: Fast downloading is enabled - ignore downloading bars which are red colored!
Loading weights: 100%|█████████████████████████████████████████████| 1188/1188 [05:38<00:00,  3.51it/s]
Chat template: gemma-4-thinking
  First record keys: ['messages', 'metadata']
  First message keys: ['role', 'content']
Loaded 1736 training examples from /workspace/data/train.jsonl
  First example: 3 turns, roles: ['system', 'user', 'assistant']
  First user msg (truncated): You are an expert GCSE English tutor supporting a Year 10 student studying the AQA specification.
Your role is to guide ...
Unsloth: Standardizing formats (num_proc=24): 100%|███████| 1736/1736 [00:01<00:00, 1440.51 examples/s]
Map: 100%|███████████████████████████████████████████████| 1736/1736 [00:00<00:00, 19361.38 examples/s]

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

Unsloth: Tokenizing ["text"] (num_proc=24): 100%|███████████| 1736/1736 [00:51<00:00, 33.93 examples/s]
Map (num_proc=24): 100%|██████████████████████████████████| 1736/1736 [00:01<00:00, 1734.55 examples/s]
Filter (num_proc=24): 100%|███████████████████████████████| 1736/1736 [00:01<00:00, 1677.97 examples/s]
Verifying response-only masking...
  Masked tokens: 223/404 (55.2% masked)

============================================================
Starting training...
  Epochs: 1
  Effective batch size: 4
  Learning rate: 0.0002
  Output: /workspace/output/gcse-tutor-gemma4-31b
============================================================

The tokenizer has new PAD/BOS/EOS tokens that differ from the model config and generation config. The model config and generation config were aligned accordingly, being updated with the tokenizer's values. Updated tokens: {'bos_token_id': 2}.
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 1,736 | Num Epochs = 1 | Total steps = 434
O^O/ \_/ \    Batch size per device = 1 | Gradient accumulation steps = 4
\        /    Data Parallel GPUs = 1 | Total batch size (1 x 4 x 1) = 4
 "-____-"     Trainable parameters = 61,214,720 of 31,334,301,232 (0.20% trained)
  0%|                                                                          | 0/434 [00:00<?, ?it/s]Unsloth: Will smartly offload gradients to save VRAM!
{'loss': '2.449', 'grad_norm': '3.12', 'learning_rate': '0', 'epoch': '0.002304'}                      
{'loss': '2.473', 'grad_norm': '4.122', 'learning_rate': '2e-05', 'epoch': '0.004608'}                 
{'loss': '2.647', 'grad_norm': '1.112', 'learning_rate': '4e-05', 'epoch': '0.006912'}                 
{'loss': '2.574', 'grad_norm': '1.915', 'learning_rate': '6e-05', 'epoch': '0.009217'}                 
{'loss': '2.779', 'grad_norm': '1.553', 'learning_rate': '8e-05', 'epoch': '0.01152'}                  
{'loss': '2.515', 'grad_norm': '1.996', 'learning_rate': '0.0001', 'epoch': '0.01382'}                 
{'loss': '2.431', 'grad_norm': '2.157', 'learning_rate': '0.00012', 'epoch': '0.01613'}                
{'loss': '2.255', 'grad_norm': '6.227', 'learning_rate': '0.00014', 'epoch': '0.01843'}                
{'loss': '1.969', 'grad_norm': '8.068', 'learning_rate': '0.00016', 'epoch': '0.02074'}                
{'loss': '1.574', 'grad_norm': '29.4', 'learning_rate': '0.00018', 'epoch': '0.02304'}                 
{'loss': '1.44', 'grad_norm': '1.817', 'learning_rate': '0.0002', 'epoch': '0.02535'}                  
{'loss': '1.467', 'grad_norm': '2.959', 'learning_rate': '0.0001995', 'epoch': '0.02765'}              
{'loss': '1.502', 'grad_norm': '1.967', 'learning_rate': '0.0001991', 'epoch': '0.02995'}              
{'loss': '1.599', 'grad_norm': '1.249', 'learning_rate': '0.0001986', 'epoch': '0.03226'}              
{'loss': '1.326', 'grad_norm': '1.087', 'learning_rate': '0.0001981', 'epoch': '0.03456'}              
{'loss': '1.376', 'grad_norm': '0.8875', 'learning_rate': '0.0001976', 'epoch': '0.03687'}             
{'loss': '1.355', 'grad_norm': '1.216', 'learning_rate': '0.0001972', 'epoch': '0.03917'}              
{'loss': '1.261', 'grad_norm': '0.9594', 'learning_rate': '0.0001967', 'epoch': '0.04147'}             
{'loss': '1.12', 'grad_norm': '1.002', 'learning_rate': '0.0001962', 'epoch': '0.04378'}               
{'loss': '1.118', 'grad_norm': '0.7657', 'learning_rate': '0.0001958', 'epoch': '0.04608'}             
{'loss': '0.9708', 'grad_norm': '0.7818', 'learning_rate': '0.0001953', 'epoch': '0.04839'}            
{'loss': '1.06', 'grad_norm': '0.5288', 'learning_rate': '0.0001948', 'epoch': '0.05069'}              
{'loss': '0.9388', 'grad_norm': '0.5154', 'learning_rate': '0.0001943', 'epoch': '0.053'}              
{'loss': '1.016', 'grad_norm': '0.7214', 'learning_rate': '0.0001939', 'epoch': '0.0553'}              
{'loss': '1.027', 'grad_norm': '0.5689', 'learning_rate': '0.0001934', 'epoch': '0.0576'}              
{'loss': '0.9288', 'grad_norm': '0.7221', 'learning_rate': '0.0001929', 'epoch': '0.05991'}            
{'loss': '0.7545', 'grad_norm': '0.8645', 'learning_rate': '0.0001925', 'epoch': '0.06221'}            
{'loss': '0.9924', 'grad_norm': '0.6159', 'learning_rate': '0.000192', 'epoch': '0.06452'}             
{'loss': '1.135', 'grad_norm': '0.8511', 'learning_rate': '0.0001915', 'epoch': '0.06682'}             
{'loss': '0.9239', 'grad_norm': '1.088', 'learning_rate': '0.000191', 'epoch': '0.06912'}              
{'loss': '1.007', 'grad_norm': '0.7669', 'learning_rate': '0.0001906', 'epoch': '0.07143'}             
{'loss': '0.9489', 'grad_norm': '0.661', 'learning_rate': '0.0001901', 'epoch': '0.07373'}             
{'loss': '0.8591', 'grad_norm': '2.706', 'learning_rate': '0.0001896', 'epoch': '0.07604'}             
{'loss': '1.125', 'grad_norm': '0.7425', 'learning_rate': '0.0001892', 'epoch': '0.07834'}             
{'loss': '0.849', 'grad_norm': '0.6497', 'learning_rate': '0.0001887', 'epoch': '0.08065'}             
{'loss': '0.8458', 'grad_norm': '0.5717', 'learning_rate': '0.0001882', 'epoch': '0.08295'}            
{'loss': '0.8846', 'grad_norm': '0.5789', 'learning_rate': '0.0001877', 'epoch': '0.08525'}            
{'loss': '0.8114', 'grad_norm': '0.6476', 'learning_rate': '0.0001873', 'epoch': '0.08756'}            
{'loss': '0.6844', 'grad_norm': '0.9369', 'learning_rate': '0.0001868', 'epoch': '0.08986'}            
{'loss': '0.9195', 'grad_norm': '0.6766', 'learning_rate': '0.0001863', 'epoch': '0.09217'}            
{'loss': '0.8873', 'grad_norm': '0.4962', 'learning_rate': '0.0001858', 'epoch': '0.09447'}            
{'loss': '0.7886', 'grad_norm': '1.657', 'learning_rate': '0.0001854', 'epoch': '0.09677'}             
{'loss': '0.8096', 'grad_norm': '0.5933', 'learning_rate': '0.0001849', 'epoch': '0.09908'}            
{'loss': '0.8746', 'grad_norm': '0.5876', 'learning_rate': '0.0001844', 'epoch': '0.1014'}             
{'loss': '0.7985', 'grad_norm': '4.574', 'learning_rate': '0.000184', 'epoch': '0.1037'}               
{'loss': '0.8141', 'grad_norm': '0.6649', 'learning_rate': '0.0001835', 'epoch': '0.106'}              
{'loss': '0.828', 'grad_norm': '0.7022', 'learning_rate': '0.000183', 'epoch': '0.1083'}               
{'loss': '0.7632', 'grad_norm': '7.034', 'learning_rate': '0.0001825', 'epoch': '0.1106'}              
{'loss': '0.9864', 'grad_norm': '1.117', 'learning_rate': '0.0001821', 'epoch': '0.1129'}              
{'loss': '0.8266', 'grad_norm': '7.421', 'learning_rate': '0.0001816', 'epoch': '0.1152'}              
{'loss': '0.7637', 'grad_norm': '0.6576', 'learning_rate': '0.0001811', 'epoch': '0.1175'}             
{'loss': '0.8249', 'grad_norm': '0.6872', 'learning_rate': '0.0001807', 'epoch': '0.1198'}             
{'loss': '0.7793', 'grad_norm': '0.6475', 'learning_rate': '0.0001802', 'epoch': '0.1221'}             
{'loss': '0.7396', 'grad_norm': '0.6251', 'learning_rate': '0.0001797', 'epoch': '0.1244'}             
{'loss': '0.7254', 'grad_norm': '0.8587', 'learning_rate': '0.0001792', 'epoch': '0.1267'}             
{'loss': '0.7477', 'grad_norm': '0.5831', 'learning_rate': '0.0001788', 'epoch': '0.129'}              
{'loss': '0.7873', 'grad_norm': '0.6854', 'learning_rate': '0.0001783', 'epoch': '0.1313'}             
{'loss': '0.7704', 'grad_norm': '0.5703', 'learning_rate': '0.0001778', 'epoch': '0.1336'}             
{'loss': '0.7858', 'grad_norm': '2.152', 'learning_rate': '0.0001774', 'epoch': '0.1359'}              
{'loss': '0.6793', 'grad_norm': '0.6831', 'learning_rate': '0.0001769', 'epoch': '0.1382'}             
{'loss': '0.889', 'grad_norm': '0.7007', 'learning_rate': '0.0001764', 'epoch': '0.1406'}              
{'loss': '0.7676', 'grad_norm': '0.9103', 'learning_rate': '0.0001759', 'epoch': '0.1429'}             
{'loss': '0.8055', 'grad_norm': '1.449', 'learning_rate': '0.0001755', 'epoch': '0.1452'}              
{'loss': '0.7143', 'grad_norm': '0.7374', 'learning_rate': '0.000175', 'epoch': '0.1475'}              
{'loss': '0.7449', 'grad_norm': '0.5523', 'learning_rate': '0.0001745', 'epoch': '0.1498'}             
{'loss': '0.6586', 'grad_norm': '0.7742', 'learning_rate': '0.0001741', 'epoch': '0.1521'}             
{'loss': '0.698', 'grad_norm': '0.6406', 'learning_rate': '0.0001736', 'epoch': '0.1544'}              
{'loss': '0.7823', 'grad_norm': '0.5595', 'learning_rate': '0.0001731', 'epoch': '0.1567'}             
{'loss': '0.7402', 'grad_norm': '0.5766', 'learning_rate': '0.0001726', 'epoch': '0.159'}              
{'loss': '0.7112', 'grad_norm': '0.694', 'learning_rate': '0.0001722', 'epoch': '0.1613'}              
{'loss': '0.7703', 'grad_norm': '0.5917', 'learning_rate': '0.0001717', 'epoch': '0.1636'}             
{'loss': '0.6494', 'grad_norm': '0.698', 'learning_rate': '0.0001712', 'epoch': '0.1659'}              
{'loss': '0.671', 'grad_norm': '0.6649', 'learning_rate': '0.0001708', 'epoch': '0.1682'}              
{'loss': '0.7963', 'grad_norm': '0.5956', 'learning_rate': '0.0001703', 'epoch': '0.1705'}             
{'loss': '0.7909', 'grad_norm': '0.6126', 'learning_rate': '0.0001698', 'epoch': '0.1728'}             
{'loss': '0.6918', 'grad_norm': '0.6935', 'learning_rate': '0.0001693', 'epoch': '0.1751'}             
{'loss': '0.6512', 'grad_norm': '0.6703', 'learning_rate': '0.0001689', 'epoch': '0.1774'}             
{'loss': '0.7144', 'grad_norm': '0.6902', 'learning_rate': '0.0001684', 'epoch': '0.1797'}             
{'loss': '0.7388', 'grad_norm': '0.6462', 'learning_rate': '0.0001679', 'epoch': '0.182'}              
{'loss': '1.005', 'grad_norm': '0.8236', 'learning_rate': '0.0001675', 'epoch': '0.1843'}              
{'loss': '0.795', 'grad_norm': '0.7009', 'learning_rate': '0.000167', 'epoch': '0.1866'}               
{'loss': '0.7875', 'grad_norm': '0.5874', 'learning_rate': '0.0001665', 'epoch': '0.1889'}             
{'loss': '0.701', 'grad_norm': '1.814', 'learning_rate': '0.000166', 'epoch': '0.1912'}                
{'loss': '0.7916', 'grad_norm': '0.5939', 'learning_rate': '0.0001656', 'epoch': '0.1935'}             
{'loss': '0.6723', 'grad_norm': '0.7629', 'learning_rate': '0.0001651', 'epoch': '0.1959'}             
{'loss': '0.7365', 'grad_norm': '0.5514', 'learning_rate': '0.0001646', 'epoch': '0.1982'}             
{'loss': '0.7455', 'grad_norm': '4.133', 'learning_rate': '0.0001642', 'epoch': '0.2005'}              
{'loss': '0.6803', 'grad_norm': '1.638', 'learning_rate': '0.0001637', 'epoch': '0.2028'}              
{'loss': '0.6614', 'grad_norm': '0.653', 'learning_rate': '0.0001632', 'epoch': '0.2051'}              
{'loss': '0.9468', 'grad_norm': '0.8293', 'learning_rate': '0.0001627', 'epoch': '0.2074'}             
{'loss': '0.7139', 'grad_norm': '0.737', 'learning_rate': '0.0001623', 'epoch': '0.2097'}              
{'loss': '0.7399', 'grad_norm': '0.6102', 'learning_rate': '0.0001618', 'epoch': '0.212'}              
{'loss': '0.5633', 'grad_norm': '0.6784', 'learning_rate': '0.0001613', 'epoch': '0.2143'}             
{'loss': '0.7159', 'grad_norm': '0.5942', 'learning_rate': '0.0001608', 'epoch': '0.2166'}             
{'loss': '0.7888', 'grad_norm': '0.6131', 'learning_rate': '0.0001604', 'epoch': '0.2189'}             
{'loss': '0.6768', 'grad_norm': '0.6068', 'learning_rate': '0.0001599', 'epoch': '0.2212'}             
{'loss': '0.7127', 'grad_norm': '0.6715', 'learning_rate': '0.0001594', 'epoch': '0.2235'}             
{'loss': '0.7102', 'grad_norm': '0.735', 'learning_rate': '0.000159', 'epoch': '0.2258'}               
{'loss': '0.8401', 'grad_norm': '0.7567', 'learning_rate': '0.0001585', 'epoch': '0.2281'}             
{'loss': '0.7674', 'grad_norm': '2.158', 'learning_rate': '0.000158', 'epoch': '0.2304'}               
{'loss': '0.5776', 'grad_norm': '0.6617', 'learning_rate': '0.0001575', 'epoch': '0.2327'}             
{'loss': '0.6297', 'grad_norm': '0.715', 'learning_rate': '0.0001571', 'epoch': '0.235'}               
{'loss': '0.7456', 'grad_norm': '0.6821', 'learning_rate': '0.0001566', 'epoch': '0.2373'}             
{'loss': '0.6185', 'grad_norm': '0.7013', 'learning_rate': '0.0001561', 'epoch': '0.2396'}             
{'loss': '0.7343', 'grad_norm': '0.5272', 'learning_rate': '0.0001557', 'epoch': '0.2419'}             
{'loss': '0.6973', 'grad_norm': '29.09', 'learning_rate': '0.0001552', 'epoch': '0.2442'}              
{'loss': '0.7846', 'grad_norm': '0.6587', 'learning_rate': '0.0001547', 'epoch': '0.2465'}             
{'loss': '0.6059', 'grad_norm': '0.8331', 'learning_rate': '0.0001542', 'epoch': '0.2488'}             
{'loss': '0.6471', 'grad_norm': '0.769', 'learning_rate': '0.0001538', 'epoch': '0.2512'}              
{'loss': '0.6971', 'grad_norm': '0.8254', 'learning_rate': '0.0001533', 'epoch': '0.2535'}             
{'loss': '0.6766', 'grad_norm': '0.6872', 'learning_rate': '0.0001528', 'epoch': '0.2558'}             
{'loss': '0.6312', 'grad_norm': '0.6485', 'learning_rate': '0.0001524', 'epoch': '0.2581'}             
{'loss': '0.6748', 'grad_norm': '0.7292', 'learning_rate': '0.0001519', 'epoch': '0.2604'}             
{'loss': '0.6082', 'grad_norm': '0.6007', 'learning_rate': '0.0001514', 'epoch': '0.2627'}             
{'loss': '0.6675', 'grad_norm': '0.7073', 'learning_rate': '0.0001509', 'epoch': '0.265'}              
{'loss': '0.5499', 'grad_norm': '0.9573', 'learning_rate': '0.0001505', 'epoch': '0.2673'}             
{'loss': '0.5594', 'grad_norm': '0.6103', 'learning_rate': '0.00015', 'epoch': '0.2696'}               
{'loss': '0.7716', 'grad_norm': '0.5256', 'learning_rate': '0.0001495', 'epoch': '0.2719'}             
{'loss': '0.5177', 'grad_norm': '0.7259', 'learning_rate': '0.0001491', 'epoch': '0.2742'}             
{'loss': '0.5944', 'grad_norm': '0.6718', 'learning_rate': '0.0001486', 'epoch': '0.2765'}             
{'loss': '0.7232', 'grad_norm': '0.7323', 'learning_rate': '0.0001481', 'epoch': '0.2788'}             
{'loss': '0.6827', 'grad_norm': '0.8394', 'learning_rate': '0.0001476', 'epoch': '0.2811'}             
{'loss': '0.6825', 'grad_norm': '0.7217', 'learning_rate': '0.0001472', 'epoch': '0.2834'}             
{'loss': '0.5879', 'grad_norm': '0.7387', 'learning_rate': '0.0001467', 'epoch': '0.2857'}             
{'loss': '0.712', 'grad_norm': '0.8994', 'learning_rate': '0.0001462', 'epoch': '0.288'}               
{'loss': '0.6993', 'grad_norm': '0.5818', 'learning_rate': '0.0001458', 'epoch': '0.2903'}             
{'loss': '0.7238', 'grad_norm': '0.5166', 'learning_rate': '0.0001453', 'epoch': '0.2926'}             
{'loss': '0.6826', 'grad_norm': '0.796', 'learning_rate': '0.0001448', 'epoch': '0.2949'}              
{'loss': '0.7428', 'grad_norm': '0.571', 'learning_rate': '0.0001443', 'epoch': '0.2972'}              
{'loss': '0.6341', 'grad_norm': '0.6607', 'learning_rate': '0.0001439', 'epoch': '0.2995'}             
{'loss': '0.7735', 'grad_norm': '0.7123', 'learning_rate': '0.0001434', 'epoch': '0.3018'}             
{'loss': '0.6838', 'grad_norm': '2.028', 'learning_rate': '0.0001429', 'epoch': '0.3041'}              
{'loss': '0.6472', 'grad_norm': '0.6625', 'learning_rate': '0.0001425', 'epoch': '0.3065'}             
{'loss': '0.6516', 'grad_norm': '0.5824', 'learning_rate': '0.000142', 'epoch': '0.3088'}              
{'loss': '0.6295', 'grad_norm': '0.9179', 'learning_rate': '0.0001415', 'epoch': '0.3111'}             
{'loss': '0.7464', 'grad_norm': '0.6789', 'learning_rate': '0.000141', 'epoch': '0.3134'}              
{'loss': '0.6094', 'grad_norm': '0.7097', 'learning_rate': '0.0001406', 'epoch': '0.3157'}             
{'loss': '0.6306', 'grad_norm': '0.7262', 'learning_rate': '0.0001401', 'epoch': '0.318'}              
{'loss': '0.647', 'grad_norm': '1.271', 'learning_rate': '0.0001396', 'epoch': '0.3203'}               
{'loss': '0.6401', 'grad_norm': '0.7096', 'learning_rate': '0.0001392', 'epoch': '0.3226'}             
{'loss': '0.6138', 'grad_norm': '0.6651', 'learning_rate': '0.0001387', 'epoch': '0.3249'}             
{'loss': '0.6371', 'grad_norm': '0.6309', 'learning_rate': '0.0001382', 'epoch': '0.3272'}             
{'loss': '0.8028', 'grad_norm': '0.8023', 'learning_rate': '0.0001377', 'epoch': '0.3295'}             
{'loss': '0.5854', 'grad_norm': '0.5646', 'learning_rate': '0.0001373', 'epoch': '0.3318'}             
{'loss': '0.6443', 'grad_norm': '0.6797', 'learning_rate': '0.0001368', 'epoch': '0.3341'}             
{'loss': '0.5877', 'grad_norm': '0.7349', 'learning_rate': '0.0001363', 'epoch': '0.3364'}             
{'loss': '0.6179', 'grad_norm': '0.9174', 'learning_rate': '0.0001358', 'epoch': '0.3387'}             
{'loss': '0.5975', 'grad_norm': '0.6749', 'learning_rate': '0.0001354', 'epoch': '0.341'}              
{'loss': '0.641', 'grad_norm': '0.5904', 'learning_rate': '0.0001349', 'epoch': '0.3433'}              
{'loss': '0.6332', 'grad_norm': '0.7641', 'learning_rate': '0.0001344', 'epoch': '0.3456'}             
{'loss': '0.7319', 'grad_norm': '0.6389', 'learning_rate': '0.000134', 'epoch': '0.3479'}              
{'loss': '0.6646', 'grad_norm': '1.07', 'learning_rate': '0.0001335', 'epoch': '0.3502'}               
{'loss': '0.7117', 'grad_norm': '1.162', 'learning_rate': '0.000133', 'epoch': '0.3525'}               
{'loss': '0.6124', 'grad_norm': '0.7805', 'learning_rate': '0.0001325', 'epoch': '0.3548'}             
{'loss': '0.5946', 'grad_norm': '0.6931', 'learning_rate': '0.0001321', 'epoch': '0.3571'}             
{'loss': '0.5629', 'grad_norm': '0.6326', 'learning_rate': '0.0001316', 'epoch': '0.3594'}             
{'loss': '0.6626', 'grad_norm': '0.7584', 'learning_rate': '0.0001311', 'epoch': '0.3618'}             
{'loss': '0.6723', 'grad_norm': '0.8184', 'learning_rate': '0.0001307', 'epoch': '0.3641'}             
{'loss': '0.6207', 'grad_norm': '0.7239', 'learning_rate': '0.0001302', 'epoch': '0.3664'}             
{'loss': '0.5891', 'grad_norm': '0.8023', 'learning_rate': '0.0001297', 'epoch': '0.3687'}             
{'loss': '0.5819', 'grad_norm': '0.5898', 'learning_rate': '0.0001292', 'epoch': '0.371'}              
{'loss': '0.6079', 'grad_norm': '0.6509', 'learning_rate': '0.0001288', 'epoch': '0.3733'}             
{'loss': '0.6144', 'grad_norm': '2.24', 'learning_rate': '0.0001283', 'epoch': '0.3756'}               
{'loss': '0.5921', 'grad_norm': '0.7252', 'learning_rate': '0.0001278', 'epoch': '0.3779'}             
{'loss': '0.7108', 'grad_norm': '0.643', 'learning_rate': '0.0001274', 'epoch': '0.3802'}              
{'loss': '0.5693', 'grad_norm': '0.5982', 'learning_rate': '0.0001269', 'epoch': '0.3825'}             
{'loss': '0.5801', 'grad_norm': '0.6072', 'learning_rate': '0.0001264', 'epoch': '0.3848'}             
{'loss': '0.7429', 'grad_norm': '0.906', 'learning_rate': '0.0001259', 'epoch': '0.3871'}              
{'loss': '0.7358', 'grad_norm': '0.5468', 'learning_rate': '0.0001255', 'epoch': '0.3894'}             
{'loss': '0.6183', 'grad_norm': '0.5541', 'learning_rate': '0.000125', 'epoch': '0.3917'}              
{'loss': '0.6956', 'grad_norm': '0.6743', 'learning_rate': '0.0001245', 'epoch': '0.394'}              
{'loss': '0.7019', 'grad_norm': '0.6122', 'learning_rate': '0.0001241', 'epoch': '0.3963'}             
{'loss': '0.6791', 'grad_norm': '0.7477', 'learning_rate': '0.0001236', 'epoch': '0.3986'}             
{'loss': '0.5913', 'grad_norm': '0.9395', 'learning_rate': '0.0001231', 'epoch': '0.4009'}             
{'loss': '0.6121', 'grad_norm': '0.6858', 'learning_rate': '0.0001226', 'epoch': '0.4032'}             
{'loss': '0.6859', 'grad_norm': '0.6724', 'learning_rate': '0.0001222', 'epoch': '0.4055'}             
{'loss': '0.5848', 'grad_norm': '0.6873', 'learning_rate': '0.0001217', 'epoch': '0.4078'}             
{'loss': '0.7109', 'grad_norm': '0.6811', 'learning_rate': '0.0001212', 'epoch': '0.4101'}             
{'loss': '0.5902', 'grad_norm': '0.7023', 'learning_rate': '0.0001208', 'epoch': '0.4124'}             
{'loss': '0.7342', 'grad_norm': '0.8165', 'learning_rate': '0.0001203', 'epoch': '0.4147'}             
{'loss': '0.5664', 'grad_norm': '0.674', 'learning_rate': '0.0001198', 'epoch': '0.4171'}              
{'loss': '0.6427', 'grad_norm': '1.111', 'learning_rate': '0.0001193', 'epoch': '0.4194'}              
{'loss': '0.6065', 'grad_norm': '0.6647', 'learning_rate': '0.0001189', 'epoch': '0.4217'}             
{'loss': '0.5793', 'grad_norm': '0.6721', 'learning_rate': '0.0001184', 'epoch': '0.424'}              
{'loss': '0.6686', 'grad_norm': '0.5807', 'learning_rate': '0.0001179', 'epoch': '0.4263'}             
{'loss': '0.5705', 'grad_norm': '0.6107', 'learning_rate': '0.0001175', 'epoch': '0.4286'}             
{'loss': '0.6553', 'grad_norm': '0.7594', 'learning_rate': '0.000117', 'epoch': '0.4309'}              
{'loss': '0.5925', 'grad_norm': '0.7651', 'learning_rate': '0.0001165', 'epoch': '0.4332'}             
{'loss': '0.5751', 'grad_norm': '1.566', 'learning_rate': '0.000116', 'epoch': '0.4355'}               
{'loss': '0.6164', 'grad_norm': '0.8485', 'learning_rate': '0.0001156', 'epoch': '0.4378'}             
{'loss': '0.6269', 'grad_norm': '46.6', 'learning_rate': '0.0001151', 'epoch': '0.4401'}               
{'loss': '0.5365', 'grad_norm': '1.393', 'learning_rate': '0.0001146', 'epoch': '0.4424'}              
{'loss': '0.6474', 'grad_norm': '0.7473', 'learning_rate': '0.0001142', 'epoch': '0.4447'}             
{'loss': '0.6095', 'grad_norm': '0.7546', 'learning_rate': '0.0001137', 'epoch': '0.447'}              
{'loss': '0.6669', 'grad_norm': '0.7517', 'learning_rate': '0.0001132', 'epoch': '0.4493'}             
{'loss': '0.7598', 'grad_norm': '0.6949', 'learning_rate': '0.0001127', 'epoch': '0.4516'}             
{'loss': '0.7516', 'grad_norm': '0.9586', 'learning_rate': '0.0001123', 'epoch': '0.4539'}             
{'loss': '0.5646', 'grad_norm': '0.7684', 'learning_rate': '0.0001118', 'epoch': '0.4562'}             
{'loss': '0.5884', 'grad_norm': '0.65', 'learning_rate': '0.0001113', 'epoch': '0.4585'}               
{'loss': '0.4916', 'grad_norm': '0.7924', 'learning_rate': '0.0001108', 'epoch': '0.4608'}             
{'loss': '0.616', 'grad_norm': '0.6945', 'learning_rate': '0.0001104', 'epoch': '0.4631'}              
{'loss': '0.7856', 'grad_norm': '0.7076', 'learning_rate': '0.0001099', 'epoch': '0.4654'}             
{'loss': '0.629', 'grad_norm': '0.708', 'learning_rate': '0.0001094', 'epoch': '0.4677'}               
{'loss': '0.6867', 'grad_norm': '0.6259', 'learning_rate': '0.000109', 'epoch': '0.47'}                
{'loss': '0.519', 'grad_norm': '0.6818', 'learning_rate': '0.0001085', 'epoch': '0.4724'}              
{'loss': '0.5748', 'grad_norm': '1.339', 'learning_rate': '0.000108', 'epoch': '0.4747'}               
{'loss': '0.6243', 'grad_norm': '0.7804', 'learning_rate': '0.0001075', 'epoch': '0.477'}              
{'loss': '0.6346', 'grad_norm': '0.6725', 'learning_rate': '0.0001071', 'epoch': '0.4793'}             
{'loss': '0.5456', 'grad_norm': '0.6968', 'learning_rate': '0.0001066', 'epoch': '0.4816'}             
{'loss': '0.6387', 'grad_norm': '6.192', 'learning_rate': '0.0001061', 'epoch': '0.4839'}              
{'loss': '0.6134', 'grad_norm': '0.7031', 'learning_rate': '0.0001057', 'epoch': '0.4862'}             
{'loss': '0.5228', 'grad_norm': '0.7418', 'learning_rate': '0.0001052', 'epoch': '0.4885'}             
{'loss': '0.6851', 'grad_norm': '0.6711', 'learning_rate': '0.0001047', 'epoch': '0.4908'}             
{'loss': '0.6144', 'grad_norm': '0.6265', 'learning_rate': '0.0001042', 'epoch': '0.4931'}             
{'loss': '0.6672', 'grad_norm': '1.797', 'learning_rate': '0.0001038', 'epoch': '0.4954'}              
{'loss': '0.6125', 'grad_norm': '0.6996', 'learning_rate': '0.0001033', 'epoch': '0.4977'}             
{'loss': '0.6355', 'grad_norm': '0.7779', 'learning_rate': '0.0001028', 'epoch': '0.5'}                
{'loss': '0.6202', 'grad_norm': '0.725', 'learning_rate': '0.0001024', 'epoch': '0.5023'}              
{'loss': '0.6384', 'grad_norm': '0.5536', 'learning_rate': '0.0001019', 'epoch': '0.5046'}             
{'loss': '0.673', 'grad_norm': '1.154', 'learning_rate': '0.0001014', 'epoch': '0.5069'}               
{'loss': '0.6689', 'grad_norm': '0.5904', 'learning_rate': '0.0001009', 'epoch': '0.5092'}             
{'loss': '0.5583', 'grad_norm': '0.6963', 'learning_rate': '0.0001005', 'epoch': '0.5115'}             
{'loss': '0.6197', 'grad_norm': '0.7055', 'learning_rate': '0.0001', 'epoch': '0.5138'}                
{'loss': '0.5063', 'grad_norm': '0.7208', 'learning_rate': '9.953e-05', 'epoch': '0.5161'}             
{'loss': '0.5691', 'grad_norm': '0.6183', 'learning_rate': '9.906e-05', 'epoch': '0.5184'}             
{'loss': '0.668', 'grad_norm': '0.647', 'learning_rate': '9.858e-05', 'epoch': '0.5207'}               
{'loss': '0.6523', 'grad_norm': '0.5769', 'learning_rate': '9.811e-05', 'epoch': '0.523'}              
{'loss': '0.6216', 'grad_norm': '0.6314', 'learning_rate': '9.764e-05', 'epoch': '0.5253'}             
{'loss': '0.5931', 'grad_norm': '0.7069', 'learning_rate': '9.717e-05', 'epoch': '0.5276'}             
{'loss': '0.5486', 'grad_norm': '0.6317', 'learning_rate': '9.67e-05', 'epoch': '0.53'}                
{'loss': '0.5648', 'grad_norm': '0.5978', 'learning_rate': '9.623e-05', 'epoch': '0.5323'}             
{'loss': '0.7733', 'grad_norm': '0.6256', 'learning_rate': '9.575e-05', 'epoch': '0.5346'}             
{'loss': '0.582', 'grad_norm': '0.7558', 'learning_rate': '9.528e-05', 'epoch': '0.5369'}              
{'loss': '0.6539', 'grad_norm': '0.7474', 'learning_rate': '9.481e-05', 'epoch': '0.5392'}             
{'loss': '0.7479', 'grad_norm': '0.6939', 'learning_rate': '9.434e-05', 'epoch': '0.5415'}             
{'loss': '0.549', 'grad_norm': '0.6679', 'learning_rate': '9.387e-05', 'epoch': '0.5438'}              
{'loss': '0.6253', 'grad_norm': '0.6289', 'learning_rate': '9.34e-05', 'epoch': '0.5461'}              
{'loss': '0.8291', 'grad_norm': '0.725', 'learning_rate': '9.292e-05', 'epoch': '0.5484'}              
{'loss': '0.512', 'grad_norm': '1.305', 'learning_rate': '9.245e-05', 'epoch': '0.5507'}               
{'loss': '0.6604', 'grad_norm': '0.5755', 'learning_rate': '9.198e-05', 'epoch': '0.553'}              
{'loss': '0.5529', 'grad_norm': '0.6566', 'learning_rate': '9.151e-05', 'epoch': '0.5553'}             
{'loss': '0.6318', 'grad_norm': '0.7571', 'learning_rate': '9.104e-05', 'epoch': '0.5576'}             
{'loss': '0.5679', 'grad_norm': '0.9231', 'learning_rate': '9.057e-05', 'epoch': '0.5599'}             
{'loss': '0.4851', 'grad_norm': '0.6786', 'learning_rate': '9.009e-05', 'epoch': '0.5622'}             
{'loss': '0.5982', 'grad_norm': '0.7659', 'learning_rate': '8.962e-05', 'epoch': '0.5645'}             
{'loss': '0.5866', 'grad_norm': '0.7897', 'learning_rate': '8.915e-05', 'epoch': '0.5668'}             
{'loss': '0.5251', 'grad_norm': '0.6557', 'learning_rate': '8.868e-05', 'epoch': '0.5691'}             
{'loss': '0.6534', 'grad_norm': '0.5151', 'learning_rate': '8.821e-05', 'epoch': '0.5714'}             
{'loss': '0.507', 'grad_norm': '0.6653', 'learning_rate': '8.774e-05', 'epoch': '0.5737'}              
{'loss': '0.6939', 'grad_norm': '1.028', 'learning_rate': '8.726e-05', 'epoch': '0.576'}               
{'loss': '0.5379', 'grad_norm': '0.7818', 'learning_rate': '8.679e-05', 'epoch': '0.5783'}             
{'loss': '0.6253', 'grad_norm': '0.837', 'learning_rate': '8.632e-05', 'epoch': '0.5806'}              
{'loss': '0.6759', 'grad_norm': '0.8239', 'learning_rate': '8.585e-05', 'epoch': '0.5829'}             
{'loss': '0.5901', 'grad_norm': '0.573', 'learning_rate': '8.538e-05', 'epoch': '0.5853'}              
{'loss': '0.6029', 'grad_norm': '0.7206', 'learning_rate': '8.491e-05', 'epoch': '0.5876'}             
{'loss': '0.5511', 'grad_norm': '0.7012', 'learning_rate': '8.443e-05', 'epoch': '0.5899'}             
{'loss': '0.5373', 'grad_norm': '0.736', 'learning_rate': '8.396e-05', 'epoch': '0.5922'}              
{'loss': '0.643', 'grad_norm': '0.772', 'learning_rate': '8.349e-05', 'epoch': '0.5945'}               
{'loss': '0.6064', 'grad_norm': '0.7816', 'learning_rate': '8.302e-05', 'epoch': '0.5968'}             
{'loss': '0.584', 'grad_norm': '0.7606', 'learning_rate': '8.255e-05', 'epoch': '0.5991'}              
{'loss': '0.536', 'grad_norm': '0.7528', 'learning_rate': '8.208e-05', 'epoch': '0.6014'}              
{'loss': '0.64', 'grad_norm': '0.5475', 'learning_rate': '8.16e-05', 'epoch': '0.6037'}                
{'loss': '0.6621', 'grad_norm': '0.6068', 'learning_rate': '8.113e-05', 'epoch': '0.606'}              
{'loss': '0.6781', 'grad_norm': '0.6814', 'learning_rate': '8.066e-05', 'epoch': '0.6083'}             
{'loss': '0.6335', 'grad_norm': '0.6123', 'learning_rate': '8.019e-05', 'epoch': '0.6106'}             
{'loss': '0.5944', 'grad_norm': '0.8284', 'learning_rate': '7.972e-05', 'epoch': '0.6129'}             
{'loss': '0.4737', 'grad_norm': '0.6502', 'learning_rate': '7.925e-05', 'epoch': '0.6152'}             
{'loss': '0.6473', 'grad_norm': '0.6877', 'learning_rate': '7.877e-05', 'epoch': '0.6175'}             
{'loss': '0.5414', 'grad_norm': '0.7364', 'learning_rate': '7.83e-05', 'epoch': '0.6198'}              
{'loss': '0.5449', 'grad_norm': '0.7282', 'learning_rate': '7.783e-05', 'epoch': '0.6221'}             
{'loss': '0.6429', 'grad_norm': '0.713', 'learning_rate': '7.736e-05', 'epoch': '0.6244'}              
{'loss': '0.5514', 'grad_norm': '0.6583', 'learning_rate': '7.689e-05', 'epoch': '0.6267'}             
{'loss': '0.582', 'grad_norm': '0.7366', 'learning_rate': '7.642e-05', 'epoch': '0.629'}               
{'loss': '0.6055', 'grad_norm': '0.9642', 'learning_rate': '7.594e-05', 'epoch': '0.6313'}             
{'loss': '0.6347', 'grad_norm': '0.6876', 'learning_rate': '7.547e-05', 'epoch': '0.6336'}             
{'loss': '0.7811', 'grad_norm': '0.8083', 'learning_rate': '7.5e-05', 'epoch': '0.6359'}               
{'loss': '0.57', 'grad_norm': '0.6865', 'learning_rate': '7.453e-05', 'epoch': '0.6382'}               
{'loss': '0.6602', 'grad_norm': '1.308', 'learning_rate': '7.406e-05', 'epoch': '0.6406'}              
{'loss': '0.5685', 'grad_norm': '0.7208', 'learning_rate': '7.358e-05', 'epoch': '0.6429'}             
{'loss': '0.5656', 'grad_norm': '0.7693', 'learning_rate': '7.311e-05', 'epoch': '0.6452'}             
{'loss': '0.5647', 'grad_norm': '0.7145', 'learning_rate': '7.264e-05', 'epoch': '0.6475'}             
{'loss': '0.6572', 'grad_norm': '0.606', 'learning_rate': '7.217e-05', 'epoch': '0.6498'}              
{'loss': '0.5692', 'grad_norm': '0.6468', 'learning_rate': '7.17e-05', 'epoch': '0.6521'}              
{'loss': '0.7013', 'grad_norm': '1.139', 'learning_rate': '7.123e-05', 'epoch': '0.6544'}              
{'loss': '0.5278', 'grad_norm': '0.6108', 'learning_rate': '7.075e-05', 'epoch': '0.6567'}             
{'loss': '0.7068', 'grad_norm': '0.9266', 'learning_rate': '7.028e-05', 'epoch': '0.659'}              
{'loss': '0.5866', 'grad_norm': '0.5983', 'learning_rate': '6.981e-05', 'epoch': '0.6613'}             
{'loss': '0.7429', 'grad_norm': '0.7525', 'learning_rate': '6.934e-05', 'epoch': '0.6636'}             
{'loss': '0.5486', 'grad_norm': '0.6002', 'learning_rate': '6.887e-05', 'epoch': '0.6659'}             
{'loss': '0.6707', 'grad_norm': '0.7478', 'learning_rate': '6.84e-05', 'epoch': '0.6682'}              
{'loss': '0.473', 'grad_norm': '0.7223', 'learning_rate': '6.792e-05', 'epoch': '0.6705'}              
{'loss': '0.6583', 'grad_norm': '0.6295', 'learning_rate': '6.745e-05', 'epoch': '0.6728'}             
{'loss': '0.4973', 'grad_norm': '0.637', 'learning_rate': '6.698e-05', 'epoch': '0.6751'}              
{'loss': '0.6633', 'grad_norm': '0.7371', 'learning_rate': '6.651e-05', 'epoch': '0.6774'}             
{'loss': '0.6287', 'grad_norm': '5.462', 'learning_rate': '6.604e-05', 'epoch': '0.6797'}              
{'loss': '0.5798', 'grad_norm': '0.5596', 'learning_rate': '6.557e-05', 'epoch': '0.682'}              
{'loss': '0.6464', 'grad_norm': '0.66', 'learning_rate': '6.509e-05', 'epoch': '0.6843'}               
{'loss': '0.6702', 'grad_norm': '0.7073', 'learning_rate': '6.462e-05', 'epoch': '0.6866'}             
{'loss': '0.6131', 'grad_norm': '0.6034', 'learning_rate': '6.415e-05', 'epoch': '0.6889'}             
{'loss': '0.5806', 'grad_norm': '0.6287', 'learning_rate': '6.368e-05', 'epoch': '0.6912'}             
{'loss': '0.4749', 'grad_norm': '0.7379', 'learning_rate': '6.321e-05', 'epoch': '0.6935'}             
{'loss': '0.5028', 'grad_norm': '0.6673', 'learning_rate': '6.274e-05', 'epoch': '0.6959'}             
{'loss': '0.5235', 'grad_norm': '0.6565', 'learning_rate': '6.226e-05', 'epoch': '0.6982'}             
{'loss': '0.5698', 'grad_norm': '0.5777', 'learning_rate': '6.179e-05', 'epoch': '0.7005'}             
{'loss': '0.6336', 'grad_norm': '0.7593', 'learning_rate': '6.132e-05', 'epoch': '0.7028'}             
{'loss': '0.6848', 'grad_norm': '0.8509', 'learning_rate': '6.085e-05', 'epoch': '0.7051'}             
{'loss': '0.6755', 'grad_norm': '0.6572', 'learning_rate': '6.038e-05', 'epoch': '0.7074'}             
{'loss': '0.5925', 'grad_norm': '0.7497', 'learning_rate': '5.991e-05', 'epoch': '0.7097'}             
{'loss': '0.5459', 'grad_norm': '0.7243', 'learning_rate': '5.943e-05', 'epoch': '0.712'}              
{'loss': '0.686', 'grad_norm': '1.275', 'learning_rate': '5.896e-05', 'epoch': '0.7143'}               
{'loss': '0.6408', 'grad_norm': '0.6012', 'learning_rate': '5.849e-05', 'epoch': '0.7166'}             
{'loss': '0.6589', 'grad_norm': '1.147', 'learning_rate': '5.802e-05', 'epoch': '0.7189'}              
{'loss': '0.6846', 'grad_norm': '0.7501', 'learning_rate': '5.755e-05', 'epoch': '0.7212'}             
{'loss': '0.602', 'grad_norm': '0.7578', 'learning_rate': '5.708e-05', 'epoch': '0.7235'}              
{'loss': '0.6929', 'grad_norm': '1.424', 'learning_rate': '5.66e-05', 'epoch': '0.7258'}               
{'loss': '0.5686', 'grad_norm': '0.6946', 'learning_rate': '5.613e-05', 'epoch': '0.7281'}             
{'loss': '0.5459', 'grad_norm': '0.7554', 'learning_rate': '5.566e-05', 'epoch': '0.7304'}             
{'loss': '0.4948', 'grad_norm': '0.7185', 'learning_rate': '5.519e-05', 'epoch': '0.7327'}             
{'loss': '0.5869', 'grad_norm': '0.5912', 'learning_rate': '5.472e-05', 'epoch': '0.735'}              
{'loss': '0.6348', 'grad_norm': '0.5907', 'learning_rate': '5.425e-05', 'epoch': '0.7373'}             
{'loss': '0.5782', 'grad_norm': '0.7222', 'learning_rate': '5.377e-05', 'epoch': '0.7396'}             
{'loss': '0.5447', 'grad_norm': '0.6608', 'learning_rate': '5.33e-05', 'epoch': '0.7419'}              
{'loss': '0.6876', 'grad_norm': '0.5489', 'learning_rate': '5.283e-05', 'epoch': '0.7442'}             
{'loss': '0.6792', 'grad_norm': '0.5963', 'learning_rate': '5.236e-05', 'epoch': '0.7465'}             
{'loss': '0.5699', 'grad_norm': '0.6224', 'learning_rate': '5.189e-05', 'epoch': '0.7488'}             
{'loss': '0.5835', 'grad_norm': '0.7271', 'learning_rate': '5.142e-05', 'epoch': '0.7512'}             
{'loss': '0.6089', 'grad_norm': '0.7953', 'learning_rate': '5.094e-05', 'epoch': '0.7535'}             
{'loss': '0.646', 'grad_norm': '0.9411', 'learning_rate': '5.047e-05', 'epoch': '0.7558'}              
{'loss': '0.5955', 'grad_norm': '0.6665', 'learning_rate': '5e-05', 'epoch': '0.7581'}                 
{'loss': '0.6611', 'grad_norm': '0.5541', 'learning_rate': '4.953e-05', 'epoch': '0.7604'}             
{'loss': '0.5331', 'grad_norm': '0.7769', 'learning_rate': '4.906e-05', 'epoch': '0.7627'}             
{'loss': '0.5725', 'grad_norm': '0.9532', 'learning_rate': '4.858e-05', 'epoch': '0.765'}              
{'loss': '0.6249', 'grad_norm': '0.7445', 'learning_rate': '4.811e-05', 'epoch': '0.7673'}             
{'loss': '0.6488', 'grad_norm': '0.655', 'learning_rate': '4.764e-05', 'epoch': '0.7696'}              
{'loss': '0.5975', 'grad_norm': '0.5646', 'learning_rate': '4.717e-05', 'epoch': '0.7719'}             
{'loss': '0.5021', 'grad_norm': '0.7826', 'learning_rate': '4.67e-05', 'epoch': '0.7742'}              
{'loss': '0.6172', 'grad_norm': '0.6066', 'learning_rate': '4.623e-05', 'epoch': '0.7765'}             
{'loss': '0.4962', 'grad_norm': '27.96', 'learning_rate': '4.575e-05', 'epoch': '0.7788'}              
{'loss': '0.5559', 'grad_norm': '0.6903', 'learning_rate': '4.528e-05', 'epoch': '0.7811'}             
{'loss': '0.5108', 'grad_norm': '0.6935', 'learning_rate': '4.481e-05', 'epoch': '0.7834'}             
{'loss': '0.6045', 'grad_norm': '0.5501', 'learning_rate': '4.434e-05', 'epoch': '0.7857'}             
{'loss': '0.5843', 'grad_norm': '0.7504', 'learning_rate': '4.387e-05', 'epoch': '0.788'}              
{'loss': '0.6023', 'grad_norm': '0.594', 'learning_rate': '4.34e-05', 'epoch': '0.7903'}               
{'loss': '0.6191', 'grad_norm': '0.8226', 'learning_rate': '4.292e-05', 'epoch': '0.7926'}             
{'loss': '0.5678', 'grad_norm': '0.7123', 'learning_rate': '4.245e-05', 'epoch': '0.7949'}             
{'loss': '0.4981', 'grad_norm': '0.6474', 'learning_rate': '4.198e-05', 'epoch': '0.7972'}             
{'loss': '0.61', 'grad_norm': '0.4926', 'learning_rate': '4.151e-05', 'epoch': '0.7995'}               
{'loss': '0.6231', 'grad_norm': '0.6171', 'learning_rate': '4.104e-05', 'epoch': '0.8018'}             
{'loss': '0.6295', 'grad_norm': '0.4716', 'learning_rate': '4.057e-05', 'epoch': '0.8041'}             
{'loss': '0.5081', 'grad_norm': '0.7089', 'learning_rate': '4.009e-05', 'epoch': '0.8065'}             
{'loss': '0.5477', 'grad_norm': '0.667', 'learning_rate': '3.962e-05', 'epoch': '0.8088'}              
{'loss': '0.5226', 'grad_norm': '0.7296', 'learning_rate': '3.915e-05', 'epoch': '0.8111'}             
{'loss': '0.5092', 'grad_norm': '0.7331', 'learning_rate': '3.868e-05', 'epoch': '0.8134'}             
{'loss': '0.5802', 'grad_norm': '0.6332', 'learning_rate': '3.821e-05', 'epoch': '0.8157'}             
{'loss': '0.5561', 'grad_norm': '0.7515', 'learning_rate': '3.774e-05', 'epoch': '0.818'}              
{'loss': '0.4915', 'grad_norm': '0.742', 'learning_rate': '3.726e-05', 'epoch': '0.8203'}              
{'loss': '0.5517', 'grad_norm': '0.7282', 'learning_rate': '3.679e-05', 'epoch': '0.8226'}             
{'loss': '0.5657', 'grad_norm': '0.545', 'learning_rate': '3.632e-05', 'epoch': '0.8249'}              
{'loss': '0.6397', 'grad_norm': '6.894', 'learning_rate': '3.585e-05', 'epoch': '0.8272'}              
{'loss': '0.5999', 'grad_norm': '0.7526', 'learning_rate': '3.538e-05', 'epoch': '0.8295'}             
{'loss': '0.5575', 'grad_norm': '0.9095', 'learning_rate': '3.491e-05', 'epoch': '0.8318'}             
{'loss': '0.6429', 'grad_norm': '0.5952', 'learning_rate': '3.443e-05', 'epoch': '0.8341'}             
{'loss': '0.5305', 'grad_norm': '6.23', 'learning_rate': '3.396e-05', 'epoch': '0.8364'}               
{'loss': '0.4834', 'grad_norm': '0.7814', 'learning_rate': '3.349e-05', 'epoch': '0.8387'}             
{'loss': '0.466', 'grad_norm': '0.7303', 'learning_rate': '3.302e-05', 'epoch': '0.841'}               
{'loss': '0.4826', 'grad_norm': '0.7256', 'learning_rate': '3.255e-05', 'epoch': '0.8433'}             
{'loss': '0.5018', 'grad_norm': '0.7278', 'learning_rate': '3.208e-05', 'epoch': '0.8456'}             
{'loss': '0.4884', 'grad_norm': '0.6818', 'learning_rate': '3.16e-05', 'epoch': '0.8479'}              
{'loss': '0.6891', 'grad_norm': '0.8488', 'learning_rate': '3.113e-05', 'epoch': '0.8502'}             
{'loss': '0.5536', 'grad_norm': '0.7863', 'learning_rate': '3.066e-05', 'epoch': '0.8525'}             
{'loss': '0.6038', 'grad_norm': '0.5846', 'learning_rate': '3.019e-05', 'epoch': '0.8548'}             
{'loss': '0.5625', 'grad_norm': '0.8289', 'learning_rate': '2.972e-05', 'epoch': '0.8571'}             
{'loss': '0.5697', 'grad_norm': '0.7733', 'learning_rate': '2.925e-05', 'epoch': '0.8594'}             
{'loss': '0.5133', 'grad_norm': '0.7401', 'learning_rate': '2.877e-05', 'epoch': '0.8618'}             
{'loss': '0.6173', 'grad_norm': '0.7686', 'learning_rate': '2.83e-05', 'epoch': '0.8641'}              
{'loss': '0.6092', 'grad_norm': '8.421', 'learning_rate': '2.783e-05', 'epoch': '0.8664'}              
{'loss': '0.5726', 'grad_norm': '0.7178', 'learning_rate': '2.736e-05', 'epoch': '0.8687'}             
{'loss': '0.6303', 'grad_norm': '0.76', 'learning_rate': '2.689e-05', 'epoch': '0.871'}                
{'loss': '0.5703', 'grad_norm': '0.695', 'learning_rate': '2.642e-05', 'epoch': '0.8733'}              
{'loss': '0.5798', 'grad_norm': '0.6117', 'learning_rate': '2.594e-05', 'epoch': '0.8756'}             
{'loss': '0.5455', 'grad_norm': '0.5466', 'learning_rate': '2.547e-05', 'epoch': '0.8779'}             
{'loss': '0.5967', 'grad_norm': '0.5078', 'learning_rate': '2.5e-05', 'epoch': '0.8802'}               
{'loss': '0.5516', 'grad_norm': '0.7812', 'learning_rate': '2.453e-05', 'epoch': '0.8825'}             
{'loss': '0.6216', 'grad_norm': '0.548', 'learning_rate': '2.406e-05', 'epoch': '0.8848'}              
{'loss': '0.6446', 'grad_norm': '0.6944', 'learning_rate': '2.358e-05', 'epoch': '0.8871'}             
{'loss': '0.6624', 'grad_norm': '0.7053', 'learning_rate': '2.311e-05', 'epoch': '0.8894'}             
{'loss': '0.4958', 'grad_norm': '0.6882', 'learning_rate': '2.264e-05', 'epoch': '0.8917'}             
{'loss': '0.5617', 'grad_norm': '0.6871', 'learning_rate': '2.217e-05', 'epoch': '0.894'}              
{'loss': '0.5536', 'grad_norm': '0.7592', 'learning_rate': '2.17e-05', 'epoch': '0.8963'}              
{'loss': '0.5156', 'grad_norm': '0.6423', 'learning_rate': '2.123e-05', 'epoch': '0.8986'}             
{'loss': '0.5859', 'grad_norm': '0.8402', 'learning_rate': '2.075e-05', 'epoch': '0.9009'}             
{'loss': '0.4972', 'grad_norm': '0.9633', 'learning_rate': '2.028e-05', 'epoch': '0.9032'}             
{'loss': '0.6087', 'grad_norm': '1.858', 'learning_rate': '1.981e-05', 'epoch': '0.9055'}              
{'loss': '0.5295', 'grad_norm': '0.7498', 'learning_rate': '1.934e-05', 'epoch': '0.9078'}             
{'loss': '0.5104', 'grad_norm': '0.7019', 'learning_rate': '1.887e-05', 'epoch': '0.9101'}             
{'loss': '0.5477', 'grad_norm': '0.8022', 'learning_rate': '1.84e-05', 'epoch': '0.9124'}              
{'loss': '0.579', 'grad_norm': '0.6045', 'learning_rate': '1.792e-05', 'epoch': '0.9147'}              
{'loss': '0.5898', 'grad_norm': '0.8872', 'learning_rate': '1.745e-05', 'epoch': '0.9171'}             
{'loss': '0.4639', 'grad_norm': '0.724', 'learning_rate': '1.698e-05', 'epoch': '0.9194'}              
{'loss': '0.5651', 'grad_norm': '0.7337', 'learning_rate': '1.651e-05', 'epoch': '0.9217'}             
{'loss': '0.5548', 'grad_norm': '0.6828', 'learning_rate': '1.604e-05', 'epoch': '0.924'}              
{'loss': '0.5379', 'grad_norm': '0.889', 'learning_rate': '1.557e-05', 'epoch': '0.9263'}              
{'loss': '0.5248', 'grad_norm': '7.366', 'learning_rate': '1.509e-05', 'epoch': '0.9286'}              
{'loss': '0.5301', 'grad_norm': '0.7876', 'learning_rate': '1.462e-05', 'epoch': '0.9309'}             
{'loss': '0.6551', 'grad_norm': '0.8864', 'learning_rate': '1.415e-05', 'epoch': '0.9332'}             
{'loss': '0.6373', 'grad_norm': '1.096', 'learning_rate': '1.368e-05', 'epoch': '0.9355'}              
{'loss': '0.578', 'grad_norm': '0.7194', 'learning_rate': '1.321e-05', 'epoch': '0.9378'}              
{'loss': '0.6119', 'grad_norm': '0.6459', 'learning_rate': '1.274e-05', 'epoch': '0.9401'}             
{'loss': '0.5648', 'grad_norm': '0.6575', 'learning_rate': '1.226e-05', 'epoch': '0.9424'}             
{'loss': '0.5912', 'grad_norm': '0.6135', 'learning_rate': '1.179e-05', 'epoch': '0.9447'}             
{'loss': '0.5388', 'grad_norm': '0.6774', 'learning_rate': '1.132e-05', 'epoch': '0.947'}              
{'loss': '0.5374', 'grad_norm': '0.5862', 'learning_rate': '1.085e-05', 'epoch': '0.9493'}             
{'loss': '0.543', 'grad_norm': '0.7344', 'learning_rate': '1.038e-05', 'epoch': '0.9516'}              
{'loss': '0.5712', 'grad_norm': '2.951', 'learning_rate': '9.906e-06', 'epoch': '0.9539'}              
{'loss': '0.6042', 'grad_norm': '0.6013', 'learning_rate': '9.434e-06', 'epoch': '0.9562'}             
{'loss': '0.5557', 'grad_norm': '0.6044', 'learning_rate': '8.962e-06', 'epoch': '0.9585'}             
{'loss': '0.6842', 'grad_norm': '0.7757', 'learning_rate': '8.491e-06', 'epoch': '0.9608'}             
{'loss': '0.6073', 'grad_norm': '0.8176', 'learning_rate': '8.019e-06', 'epoch': '0.9631'}             
{'loss': '0.6584', 'grad_norm': '0.7175', 'learning_rate': '7.547e-06', 'epoch': '0.9654'}             
{'loss': '0.5009', 'grad_norm': '0.8671', 'learning_rate': '7.075e-06', 'epoch': '0.9677'}             
{'loss': '0.5135', 'grad_norm': '1.537', 'learning_rate': '6.604e-06', 'epoch': '0.97'}                
{'loss': '0.5471', 'grad_norm': '0.6181', 'learning_rate': '6.132e-06', 'epoch': '0.9724'}             
{'loss': '0.4938', 'grad_norm': '0.7135', 'learning_rate': '5.66e-06', 'epoch': '0.9747'}              
{'loss': '0.6193', 'grad_norm': '0.6272', 'learning_rate': '5.189e-06', 'epoch': '0.977'}              
{'loss': '0.5456', 'grad_norm': '0.6822', 'learning_rate': '4.717e-06', 'epoch': '0.9793'}             
{'loss': '0.5714', 'grad_norm': '0.6279', 'learning_rate': '4.245e-06', 'epoch': '0.9816'}             
{'loss': '0.6351', 'grad_norm': '0.9461', 'learning_rate': '3.774e-06', 'epoch': '0.9839'}             
{'loss': '0.5579', 'grad_norm': '2.173', 'learning_rate': '3.302e-06', 'epoch': '0.9862'}              
{'loss': '0.5422', 'grad_norm': '0.6888', 'learning_rate': '2.83e-06', 'epoch': '0.9885'}              
{'loss': '0.588', 'grad_norm': '0.6757', 'learning_rate': '2.358e-06', 'epoch': '0.9908'}              
{'loss': '0.547', 'grad_norm': '0.8139', 'learning_rate': '1.887e-06', 'epoch': '0.9931'}              
{'loss': '0.5368', 'grad_norm': '0.7084', 'learning_rate': '1.415e-06', 'epoch': '0.9954'}             
{'loss': '0.5015', 'grad_norm': '0.6998', 'learning_rate': '9.434e-07', 'epoch': '0.9977'}             
{'loss': '0.6', 'grad_norm': '0.8133', 'learning_rate': '4.717e-07', 'epoch': '1'}                     
{'train_runtime': '7536', 'train_samples_per_second': '0.23', 'train_steps_per_second': '0.058', 'train_loss': '0.7015', 'epoch': '1'}
100%|██████████████████████████████████████████████████████████████| 434/434 [2:05:35<00:00, 17.36s/it]

Training complete!
  Total steps: 434
  Final loss: 0.7015

Saving LoRA adapter to /workspace/output/gcse-tutor-gemma4-31b/lora-adapter...
Saving merged 16-bit model to /workspace/output/gcse-tutor-gemma4-31b/merged-16bit...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|██████████████████████████████████████████████████| 1/1 [00:00<00:00, 18.50it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files.../s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-31b/merged-16bit`: 100%|█| 
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-31b/merged-16bit`█| 
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|██████████████████████| 2/2 [00:00<00:00, 74235.47it/s]
Download complete: : 0.00B [00:48, ?B/s]s:   0%|                                 | 0/2 [00:00<?, ?it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████| 2/2 [07:47<00:00, 233.65s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-31b/merged-16bit`55s/it]
Exporting GGUF to /workspace/output/gcse-tutor-gemma4-31b/gguf...
Unsloth: Merging model weights to 16-bit format...
Found HuggingFace hub cache directory: /root/.cache/huggingface/hub
Fetching 1 files: 100%|█████████████████████████████████████████████████| 1/1 [00:00<00:00, 591.08it/s]
Download complete: : 0.00B [00:00, ?B/s]              Checking cache directory for required files.../s]
Unsloth: Copying 2 files from cache to `/workspace/output/gcse-tutor-gemma4-31b/gguf`: 100%|█| 2/2 [01:
Successfully copied all 2 files from cache to `/workspace/output/gcse-tutor-gemma4-31b/gguf`█| 2/2 [01:
Checking cache directory for required files...
Cache check failed: tokenizer.model not found in local cache.
Not all required files found in cache. Will proceed with downloading.
Unsloth: Preparing safetensor model files: 100%|██████████████████████| 2/2 [00:00<00:00, 64035.18it/s]
Download complete: : 0.00B [01:35, ?B/s]s:   0%|                                 | 0/2 [00:00<?, ?it/s]
Unsloth: Merging weights into 16bit: 100%|██████████████████████████████| 2/2 [07:55<00:00, 237.81s/it]
Unsloth: Merge process complete. Saved to `/workspace/output/gcse-tutor-gemma4-31b/gguf`00, 214.44s/it]
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
Unsloth: Initial conversion completed! Files: ['/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-00001-of-00002.gguf', '/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-00002-of-00002.gguf', '/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-mmproj.gguf']
Unsloth: [2] Converting GGUF bf16 into q4_k_m. This might take 10 minutes...
Unsloth: Model files cleanup...
Unsloth: All GGUF conversions completed successfully!
Generated files: ['/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.Q4_K_M.gguf', '/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-mmproj.gguf', '/workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-00002-of-00002.gguf']


Unsloth: example usage for Multimodal LLMs: /root/.unsloth/llama.cpp/llama-mtmd-cli -m /workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.Q4_K_M.gguf --mmproj /workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/gemma-4-31B-it.BF16-00002-of-00002.gguf
Unsloth: load image inside llama.cpp runner: /image test_image.jpg
Unsloth: Prompt model to describe the image
Unsloth: Saved Ollama Modelfile to /workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/Modelfile
Unsloth: convert model to ollama format by running - ollama create model_name -f /workspace/output/gcse-tutor-gemma4-31b/gguf_gguf/Modelfile
  Exported: q4_k_m

============================================================
All done! Next steps:
  1. Test with vLLM:  vllm serve /workspace/output/gcse-tutor-gemma4-31b/merged-16bit
  2. Or use GGUF:     ls /workspace/output/gcse-tutor-gemma4-31b/gguf/
  3. LoRA adapter:    /workspace/output/gcse-tutor-gemma4-31b/lora-adapter/
============================================================

root@15f5227647c4:/workspace# 
