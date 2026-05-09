mkdir -p ~/Projects/agentic-dataset-factory-runs && \
rsync -avh --progress \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output_backup_post_architect-agent_20260502-072937 \
  richardwoollcott@promaxgb10-41b1:/home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/output_backup_pre_architect_20260429-154246 \
  ~/Projects/agentic-dataset-factory-runs/
