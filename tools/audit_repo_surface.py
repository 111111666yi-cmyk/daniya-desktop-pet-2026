from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    checker = Path(__file__).with_name("check_public_surface.py")
    namespace = runpy.run_path(str(checker))
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
