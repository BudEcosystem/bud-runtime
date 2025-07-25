import glob
import json
import os

import pandas as pd


def convert_and_save_json(folder_path: str, ext: str, key_mapping: dict[str, str]):
    """Read all files with the given extension in the specified folder, extracts relevant fields, converts them to a common JSON format, and saves them as JSON files before deleting the originals.

    Args:
        folder_path (str): Path to the folder containing the files.
        ext (str): File extension to process (e.g., 'parquet', 'json', 'jsonl').
    """
    file_paths = glob.glob(os.path.join(folder_path, f"*.{ext}"))

    for file_path in file_paths:
        output_path = file_path.replace(f".{ext}", ".json")
        formatted_data = []

        if ext == "parquet":
            df = pd.read_parquet(file_path)
        elif ext == "json":
            df = pd.read_json(file_path)
        elif ext == "jsonl":
            df = pd.read_json(file_path, lines=True)
        else:
            print(f"Skipping unsupported file type: {file_path}")
            continue

        for _, row in df.iterrows():
            formatted_data.append(
                {
                    "id": row.get(key_mapping["id"], ""),
                    "prompt": row.get(key_mapping["prompt"], ""),
                    "response": row.get(key_mapping["response"], ""),
                }
            )

        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(formatted_data, json_file, ensure_ascii=False, indent=4)

        os.remove(file_path)
        print(f"Processed and removed: {file_path}")


def handle_sharegpt(folder_path: str, ext: str = "json"):
    """To handle ShareGPT dataset."""
    file_paths = glob.glob(os.path.join(folder_path, f"*.{ext}"))

    for file_path in file_paths:
        output_path = file_path.replace(f".{ext}", ".json")
        formatted_data = []

        df = pd.read_json(file_path)

        for _, row in df.iterrows():
            if "conversations" in row and len(row["conversations"]) >= 2:
                formatted_data.append(
                    {
                        "id": row["id"],
                        "prompt": row["conversations"][0]["value"],
                        "response": row["conversations"][1]["value"],
                    }
                )

        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(formatted_data, json_file, ensure_ascii=False, indent=4)

        # os.remove(file_path)
        print(f"Processed and removed: {file_path}")


def handle_thudm_longbench(folder_path: str, ext: str = "jsonl"):
    """To handle THUDM LongBench dataset."""
    file_paths = glob.glob(os.path.join(folder_path, f"*.{ext}"))

    for file_path in file_paths:
        output_path = file_path.replace(f".{ext}", ".json")
        formatted_data = []
        df = pd.read_json(file_path, lines=True)
        for _, row in df.iterrows():
            formatted_data.append(
                {
                    "id": row.get("_id", ""),
                    "prompt": row.get("context", "") + row.get("input", ""),
                    "response": row.get("answers", "")[0],
                }
            )
        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(formatted_data, json_file, ensure_ascii=False, indent=4)

        os.remove(file_path)
        print(f"Processed and removed: {file_path}")


if __name__ == "__main__":
    folder_path = "/datadisk/sonali/datasets/open-r1-OpenR1-Math-220k"
    ext = "parquet"
    key_mapping = {"id": "uuid", "prompt": "problem", "response": "solution"}
    # convert_and_save_json(folder_path, ext, key_mapping)
    # folder_path = '/datadisk/sonali/datasets/ShareGPT'
    # handle_sharegpt(folder_path)
    # folder_path = '/datadisk/sonali/datasets/THUDM-LongBench'
    # handle_thudm_longbench(folder_path)
