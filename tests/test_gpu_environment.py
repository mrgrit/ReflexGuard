"""GPU guard regression; successful arithmetic is checked on the Thor device."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_gpu_check_rejects_cpu_only_before_allocating():
    path = Path(__file__).resolve().parents[1] / "scripts/check_gpu.py"
    spec = importlib.util.spec_from_file_location("check_gpu", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    unavailable = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        module.check_gpu(unavailable)
