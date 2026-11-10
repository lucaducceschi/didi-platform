#!/bin/bash
#SBATCH --job-name=didi_stanza
#SBATCH --account=eurac-commul
#SBATCH --partition=gpu-low
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=/data/users/luducceschi_eurac/didi_transfer/stanza_%j.log
#SBATCH --error=/data/users/luducceschi_eurac/didi_transfer/stanza_%j.err

echo "=== DIDI Platform Stanza GPU Job Started ==="
echo "Node: $(hostname)"
echo "Date: $(date)"

cd /data/users/luducceschi_eurac/didi_transfer

PYTHON="/data/users/luducceschi_eurac/envs/stanza/bin/python"

$PYTHON -c "import torch; print('CUDA available in job:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

$PYTHON cluster_stanza_gpu.py \
    --input articles_to_annotate.jsonl.gz \
    --output didi_words_cluster.db \
    --model-dir /data/users/luducceschi_eurac/stanza \
    --batch-size 32

echo "=== DIDI Platform Stanza GPU Job Finished ==="
echo "Date: $(date)"

