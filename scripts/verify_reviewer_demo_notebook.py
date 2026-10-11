"""Execute the synthetic reviewer notebook in a fresh kernel and save its outputs."""

import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
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

path = ROOT / "notebooks/00_synthetic_reviewer_demo.ipynb"
notebook = nbformat.read(path, as_version=4)
executed = NotebookClient(
    notebook, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}
).execute()
errors = [
    output
    for cell in executed.cells
    if cell.cell_type == "code"
    for output in cell.get("outputs", [])
    if output.output_type == "error"
]
if errors:
    raise RuntimeError(f"Reviewer notebook produced {len(errors)} error output(s)")
for cell in executed.cells:
    cell.metadata.pop("execution", None)
nbformat.write(executed, path)
text = path.read_text(encoding="utf-8")
if "ACC_" in text:
    raise RuntimeError("Reviewer notebook output contains a source-style account identifier")
print(f"Executed {sum(c.cell_type == 'code' for c in executed.cells)} reviewer code cells: {path}")
