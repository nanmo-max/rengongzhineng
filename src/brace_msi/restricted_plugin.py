"""Fail-closed execution sandbox for Qwen-proposed pure-function patches."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import multiprocessing
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import numpy as np


class PluginSandboxError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PluginSlot:
    slot_id: str
    function_name: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class PluginExecutionResult:
    slot_id: str
    patch_sha256: str
    output: np.ndarray
    deterministic: bool
    changed_fraction: float
    max_abs_delta: float | None


SLOTS = {
    "feature_transform": PluginSlot("feature_transform", "transform_features", ("X",)),
    "sample_weights": PluginSlot("sample_weights", "sample_weights", ("X", "y")),
    "prediction_postprocess": PluginSlot(
        "prediction_postprocess", "postprocess_predictions", ("predictions",)
    ),
}

_BANNED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.Lambda,
    ast.With,
    ast.AsyncWith,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Try,
    ast.Raise,
    ast.Global,
    ast.Nonlocal,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.Delete,
)
_SAFE_BUILTINS = {"abs": abs, "min": min, "max": max, "float": float, "int": int, "len": len}
_SAFE_NUMPY_CALLS = {
    "abs",
    "clip",
    "column_stack",
    "concatenate",
    "log1p",
    "maximum",
    "minimum",
    "nan_to_num",
    "ones_like",
    "sqrt",
    "tanh",
    "where",
    "zeros_like",
}
_SAFE_ARRAY_ATTRIBUTES = {"shape", "ndim"}


class _StaticGate(ast.NodeVisitor):
    def __init__(self, slot: PluginSlot) -> None:
        self.slot = slot
        self.local_names = set(slot.arguments)

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, _BANNED_NODES):
            raise PluginSandboxError("forbidden_syntax")
        return super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            if node.id.startswith("_"):
                raise PluginSandboxError("private_name_forbidden")
            self.local_names.add(node.id)
            return
        if node.id not in self.local_names and node.id not in {"np", *tuple(_SAFE_BUILTINS)}:
            raise PluginSandboxError("unsafe_name")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise PluginSandboxError("reflection_forbidden")
        if isinstance(node.value, ast.Name) and node.value.id == "np":
            if node.attr not in _SAFE_NUMPY_CALLS:
                raise PluginSandboxError("unsafe_numpy_call")
            return
        if isinstance(node.value, ast.Name) and node.value.id in self.slot.arguments:
            if node.attr not in _SAFE_ARRAY_ATTRIBUTES:
                raise PluginSandboxError("reflection_forbidden")
            return
        raise PluginSandboxError("reflection_forbidden")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in _SAFE_BUILTINS:
                raise PluginSandboxError("dynamic_call_forbidden")
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "np":
                if node.func.attr not in _SAFE_NUMPY_CALLS:
                    raise PluginSandboxError("unsafe_numpy_call")
            else:
                raise PluginSandboxError("dynamic_call_forbidden")
        else:
            raise PluginSandboxError("dynamic_call_forbidden")
        self.generic_visit(node)

    def visit_List(self, node: ast.List) -> None:
        if len(node.elts) > 16:
            raise PluginSandboxError("literal_too_large")
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        if len(node.elts) > 16:
            raise PluginSandboxError("literal_too_large")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Mult) and isinstance(node.left, (ast.List, ast.Tuple)):
            raise PluginSandboxError("container_repeat_forbidden")
        self.generic_visit(node)


def _validate_source(slot: PluginSlot, source: str) -> None:
    if not source.strip() or len(source.encode("utf-8")) > 16_384:
        raise PluginSandboxError("source_size_invalid")
    if "__" in source:
        raise PluginSandboxError("reflection_forbidden")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise PluginSandboxError("syntax_error") from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise PluginSandboxError("single_function_required")
    function = tree.body[0]
    if function.name != slot.function_name or function.decorator_list:
        raise PluginSandboxError("function_signature_invalid")
    args = function.args
    if (
        tuple(argument.arg for argument in args.args) != slot.arguments
        or args.defaults
        or args.kwonlyargs
        or args.vararg is not None
        or args.kwarg is not None
    ):
        raise PluginSandboxError("function_signature_invalid")
    _StaticGate(slot).visit(tree)


def _child_execute(
    connection: Any,
    source: str,
    slot: PluginSlot,
    inputs: Mapping[str, np.ndarray],
    workdir: str,
    memory_limit_bytes: int,
    output_limit_bytes: int,
) -> None:
    try:
        os.chdir(workdir)
        for key in tuple(os.environ):
            if key not in {"SYSTEMROOT", "WINDIR", "PATH", "PYTHONPATH"}:
                os.environ.pop(key, None)
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
            resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        except (ImportError, OSError, ValueError):
            pass
        namespace: dict[str, Any] = {"np": np, "__builtins__": _SAFE_BUILTINS}
        exec(compile(source, "<restricted-plugin>", "exec"), namespace, namespace)
        function = namespace[slot.function_name]
        output = np.asarray(function(**{name: inputs[name] for name in slot.arguments}))
        if output.nbytes > output_limit_bytes:
            connection.send(("error", "output_size_exceeded"))
        else:
            connection.send(("ok", output))
    except MemoryError:
        connection.send(("error", "memory_limit_exceeded"))
    except BaseException as exc:  # child errors are data, never trusted exceptions
        try:
            connection.send(("error", f"runtime_error:{type(exc).__name__}"))
        except BaseException:
            pass
    finally:
        connection.close()


class RestrictedPluginSandbox:
    def __init__(
        self,
        *,
        timeout_seconds: float = 1.0,
        memory_limit_bytes: int = 512 * 1024 * 1024,
        output_limit_bytes: int = 8 * 1024 * 1024,
        max_feature_multiplier: int = 4,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.memory_limit_bytes = int(memory_limit_bytes)
        self.output_limit_bytes = int(output_limit_bytes)
        self.max_feature_multiplier = int(max_feature_multiplier)

    def execute(self, slot_id: str, source: str, **inputs: np.ndarray) -> PluginExecutionResult:
        try:
            slot = SLOTS[slot_id]
        except KeyError as exc:
            raise PluginSandboxError("unknown_plugin_slot") from exc
        if set(inputs) != set(slot.arguments):
            raise PluginSandboxError("input_signature_invalid")
        arrays = {name: np.asarray(value) for name, value in inputs.items()}
        if any(array.nbytes > self.output_limit_bytes for array in arrays.values()):
            raise PluginSandboxError("input_size_exceeded")
        if any(not np.issubdtype(array.dtype, np.number) for array in arrays.values()):
            raise PluginSandboxError("input_type_invalid")
        _validate_source(slot, source)

        first = self._run_once(slot, source, arrays)
        self._validate_output(slot, first, arrays)
        second = self._run_once(slot, source, arrays)
        self._validate_output(slot, second, arrays)
        if first.shape != second.shape or not np.array_equal(first, second):
            raise PluginSandboxError("nondeterministic_output")

        baseline = self._baseline(slot, arrays)
        if first.shape == baseline.shape:
            delta = np.abs(first.astype(np.float64) - baseline.astype(np.float64))
            changed_fraction = float(np.count_nonzero(delta) / max(1, delta.size))
            max_abs_delta = float(np.max(delta)) if delta.size else 0.0
        else:
            changed_fraction = 1.0
            max_abs_delta = None
        return PluginExecutionResult(
            slot_id=slot_id,
            patch_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            output=first,
            deterministic=True,
            changed_fraction=changed_fraction,
            max_abs_delta=max_abs_delta,
        )

    def _run_once(
        self,
        slot: PluginSlot,
        source: str,
        inputs: Mapping[str, np.ndarray],
    ) -> np.ndarray:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        with tempfile.TemporaryDirectory(prefix="brace-plugin-") as temporary:
            workdir = Path(temporary)
            try:
                os.chmod(workdir, 0o555)
            except OSError:
                pass
            process = context.Process(
                target=_child_execute,
                args=(
                    child,
                    source,
                    slot,
                    dict(inputs),
                    str(workdir),
                    self.memory_limit_bytes,
                    self.output_limit_bytes,
                ),
            )
            process.start()
            child.close()
            process.join(self.timeout_seconds)
            if process.is_alive():
                process.terminate()
                process.join(1.0)
                parent.close()
                raise PluginSandboxError("execution_timeout")
            if not parent.poll():
                parent.close()
                raise PluginSandboxError("child_process_failed")
            status, payload = parent.recv()
            parent.close()
            if status != "ok":
                code = str(payload).split(":", 1)[0]
                raise PluginSandboxError(code)
            return np.asarray(payload)

    def _validate_output(
        self,
        slot: PluginSlot,
        output: np.ndarray,
        inputs: Mapping[str, np.ndarray],
    ) -> None:
        if not np.issubdtype(output.dtype, np.number):
            raise PluginSandboxError("output_type_invalid")
        if output.nbytes > self.output_limit_bytes:
            raise PluginSandboxError("output_size_exceeded")
        if not np.all(np.isfinite(output)):
            raise PluginSandboxError("non_finite_output")
        if slot.slot_id == "feature_transform":
            X = inputs["X"]
            if (
                output.ndim != 2
                or output.shape[0] != X.shape[0]
                or output.shape[1] < 1
                or output.shape[1] > X.shape[1] * self.max_feature_multiplier
            ):
                raise PluginSandboxError("output_shape_invalid")
        elif slot.slot_id == "sample_weights":
            expected = inputs["y"].reshape(-1).shape
            if output.reshape(-1).shape != expected:
                raise PluginSandboxError("output_shape_invalid")
            flattened = output.reshape(-1)
            if np.any(flattened < 0) or float(np.sum(flattened)) <= 0:
                raise PluginSandboxError("weights_invalid")
        elif output.shape != inputs["predictions"].shape:
            raise PluginSandboxError("output_shape_invalid")

    @staticmethod
    def _baseline(slot: PluginSlot, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        if slot.slot_id == "feature_transform":
            return np.asarray(inputs["X"])
        if slot.slot_id == "sample_weights":
            return np.ones_like(np.asarray(inputs["y"]), dtype=np.float64).reshape(-1)
        return np.asarray(inputs["predictions"])
