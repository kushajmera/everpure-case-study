"""Execute the aggregate-only Phase 4 notebook in a fresh kernel."""

import argparse
import hashlib
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description="Verify the Phase 4 notebook without rewriting it")
parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
args = parser.parse_args()
ROOT = Path(args.repo_root).resolve()
runtime = ROOT / ".runtime"
for name in ("ipython", "jupyter_data", "jupyter_runtime"):
    (runtime / name).mkdir(parents=True, exist_ok=True)
os.environ["IPYTHONDIR"] = str(runtime / "ipython")
os.environ["JUPYTER_DATA_DIR"] = str(runtime / "jupyter_data")
os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime / "jupyter_runtime")
if os.environ.get("EVERPURE_SANDBOX_JUPYTER") == "1":
    os.environ["JUPYTER_ALLOW_INSECURE_WRITES"] = "1"

import nbformat  # noqa: E402
from nbclient import NotebookClient  # noqa: E402

from everpure_case.phase4_pipeline import validate_phase4_artifacts  # noqa: E402

path = ROOT / "notebooks/04_gtm_routing.ipynb"
before = hashlib.sha256(path.read_bytes()).hexdigest()
validate_phase4_artifacts(ROOT)
notebook = nbformat.read(path, as_version=4)
executed = NotebookClient(
    notebook, timeout=180, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}
).execute()
errors = [
    output
    for cell in executed.cells
    if cell.cell_type == "code"
    for output in cell.get("outputs", [])
    if output.output_type == "error"
]
if errors:
    raise RuntimeError(f"Phase 4 notebook produced {len(errors)} error outputs")
if hashlib.sha256(path.read_bytes()).hexdigest() != before:
    raise RuntimeError("Notebook verifier unexpectedly modified the notebook")
validate_phase4_artifacts(ROOT)
outputs = [cell.get("outputs", []) for cell in executed.cells if cell.cell_type == "code"]
output_sha256 = hashlib.sha256(
    json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
print(f"Executed {len(outputs)} Phase 4 cells; output_sha256={output_sha256}")
