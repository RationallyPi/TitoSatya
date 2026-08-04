# pip install requests
import json
import os
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv()

# ---------- CONFIG ----------
JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
TOKEN = os.environ.get("PADDLEOCR_TOKEN")
MODEL = "PaddleOCR-VL-1.6"

INPUT_FOLDER = Path("Papers")
OUTPUT_FOLDER = Path("Parsed_Markdown")
CHECKPOINT_FILE = Path("checkpoint.json")

OUTPUT_FOLDER.mkdir(exist_ok=True)

POLL_INTERVAL = 5  # seconds between job status checks

OPTIONAL_PAYLOAD = {
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useChartRecognition": False,
}

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
}


# ---------- CHECKPOINT HELPERS ----------
def load_checkpoint():
    """Returns {'date_folder': str, 'file': str} of the last successfully
    processed file, or None if no checkpoint exists yet."""
    if CHECKPOINT_FILE.exists():
        try:
            data = json.loads(CHECKPOINT_FILE.read_text())
            print(f">>> Resuming after checkpoint: {data}")
            return data
        except (json.JSONDecodeError, KeyError):
            print(">>> Checkpoint file corrupted, ignoring.")
            return None
    return None


def save_checkpoint(date_folder_name: str, filename: str):
    CHECKPOINT_FILE.write_text(json.dumps({
        "date_folder": date_folder_name,
        "file": filename
    }))


# ---------- API HELPERS ----------
def submit_job(file_path: Path) -> str:
    """Submits a local file to the OCR API and returns the jobId."""
    data = {
        "model": MODEL,
        "optionalPayload": json.dumps(OPTIONAL_PAYLOAD),
    }
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(JOB_URL, headers=HEADERS, data=data, files=files)

    if response.status_code != 200:
        raise RuntimeError(f"Job submission failed ({response.status_code}): {response.text}")

    job_id = response.json()["data"]["jobId"]
    print(f"  Job submitted. job id: {job_id}")
    return job_id


def poll_job(job_id: str) -> str:
    """Polls until the job is done, returns the resultUrl jsonUrl."""
    while True:
        job_result_response = requests.get(f"{JOB_URL}/{job_id}", headers=HEADERS)
        if job_result_response.status_code != 200:
            raise RuntimeError(f"Polling failed ({job_result_response.status_code}): {job_result_response.text}")

        data = job_result_response.json()["data"]
        state = data["state"]

        if state == "pending":
            print("  Status: pending")
        elif state == "running":
            try:
                total_pages = data["extractProgress"]["totalPages"]
                extracted_pages = data["extractProgress"]["extractedPages"]
                print(f"  Status: running ({extracted_pages}/{total_pages} pages)")
            except KeyError:
                print("  Status: running...")
        elif state == "done":
            extracted_pages = data["extractProgress"]["extractedPages"]
            print(f"  Status: done ({extracted_pages} pages extracted)")
            return data["resultUrl"]["jsonUrl"]
        elif state == "failed":
            error_msg = data.get("errorMsg", "unknown error")
            raise RuntimeError(f"Job failed: {error_msg}")

        time.sleep(POLL_INTERVAL)


def save_results(jsonl_url: str, filepath: Path, output_subfolder: Path):
    """Downloads the JSONL result and saves markdown into output_subfolder,
    naming outputs after the original filename."""
    jsonl_response = requests.get(jsonl_url)
    jsonl_response.raise_for_status()
    lines = jsonl_response.text.strip().split("\n")

    # First, collect all results across all lines so we know if this file
    # produced one page or several (e.g. a multi-page PDF).
    all_results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        all_results.extend(result["layoutParsingResults"])

    multi_page = len(all_results) > 1

    for i, res in enumerate(all_results):
        if multi_page:
            stem = f"{filepath.stem}_p{i + 1}"
        else:
            stem = filepath.stem

        md_filename = output_subfolder / f"{stem}.md"
        md_filename.write_text(res["markdown"]["text"], encoding="utf-8")
        print(f"  Saved: {md_filename}")
def process_file(filepath: Path, output_subfolder: Path):
    """Submits, polls, and saves results for a single file."""
    print(f"Processing file: {filepath}")
    job_id = submit_job(filepath)
    jsonl_url = poll_job(job_id)
    if jsonl_url:
        save_results(jsonl_url, filepath, output_subfolder)


# ---------- MAIN ----------
def main():
    if TOKEN in (None, "", "<your-token-here>"):
        print("ERROR: No API token set. Set PADDLEOCR_TOKEN env var or edit TOKEN in the script.")
        sys.exit(1)

    date_folders = sorted(f for f in INPUT_FOLDER.iterdir() if f.is_dir())
    if not date_folders:
        print(f"No date folders found in {INPUT_FOLDER.resolve()}")
        return

    checkpoint = load_checkpoint()
    resuming = checkpoint is not None  # flips off once we pass the checkpoint

    for date_folder in date_folders:
        files = sorted(date_folder.glob("*"))

        output_subfolder = OUTPUT_FOLDER / date_folder.name
        output_subfolder.mkdir(parents=True, exist_ok=True)

        for i, filepath in enumerate(files):
            target_path = output_subfolder / f"{filepath.stem}.md"

            # --- resume logic: skip everything up to and including checkpoint ---
            if resuming:
                if date_folder.name == checkpoint["date_folder"] and filepath.name == checkpoint["file"]:
                    print(f"Reached checkpoint at {filepath.name}, resuming from next file.")
                    resuming = False
                else:
                    print(f"Skipping (before checkpoint): {date_folder.name}/{filepath.name}")
                continue

            # --- skip if output already exists (belt-and-suspenders) ---
            if target_path.exists():
                print(f"Already parsed, skipping: {target_path}")
                continue

            print(f"[{i + 1}/{len(files)}] {date_folder.name}/{filepath.name}")

            try:
                process_file(filepath, output_subfolder)
                save_checkpoint(date_folder.name, filepath.name)
            except Exception as e:
                print(f"  ERROR processing {filepath.name}: {e}")
                print("  Skipping this file and continuing with the next one.")
                # Note: checkpoint is NOT advanced here, so a failed file
                # will be retried on the next run instead of silently skipped.
                continue

        print("Finished processing all files in folder:", date_folder.name)


if __name__ == "__main__":
    main()