"""Entry point for ``python -m ingestion``.

Delegates to ``ingestion.ingest.main()`` which wraps the CLI with argparse.
"""

from __future__ import annotations

from ingestion.ingest import main

if __name__ == "__main__":
    main()
