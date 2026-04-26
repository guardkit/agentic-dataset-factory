mkdir -p ~/Models/gcse-tutor-gemma4-26b-moe

rsync -avP --partial \
  promaxgb10-41b1:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/gemma-4-26b-a4b-it.Q4_K_M.gguf \
  ~/Models/gcse-tutor-gemma4-26b-moe/

rsync -avP --partial \
  promaxgb10-41b1:~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/gguf_gguf/Modelfile \
  ~/Models/gcse-tutor-gemma4-26b-moe/

rsync -avhP \
  "/Users/richardwoollcott/Projects/appmilla_github/architecture_books/Eric Evans 2003 - Domain-Driven Design - Tackling Complexity in the Heart of Software.pdf" \
  "/Users/richardwoollcott/Projects/appmilla_github/architecture_books/Software_Architecture_The_Hard_Parts_Neal_Ford_OReilly_9781492086895.pdf" \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent-probe/sources/
