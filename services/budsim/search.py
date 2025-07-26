from os import path as osp
from os import walk

import joblib


base_path = "./cache/pretrained_models"
for root, dirs, files in walk(base_path):
    for file in files:
        if not file.endswith(".pkl"):
            continue
        try:
            joblib.load(osp.join(root, file))
            print(f"Loaded {file}")
        except Exception as e:
            print(f"Error loading {file}: {e}")
