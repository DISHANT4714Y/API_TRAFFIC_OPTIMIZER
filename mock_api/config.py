"""
Configuration settings for the Mock External API.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Artificial delay in milliseconds (default: 500 ms)
MOCK_API_DELAY_MS: int = int(os.getenv("MOCK_API_DELAY_MS", "500"))

# Simulated failure rate in percentage [0-100] (default: 0, no failure)
MOCK_API_FAILURE_RATE: float = float(os.getenv("MOCK_API_FAILURE_RATE", "0"))
