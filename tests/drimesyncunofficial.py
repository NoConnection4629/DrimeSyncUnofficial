import os
import sys
import tempfile
from pathlib import Path
import pytest
def run_tests():
    project_path = Path(__file__).parent.parent
    os.chdir(project_path)
    args = sys.argv[1:]
    if len(args) == 0:
        args = ["tests"]
    returncode = pytest.main(
        [
            "-vv",
            "--color=no",
            "-o",
            f"cache_dir={tempfile.gettempdir()}/.pytest_cache",
        ] + args
    )
    print(f">>>>>>>>>> EXIT {returncode} <<<<<<<<<<")
if __name__ == "__main__":
    run_tests()