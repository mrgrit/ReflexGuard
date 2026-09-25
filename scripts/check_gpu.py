"""Small deterministic CUDA checks; this is not a brain-model benchmark."""
import importlib.metadata
import json
import platform
import time


def check_gpu(torch):
    """Reject CPU-only environments and verify dense/sparse GPU arithmetic."""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    torch.set_num_threads(2)
    device = torch.device("cuda:0")
    cpu = torch.arange(64, dtype=torch.float32).reshape(8, 8) / 64
    gpu = cpu.to(device)
    result = gpu @ gpu.T
    if result.cpu().numpy().shape != (8, 8):
        raise RuntimeError("NumPy bridge mismatch")
    if not torch.allclose(result.cpu(), cpu @ cpu.T, atol=1e-5, rtol=1e-5):
        raise RuntimeError("CUDA dense arithmetic mismatch")
    indices = torch.tensor([[0, 1, 2, 2], [1, 2, 0, 1]], device=device)
    weights = torch.tensor([2., -1., 3., 4.], device=device)
    matrix = torch.sparse_coo_tensor(indices, weights, (3, 3)).coalesce()
    vector = torch.tensor([[1.], [2.], [3.]], device=device)
    sparse = torch.sparse.mm(matrix, vector)
    expected = torch.tensor([[4.], [-3.], [11.]])
    if not torch.allclose(sparse.cpu(), expected):
        raise RuntimeError("CUDA sparse arithmetic mismatch")
    torch.cuda.synchronize()
    started = time.perf_counter()
    for _ in range(20):
        torch.sparse.mm(matrix, vector)
    torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - started) * 1000 / 20
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    return {
        "status": "ok",
        "scope": "environment_smoke_only_not_brain_model",
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "pytorch": str(torch.__version__),
        "pytorch_cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "cuda_memory_free_bytes": free_bytes,
        "cuda_memory_total_bytes": total_bytes,
        "dense_arithmetic": "passed",
        "sparse_arithmetic": "passed",
        "tiny_sparse_mean_ms": elapsed_ms,
    }


def main():
    import torch

    report = check_gpu(torch)
    report["bundled_packages"] = {}
    for package in ("numpy", "pyarrow", "safetensors", "cryptography", "fastapi", "uvicorn", "httpx", "pydantic"):
        try:
            report["bundled_packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["bundled_packages"][package] = None
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
