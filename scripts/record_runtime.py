"""Record versions actually imported for the completed experiment."""
import importlib.metadata
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    packages = ("chromadb", "sentence-transformers", "torch", "transformers", "numpy", "openai", "python-dotenv")
    result = {"python": platform.python_version(), "platform": platform.system(),
              "device": "cpu", "torch_threads": 4,
              "packages": {name: importlib.metadata.version(name) for name in packages},
              "command_note": "Day 6 venv with installed host SDK path appended; see ENVIRONMENT.md. Fresh setup uses requirements.txt."}
    result["code_sha256"] = {}
    import hashlib
    for folder in ("src", "scripts"):
        for path in sorted((ROOT / folder).glob("*.py")):
            result["code_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT / "results/runtime.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "code_sha256"}, indent=2))


if __name__ == "__main__":
    main()
