import subprocess
import sys
from pathlib import Path


client = Path(__file__).parent / "ai" / "ollama_client.py"
result = subprocess.run(
    [sys.executable, str(client)],
    capture_output=True,
    text=True,
    check=True,
)

print(result.stdout, end="")
