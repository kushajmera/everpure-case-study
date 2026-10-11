import shutil
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def isolated_repo():
    """Copy only required inputs so adversarial tests never rewrite approved outputs."""
    source_root = Path(__file__).resolve().parents[1]
    scratch = source_root / "tests" / f"_scratch_{uuid.uuid4().hex}"
    scratch.mkdir()
    try:
        shutil.copytree(source_root / "sql", scratch / "sql")
        (scratch / "data/raw").mkdir(parents=True)
        shutil.copyfile(
            source_root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv",
            scratch / "data/raw/Case_Study_1_Install_Base_Reactivation.csv",
        )
        yield scratch
    finally:
        shutil.rmtree(scratch)
