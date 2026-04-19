mkdir -p ~/Models/gcse-tutor-gemma4-26b-moe

rsync -avP --partial \
  promaxgb10-41b1:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf \
  ~/Models/gcse-tutor-gemma4-26b-moe/

rsync -avP --partial \
  promaxgb10-41b1:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/Modelfile \
  ~/Models/gcse-tutor-gemma4-26b-moe/
