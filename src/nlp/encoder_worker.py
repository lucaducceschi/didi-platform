#!/usr/bin/env python3
"""
Lightweight Persistent Query Encoder Worker for DIDI Hybrid Search.
Keeps MiniLM model in memory to eliminate cold-start import overhead.
Listens on local Unix domain socket /tmp/didi_encoder.sock.
Average query latency: < 15ms.
"""

import json
import os
import socket
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

SOCKET_PATH = "/tmp/didi_encoder.sock"
MODEL_SNAPSHOT = Path.home() / ".cache" / "huggingface" / "hub" / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2" / "snapshots" / "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


def run_worker():
    if os.path.exists(SOCKET_PATH):
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

    print(f"Loading MiniLM model into memory from: {MODEL_SNAPSHOT}")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_SNAPSHOT)
    model = AutoModel.from_pretrained(MODEL_SNAPSHOT)
    model.eval()
    print(f"Model ready in {time.time() - t0:.2f}s!")

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)
    print(f"Query Encoder listening on {SOCKET_PATH}...")

    while True:
        try:
            conn, _ = server.accept()
            data = conn.recv(4096).decode("utf-8").strip()
            if not data:
                conn.close()
                continue

            # Process query
            inputs = tokenizer([data], return_tensors="pt", truncation=True, max_length=128)
            with torch.no_grad():
                out = model(**inputs)
                mask = inputs["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
                vec = torch.sum(out.last_hidden_state * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)
                norm = torch.nn.functional.normalize(vec, p=2, dim=1)
                vec_list = norm[0].tolist()

            response = json.dumps(vec_list) + "\n"
            conn.sendall(response.encode("utf-8"))
            conn.close()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error handling request: {e}", file=sys.stderr)

    server.close()
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)


if __name__ == "__main__":
    run_worker()
