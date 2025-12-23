"""Allow running the chat worker package with `python -m app`."""
from __future__ import annotations

import asyncio

from .main import main

if __name__ == "__main__":
    asyncio.run(main())
