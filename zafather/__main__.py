"""UZ: `python -m zafather` kirish nuqtasi. RU: Точка входа `python -m zafather`.
EN: The `python -m zafather` entry point.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
