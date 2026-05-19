"""Exit with status 1 if any lookup JSON under DIR still has PUA in string values."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent   # scripts/pua/
_SCRIPTS = _HERE.parent                    # scripts/
_COMMON = _SCRIPTS / "font_lookup_common"
for _d in (_COMMON, _HERE):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from inventory import verify_dir  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dir", type=Path, nargs="+", help="One or more lookup directories to scan")
    args = p.parse_args(argv)
    bad = 0
    for d in args.dir:
        n, msgs = verify_dir(d.expanduser().resolve())
        bad += n
        for m in msgs:
            print(m)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
