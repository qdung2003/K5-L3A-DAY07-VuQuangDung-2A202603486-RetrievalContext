"""Resolve independent experiment folders and portable selection artifacts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def results_directory(value=None):
    return Path(value).resolve() if value is not None else ROOT / "results"


def artifact_path(results_root, relative):
    relative = relative.replace("\\", "/")
    relative = relative.removeprefix("results/")
    root = Path(results_root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Artifact path must stay inside the experiment directory")
    return path
