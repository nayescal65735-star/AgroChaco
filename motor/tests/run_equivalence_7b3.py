#!/usr/bin/env python3
import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"
DEFAULT_CONFIG = ROOT / "config" / "simulacion_villamontes.json"
TIMEOUT_SECONDS = 40

INDICATOR_PATHS = {
    "CWSI promedio": ("averageCWSI",),
    "Humedad final": ("soilMoistureFinalPercent",),
    "Pérdida de rendimiento": ("yieldLossPercent",),
    "Rendimiento estimado": ("estimatedYieldTnHa",),
    "Déficit hídrico": ("waterDeficitMm",),
    "Resumen balance": ("waterBalanceSummary",),
    "Serie temporal": ("timelineData",),
    "Malla espacial": ("spatialGrid",),
}


def run_command(command, env):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.communicate(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                pass
        raise RuntimeError(f"Timeout ejecutando: {' '.join(command)}")

    if process.returncode != 0:
        raise RuntimeError(
            f"Comando falló ({process.returncode}): {' '.join(command)}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return stdout, stderr


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def effective_config(data):
    return data.get("config") or {}


def numeric_diff(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return 0.0 if left == right else math.inf
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right))
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return math.inf
        return max([numeric_diff(left[key], right[key]) for key in left] or [0.0])
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return math.inf
        return max([numeric_diff(a, b) for a, b in zip(left, right)] or [0.0])
    if left != right:
        return math.inf
    return 0.0


def check(label, condition, detail=""):
    if condition:
        print(f"OK   {label}{(' | ' + detail) if detail else ''}")
        return True
    print(f"FAIL {label}{(' | ' + detail) if detail else ''}")
    return False


def verify_storage_identity(data, label):
    summary = data.get("waterBalanceSummary")
    if not isinstance(summary, dict):
        return check(f"Identidad de almacenamiento {label}", False, "resumen ausente")
    lhs = summary["storageFinalMm"] - summary["storageInitialMm"]
    rhs = summary["storageChangeMm"] + summary["rootDepthStorageRebaseTotalMm"]
    residual = abs(lhs - rhs)
    return check(
        f"Identidad de almacenamiento {label}",
        residual < 1e-8,
        f"|Delta total - (suma diaria + rebase)|={residual:.3e} mm",
    )


def verify_daily_balance(data, label):
    worst = 0.0
    for point in data.get("timelineData", []):
        balance = point.get("waterBalance")
        if not isinstance(balance, dict):
            return check(f"Residuo diario {label}", False, "balance ausente")
        lhs = (
            balance["storageChangeMm"]
            + balance["etaMm"]
            + balance["deepDrainageMm"]
            - balance["precipitationMm"]
        )
        worst = max(worst, abs(lhs - balance["balanceResidualMm"]))
        if balance["balanceErrorMm"] + 1e-9 < abs(balance["balanceResidualMm"]):
            return check(
                f"Residuo diario {label}",
                False,
                "el error máximo por celda es menor que el residuo agregado",
            )
    return check(
        f"Residuo diario {label}",
        worst < 1e-9,
        f"max diferencia={worst:.3e} mm",
    )


def verify_effective_resources(data, label, engine, processes=None, threads=None):
    config = effective_config(data)
    ok = check(
        f"Identidad del motor {label}",
        str(config.get("engine", "")).lower() == engine,
        f"engine={config.get('engine')}",
    )
    if processes is not None:
        ok &= check(
            f"Procesos efectivos {label}",
            int(config.get("mpiProcesses", -1)) == processes,
            f"mpiProcesses={config.get('mpiProcesses')}",
        )
    if threads is not None:
        ok &= check(
            f"Hilos efectivos {label}",
            int(config.get("openmpThreads", -1)) == threads,
            f"openmpThreads={config.get('openmpThreads')}",
        )
    ok &= check(
        f"Nodos efectivos {label}",
        int(config.get("nodesCount", -1)) == 1,
        f"nodesCount={config.get('nodesCount')}",
    )
    if engine == "secuencial":
        ok &= check(
            f"Métrica base declarada {label}",
            data.get("speedup") is not None and data.get("efficiency") is not None,
            f"speedup={data.get('speedup')} efficiency={data.get('efficiency')}",
        )
    else:
        ok &= check(
            f"Sin métricas ficticias {label}",
            data.get("speedup") is None and data.get("efficiency") is None,
            f"speedup={data.get('speedup')} efficiency={data.get('efficiency')}",
        )
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--rows", type=int, default=7)
    parser.add_argument("--cols", type=int, default=11)
    args = parser.parse_args()

    mpirun = shutil.which("mpirun")
    if mpirun is None:
        raise RuntimeError("No se encontró mpirun.")

    base_env = os.environ.copy()
    common = [
        "--config",
        args.config,
        "--days",
        str(args.days),
        "--rows",
        str(args.rows),
        "--cols",
        str(args.cols),
    ]

    with tempfile.TemporaryDirectory(prefix="agrochaco-7b3-") as tmp:
        output_dir = Path(tmp)
        cases = []

        def case(name, command, threads_env=None):
            path = output_dir / f"{name}.json"
            env = base_env.copy()
            if threads_env is not None:
                env["OMP_NUM_THREADS"] = str(threads_env)
            run_command(command + ["--output", str(path)], env)
            data = load_json(path)
            check(f"Estado completado {name}", data.get("status") == "completed")
            cases.append((name, data))

        case(
            "secuencial",
            [str(BIN / "agrochaco_secuencial")] + common,
        )
        case(
            "openmp_t2",
            [str(BIN / "agrochaco_openmp")] + common + ["--threads", "2"],
            2,
        )
        case(
            "openmp_t4",
            [str(BIN / "agrochaco_openmp")] + common + ["--threads", "4"],
            4,
        )
        case(
            "mpi_np2",
            [mpirun, "--oversubscribe", "-np", "2", str(BIN / "agrochaco_mpi")] + common,
        )
        case(
            "mpi_np4",
            [mpirun, "--oversubscribe", "-np", "4", str(BIN / "agrochaco_mpi")] + common,
        )
        case(
            "hibrido_np2_t2",
            [mpirun, "--oversubscribe", "-np", "2", str(BIN / "agrochaco_hibrido")]
            + common
            + ["--threads", "2"],
            2,
        )
        case(
            "hibrido_np4_t2",
            [mpirun, "--oversubscribe", "-np", "4", str(BIN / "agrochaco_hibrido")]
            + common
            + ["--threads", "2"],
            2,
        )

        baseline = cases[0][1]
        all_ok = True

        all_ok &= verify_effective_resources(baseline, "secuencial", "secuencial")
        all_ok &= verify_effective_resources(cases[1][1], "openmp_t2", "openmp", threads=2)
        all_ok &= verify_effective_resources(cases[2][1], "openmp_t4", "openmp", threads=4)
        all_ok &= verify_effective_resources(cases[3][1], "mpi_np2", "mpi", processes=2)
        all_ok &= verify_effective_resources(cases[4][1], "mpi_np4", "mpi", processes=4)
        all_ok &= verify_effective_resources(
            cases[5][1], "hibrido_np2_t2", "hibrido", processes=2, threads=2
        )
        all_ok &= verify_effective_resources(
            cases[6][1], "hibrido_np4_t2", "hibrido", processes=4, threads=2
        )

        for name, data in cases:
            all_ok &= verify_storage_identity(data, name)
            all_ok &= verify_daily_balance(data, name)

        print("\nDiferencias máximas frente al motor secuencial:")
        worst_by_indicator = {}
        for label, path in INDICATOR_PATHS.items():
            worst = 0.0
            for name, data in cases[1:]:
                left = baseline
                right = data
                for key in path:
                    left = left[key]
                    right = right[key]
                worst = max(worst, numeric_diff(left, right))
            worst_by_indicator[label] = worst
            tolerance = 1e-6 if label == "CWSI promedio" else 1e-3
            ok = worst <= tolerance
            all_ok &= ok
            print(
                f"{'OK  ' if ok else 'FAIL'} {label}: max={worst:.3e} "
                f"tol={tolerance:.1e} {'abs/rel' if tolerance == 1e-6 else 'abs'}"
            )

        print("\nResultado global de equivalencia:", "OK" if all_ok else "FAIL")
        return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        sys.exit(1)
