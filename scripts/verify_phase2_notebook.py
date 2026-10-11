"""Execute Phase 2 in a fresh kernel and persist outputs without volatile metadata."""

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

path = ROOT / "notebooks/02_survival_analysis.ipynb"
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
    raise RuntimeError(f"Phase 2 notebook produced {len(errors)} error output(s)")
for cell in executed.cells:
    cell.metadata.pop("execution", None)
nbformat.write(executed, path)
print(f"Executed {sum(cell.cell_type == 'code' for cell in executed.cells)} Phase 2 code cells")
