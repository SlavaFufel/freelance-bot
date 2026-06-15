"""Гарантирует, что пакет `bot` импортируется при запуске pytest из любого места."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
