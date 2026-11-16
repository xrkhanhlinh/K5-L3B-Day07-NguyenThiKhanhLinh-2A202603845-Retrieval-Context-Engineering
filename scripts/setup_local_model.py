"""Download official Qwen GGUF and official llama.cpp CPU binary, with checksums."""
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Day7-local-lab"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download(url, path, expected_sha):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and digest(path) == expected_sha:
        print(f"Verified existing {path.name}", flush=True)
        return
    partial = path.with_suffix(path.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "Day7-local-lab"})
    count, last = 0, 0
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
            count += len(block)
            if count - last >= 64 * 1024 * 1024:
                print(f"{path.name}: {count // (1024 * 1024)} MiB", flush=True)
                last = count
    if digest(partial) != expected_sha:
        raise RuntimeError(f"Checksum mismatch: {path.name}")
    partial.replace(path)
    print(f"Verified {path.name}: {count} bytes", flush=True)


def main():
    prior_path = ROOT / "artifacts/local_model.json"
    if prior_path.exists():
        # Reproduction uses the recorded release and model, never a moving latest.
        prior = load(prior_path)
        archive = ROOT / ".runtime" / prior["runtime_url"].rsplit("/", 1)[1]
        download(prior["runtime_url"], archive, prior["runtime_archive_sha256"])
        destination = ROOT / ".runtime/llama"
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                if not (destination / member.filename).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe archive path")
            zipped.extractall(destination)
        download(prior["model_url"], ROOT / prior["model_path"], prior["model_sha256"])
        if digest(ROOT / prior["server_path"]) != prior["server_sha256"]:
            raise RuntimeError("Pinned server binary mismatch")
        print("Pinned model and runtime ready", flush=True)
        return
    pilot_path = ROOT / "artifacts/pilot_1_5b_model.json"
    if pilot_path.exists():
        pilot = load(pilot_path)
        release = {"tag_name": pilot["runtime_release"]}
        asset = {"name": pilot["runtime_url"].rsplit("/", 1)[1], "browser_download_url": pilot["runtime_url"],
                 "digest": "sha256:" + pilot["runtime_archive_sha256"]}
    else:
        releases = get_json("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10")
        release, asset = next((r, a) for r in releases for a in r["assets"]
                              if "win-cpu-x64" in a["name"] and a["name"].endswith(".zip"))
    if not asset.get("digest", "").startswith("sha256:"):
        raise RuntimeError("Official release asset has no SHA-256 digest")
    model_repo = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    filename = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    model = get_json(f"https://huggingface.co/api/models/{model_repo}?blobs=true")
    sibling = next(f for f in model["siblings"] if f["rfilename"] == filename)
    model_sha = sibling["lfs"]["sha256"]
    model_url = f"https://huggingface.co/{model_repo}/resolve/{model['sha']}/{filename}"
    archive = ROOT / ".runtime" / asset["name"]
    model_path = ROOT / ".local-model" / filename
    print(f"Runtime {release['tag_name']}, model {model_repo}, size {sibling['lfs']['size']}", flush=True)
    download(asset["browser_download_url"], archive, asset["digest"].split(":", 1)[1])
    destination = ROOT / ".runtime/llama"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe path in official archive")
        zipped.extractall(destination)
    download(model_url, model_path, model_sha)
    servers = list(destination.rglob("llama-server.exe"))
    if len(servers) != 1:
        raise RuntimeError("Expected exactly one llama-server.exe")
    save(ROOT / "artifacts/local_model.json", {
        "downloaded_at_utc": now(), "model_repo": model_repo, "model_revision": model["sha"],
        "model_url": model_url, "model_sha256": model_sha, "model_bytes": sibling["lfs"]["size"],
        "model_path": str(model_path.relative_to(ROOT)), "license": "Apache-2.0 per official Qwen model card",
        "runtime_release": release["tag_name"], "runtime_url": asset["browser_download_url"],
        "runtime_archive_sha256": asset["digest"].split(":", 1)[1],
        "server_path": str(servers[0].relative_to(ROOT)), "server_sha256": digest(servers[0]),
        "docs": ["https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF", "https://github.com/ggml-org/llama.cpp/tree/master/tools/server"],
    })


if __name__ == "__main__":
    main()
