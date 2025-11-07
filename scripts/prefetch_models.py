#!/usr/bin/env python3
"""Prefetch a list of Hugging Face model repos to the cache.

This script is intended to be copied into the Docker image and executed
during build when PRELOAD_MODELS=1. It will attempt to download the
repos listed in the `repos` variable using huggingface_hub.snapshot_download.
"""
import os
from huggingface_hub import snapshot_download

def main():
    repos = [
        "all-MiniLM-L6-v2",
        "bert-large-uncased-whole-word-masking-finetuned-squad",
    ]

    token = os.environ.get("HUGGINGFACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")
    if token:
        os.environ["HUGGINGFACE_HUB_TOKEN"] = token

    for r in repos:
        try:
            print(f"Prefetching {r}...")
            snapshot_download(repo_id=r, resume_download=True)
            print(f"Done: {r}")
        except Exception as e:
            print("prefetch failed for", r, e)

if __name__ == "__main__":
    main()
