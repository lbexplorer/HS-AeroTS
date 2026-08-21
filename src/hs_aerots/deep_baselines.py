"""P5 CATCH adaptation and transparent GCAD-style causal-deviation ablation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.linear_model import Ridge

from .baseline import evaluate_scores


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


class RawWindowStore:
    def __init__(self, feature_dir: Path, group_dictionary: Path, window_size: int):
        table = pd.read_csv(group_dictionary)
        self.paths = dict(zip(table.group.astype(int), table.aligned_path.map(Path)))
        self.feature_dir, self.window_size = feature_dir, window_size

    def metadata(self, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (np.load(self.feature_dir / f"group_{split}.npy", mmap_mode="r"),
                np.load(self.feature_dir / f"start_{split}.npy", mmap_mode="r"),
                np.load(self.feature_dir / f"y_{split}.npy", mmap_mode="r"))

    def batches(self, split: str, indices: np.ndarray, batch_size: int, mean: np.ndarray, std: np.ndarray,
                channel_groups: list[np.ndarray] | None = None) -> Iterator[np.ndarray]:
        groups, starts, _ = self.metadata(split)
        for lo in range(0, len(indices), batch_size):
            chosen = indices[lo:lo + batch_size]
            out = np.empty((len(chosen), self.window_size, len(mean)), dtype=np.float32)
            for group in np.unique(groups[chosen]):
                local = np.flatnonzero(groups[chosen] == group)
                with np.load(self.paths[int(group)], allow_pickle=False) as shard:
                    x = shard["x"]
                    for pos in local:
                        start = int(starts[chosen[pos]])
                        out[pos] = x[start:start + self.window_size]
            out = (out - mean) / std
            if channel_groups is not None:
                out = np.stack([out[:, :, group].mean(axis=2) for group in channel_groups], axis=2)
            yield out


def _load_catch_model(repo: Path):
    """Load the official model without importing the benchmark's unrelated baselines."""
    package_paths = {
        "ts_benchmark": repo / "ts_benchmark",
        "ts_benchmark.baselines": repo / "ts_benchmark/baselines",
        "ts_benchmark.baselines.catch": repo / "ts_benchmark/baselines/catch",
        "ts_benchmark.baselines.catch.models": repo / "ts_benchmark/baselines/catch/models",
        "ts_benchmark.baselines.catch.layers": repo / "ts_benchmark/baselines/catch/layers",
    }
    for name, path in package_paths.items():
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            sys.modules[name] = module
    name = "ts_benchmark.baselines.catch.models.CATCH_model"
    spec = importlib.util.spec_from_file_location(name, repo / "ts_benchmark/baselines/catch/models/CATCH_model.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.CATCHModel


def _catch_config(raw: dict[str, Any], channels: int, window: int) -> SimpleNamespace:
    return SimpleNamespace(c_in=channels, affine=0, subtract_last=0, patch_size=raw["patch_size"],
                           patch_stride=raw["patch_stride"], seq_len=window, cf_dim=raw["cf_dim"],
                           e_layers=raw["e_layers"], n_heads=raw["n_heads"], d_ff=raw["d_ff"],
                           d_model=raw["d_model"], head_dim=raw["head_dim"], dropout=0.2,
                           regular_lambda=0.5, temperature=0.07, individual=0, head_dropout=0.1)


def _score_catch(model, store, split, mean, std, batch_size, device, channel_groups,
                 indices: np.ndarray | None = None) -> np.ndarray:
    groups, _, _ = store.metadata(split)
    indices = np.arange(len(groups)) if indices is None else np.asarray(indices)
    scores = []
    model.eval()
    with torch.no_grad():
        for batch in store.batches(split, indices, batch_size, mean, std, channel_groups):
            x = torch.from_numpy(batch).to(device)
            output, _, _ = model(x)
            temporal = (x - output).square().mean(dim=(1, 2))
            frequency = (torch.fft.fft(x, dim=1) - torch.fft.fft(output, dim=1)).abs().mean(dim=(1, 2))
            scores.append((temporal + 0.05 * frequency).cpu().numpy())
    return np.concatenate(scores)


def run_catch(config: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    paths, raw = config["paths"], config["catch"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"]); report_dir.mkdir(parents=True, exist_ok=True)
    store = RawWindowStore(feature_dir, _resolve(root, paths["group_dictionary"]), int(config["data"]["window_size"]))
    mean = np.load(feature_dir / "scaler_mean.npy").astype(np.float32)
    std = np.load(feature_dir / "scaler_std.npy").astype(np.float32)
    CATCHModel = _load_catch_model(_resolve(root, paths["catch_repo"]))
    channel_groups = None
    catch_channels = len(mean)
    if raw.get("topic_aggregate"):
        channels = [line.strip() for line in _resolve(root, paths["channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
        topics = list(dict.fromkeys(channel.split(".", 1)[0] for channel in channels))
        channel_groups = [np.asarray([i for i, channel in enumerate(channels) if channel.split(".", 1)[0] == topic]) for topic in topics]
        catch_channels = len(channel_groups)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, _, y_train = store.metadata("train"); _, _, y_val = store.metadata("validation")
    rows = []
    for seed in raw["seeds"]:
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
        if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
        rng = np.random.default_rng(seed)
        train_idx = np.flatnonzero(y_train == 0)
        val_idx = np.flatnonzero(y_val == 0)
        train_idx = np.sort(rng.choice(train_idx, min(len(train_idx), raw["max_normal_train_windows"]), replace=False))
        val_idx = np.sort(rng.choice(val_idx, min(len(val_idx), raw["max_normal_validation_windows"]), replace=False))
        model = CATCHModel(_catch_config(raw, catch_channels, int(config["data"]["window_size"]))).to(device)
        main = [p for n, p in model.named_parameters() if "mask_generator" not in n]
        optimizer = torch.optim.Adam(main, lr=float(raw["learning_rate"]))
        mask_optimizer = torch.optim.Adam(model.mask_generator.parameters(), lr=float(raw["mask_learning_rate"]))
        best, best_state = float("inf"), None
        for epoch in range(int(raw["epochs"])):
            model.train(); losses = []
            shuffled = rng.permutation(train_idx)
            for batch in store.batches("train", shuffled, int(raw["batch_size"]), mean, std, channel_groups):
                x = torch.from_numpy(batch).to(device)
                optimizer.zero_grad(); mask_optimizer.zero_grad()
                output, complex_output, dc = model(x)
                norm = model.revin_layer(x, "transform")
                aux = (complex_output - torch.fft.fft(norm, dim=1)).abs().mean()
                loss = (output - x).square().mean() + float(raw["dc_lambda"]) * dc + float(raw["auxi_lambda"]) * aux
                loss.backward(); optimizer.step(); mask_optimizer.step(); losses.append(float(loss.detach()))
            validation = _score_catch(model, store, "validation", mean, std, int(raw["evaluation_batch_size"]), device, channel_groups, val_idx).mean()
            if validation < best:
                best = float(validation); best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            print(f"CATCH seed={seed} epoch={epoch + 1} train={np.mean(losses):.6f} val_normal={validation:.6f}", flush=True)
        model.load_state_dict(best_state)
        val_scores = _score_catch(model, store, "validation", mean, std, int(raw["evaluation_batch_size"]), device, channel_groups)
        test_scores = _score_catch(model, store, "test", mean, std, int(raw["evaluation_batch_size"]), device, channel_groups)
        g_val, _, y_val = store.metadata("validation"); g_test, _, y_test = store.metadata("test")
        val_metrics = evaluate_scores(y_val, val_scores, g_val)
        metrics = evaluate_scores(y_test, test_scores, g_test, val_metrics["threshold"])
        row = {"method": "CATCH-official-model-adaptation", "seed": seed, "train_sample": len(train_idx),
               "input_channels": catch_channels, "topic_aggregation": bool(channel_groups),
               "best_normal_validation_loss": best, **metrics}
        rows.append(row); torch.save(best_state, report_dir / f"catch_seed{seed}.pt")
        print(json.dumps(row), flush=True)
    pd.DataFrame(rows).to_csv(report_dir / "catch_seed_metrics.csv", index=False, encoding="utf-8-sig")
    return rows


def run_gcad_linear(config: dict[str, Any], root: Path) -> dict[str, Any]:
    """Linear Granger/prediction-error ablation when official GCAD code is unavailable."""
    paths, raw = config["paths"], config["gcad_linear_ablation"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"]); report_dir.mkdir(parents=True, exist_ok=True)
    store = RawWindowStore(feature_dir, _resolve(root, paths["group_dictionary"]), int(config["data"]["window_size"]))
    mean = np.load(feature_dir / "scaler_mean.npy").astype(np.float32); std = np.load(feature_dir / "scaler_std.npy").astype(np.float32)
    _, _, y_train = store.metadata("train")
    rng = np.random.default_rng(0); candidates = np.flatnonzero(y_train == 0)
    chosen = np.sort(rng.choice(candidates, min(len(candidates), raw["max_normal_train_windows"]), replace=False))
    xs, ys = [], []
    for batch in store.batches("train", chosen, int(raw["batch_size"]), mean, std):
        points = np.linspace(0, batch.shape[1] - 2, int(raw["fit_points_per_window"]), dtype=int)
        xs.append(batch[:, points].reshape(-1, batch.shape[-1])); ys.append(batch[:, points + 1].reshape(-1, batch.shape[-1]))
    model = Ridge(alpha=float(raw["ridge"]), fit_intercept=True).fit(np.concatenate(xs), np.concatenate(ys))
    def score(split: str):
        groups, _, labels = store.metadata(split); parts = []
        for batch in store.batches(split, np.arange(len(groups)), int(raw["batch_size"]), mean, std):
            prediction = model.predict(batch[:, :-1].reshape(-1, batch.shape[-1])).reshape(batch.shape[0], -1, batch.shape[-1])
            parts.append(np.mean((prediction - batch[:, 1:]) ** 2, axis=(1, 2)))
        return np.concatenate(parts), groups, labels
    val_scores, g_val, y_val = score("validation"); test_scores, g_test, y_test = score("test")
    threshold = evaluate_scores(y_val, val_scores, g_val)["threshold"]
    metrics = evaluate_scores(y_test, test_scores, g_test, threshold)
    result = {"method": "GCAD-linear-Granger-ablation", "official_implementation": False,
              "train_sample": len(chosen), "ridge": float(raw["ridge"]), **metrics,
              "limitation": "Linear VAR(1) causal-prediction ablation; not the paper's nonlinear gradient GCAD network."}
    (report_dir / "gcad_linear_metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True); return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catch", "gcad", "all"])
    parser.add_argument("--config", default="configs/p5_deep_baselines.yaml")
    args = parser.parse_args(); config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")); root = Path.cwd()
    output = {}
    if args.command in {"catch", "all"}: output["catch"] = run_catch(config, root)
    if args.command in {"gcad", "all"}: output["gcad"] = run_gcad_linear(config, root)
    report_dir = _resolve(root, config["paths"]["report_dir"])
    (report_dir / "completion_summary.json").write_text(json.dumps({"status": "complete", **output}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
