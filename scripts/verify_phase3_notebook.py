"""Execute the Phase 3 aggregate notebook in a fresh kernel."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

path = ROOT / "notebooks/03_monte_carlo_npv.ipynb"
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
    raise RuntimeError(f"Phase 3 notebook produced {len(errors)} error output(s)")
for cell in executed.cells:
    cell.metadata.pop("execution", None)
nbformat.write(executed, path)
figures = list((ROOT / "outputs/phase3/figures").glob("*.png"))
if len(figures) != 6:
    raise RuntimeError(f"Expected six Phase 3 figures, found {len(figures)}")
manifest_path = ROOT / "outputs/phase3/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["notebook"] = {
    "path": "notebooks/03_monte_carlo_npv.ipynb",
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "classification": "AGGREGATE_ONLY",
}
manifest["figures"] = [
    {
        "path": f"outputs/phase3/figures/{figure.name}",
        "sha256": hashlib.sha256(figure.read_bytes()).hexdigest(),
        "classification": "AGGREGATE_ONLY",
    }
    for figure in sorted(figures)
]
manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
)
print(f"Executed {sum(cell.cell_type == 'code' for cell in executed.cells)} Phase 3 code cells")
