"""Download only the exact recorded Day 6 encoder files and verify every hash."""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load


if __name__ == "__main__":
    info = load(ROOT / "data/day6/run_info.json")
    for relative, expected in info["model_files"].items():
        normalized = relative.replace("\\", "/")
        if "/snapshots/" not in normalized:
            continue
        _, suffix = normalized.split("/snapshots/", 1)
        revision, filename = suffix.split("/", 1)
        destination = ROOT / ".model_cache" / Path(normalized)
        if destination.exists() and digest(destination) == expected:
            print("Verified cached", filename)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/Qdrant/all-MiniLM-L6-v2-onnx/resolve/{revision}/{filename}"
        with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        if digest(destination) != expected:
            raise RuntimeError(f"Downloaded encoder file hash mismatch: {filename}")
        print("Downloaded and verified", filename)
