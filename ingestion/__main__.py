"""Stub entry point for ``python -m ingestion.ingest``.

Full CLI implementation is deferred to TASK-ING-006.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Print usage instructions and exit."""
    print(
        "Usage: python -m ingestion.ingest --domain <domain-name>\n"
        "\n"
        "This command is not yet implemented.\n"
        "See TASK-ING-006 for the full CLI implementation."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
