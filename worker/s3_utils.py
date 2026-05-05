import os
import shutil
from pathlib import Path


def setup_job_workspace(job_id: str):
    """Creates the folder structure for a new job."""
    base_path = Path(f"/uploads/{job_id}")
    folders = ["original", "denoise", "separated", "transcribe"]

    for folder in folders:
        (base_path / folder).mkdir(parents=True, exist_ok=True)

    return base_path


def cleanup_job_workspace(job_id: str):
    """Nukes the entire job folder to free up disk space."""
    path = f"/uploads/{job_id}"
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"🧹 [CLEANUP] Deleted local workspace for {job_id}")
