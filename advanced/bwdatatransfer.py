#!/usr/bin/env python3
"""
High-bandwidth RAPL memory stress test using multiple worker processes.

Each worker runs a Numba-JIT parallel streaming kernel on its own arrays.
Together they can saturate all memory channels to drive DRAM RAPL power high.

Requires:
    pip install numpy psutil numba
"""

import argparse
import os
import time
import glob
import psutil
import subprocess
import numpy as np
import multiprocessing as mp
from numba import njit, prange


# ================================================================
# Utility Functions
# ================================================================

def measure_memory(label):
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    percent = mem.percent
    print(f"\nMemory {label}: {used_gb:.2f} GB used / {total_gb:.2f} GB total ({percent:.2f}%)", flush=True)


def sudo_cat(path):
    try:
        result = subprocess.run(
            ["sudo", "/bin/cat", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def read_rapl_energy():
    rapl_data = {}
    for path in glob.glob("/sys/class/powercap/intel-rapl:*"):
        name_path = os.path.join(path, "name")
        energy_path = os.path.join(path, "energy_uj")
        domain = os.path.basename(path)
        if os.path.exists(name_path):
            n = sudo_cat(name_path)
            if n:
                domain = n.strip()
        if os.path.exists(energy_path):
            val = sudo_cat(energy_path)
            if val and val.isdigit():
                rapl_data[domain] = int(val) / 1e6  # µJ → J
    return rapl_data


def print_rapl(label, data):
    print(f"\nRAPL Energy {label}:", flush=True)
    if not data:
        print("  (No RAPL data found — requires Intel RAPL support and sudo access)", flush=True)
        return
    for k, v in data.items():
        print(f"  {k:10s}: {v:.3f} J", flush=True)


def compute_rapl_delta(before, after):
    delta = {}
    for k in after:
        if k in before:
            delta[k] = after[k] - before[k]
    return delta


# ================================================================
# Worker kernel
# ================================================================

@njit(parallel=True, fastmath=True)
def stream_add(a, b, c):
    """One full streaming pass: a[i] += b[i] + c[i]."""
    n = a.shape[0]
    for i in prange(n):
        a[i] += b[i] + c[i]


def worker_task(fraction, duration_sec, worker_id):
    """Run inside each worker process."""
    total = psutil.virtual_memory().total
    bytes_to_use = int(total * fraction)
    bytes_per_array = bytes_to_use // 3
    n_elements = bytes_per_array // 8

    a = np.ones(n_elements, np.float64)
    b = np.ones(n_elements, np.float64)
    c = np.ones(n_elements, np.float64)

    stream_add(a, b, c)  # compile once

    start = time.time()
    end = start + duration_sec
    iters = 0
    last = start
    while time.time() < end:
        stream_add(a, b, c)
        iters += 1
        now = time.time()
        if now - last >= 10:
            print(f"[Worker {worker_id}] {now - start:.1f}s elapsed, {iters} passes", flush=True)
            last = now
    print(f"[Worker {worker_id}] Done after {iters} passes", flush=True)


# ================================================================
# Main
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="High-bandwidth multi-process RAPL memory stress test."
    )
    parser.add_argument("a", type=float, help="Total memory fraction (0–1 of RAM)")
    parser.add_argument(
        "-s", "--stress-duration", type=int, default=30,
        help="Duration in seconds (default: 30)"
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=os.cpu_count() // 2,
        help="Number of worker processes (default: half the cores)"
    )
    args = parser.parse_args()

    a = args.a
    duration = args.stress_duration
    workers = args.workers

    if not (0 < a <= 1):
        print("Error: memory fraction must be 0–1")
        return

    print(f"\n=== RAPL + Multi-Process Maximum Bandwidth Memory Stress ===")
    print(f"  Workers: {workers} | Total RAM fraction: {a*100:.0f}% | Duration: {duration}s\n")

    measure_memory("before")
    rapl_before = read_rapl_energy()
    print_rapl("before", rapl_before)

    # Each worker gets an equal slice of total memory fraction
    per_worker_fraction = a / workers

    procs = []
    for wid in range(workers):
        p = mp.Process(target=worker_task, args=(per_worker_fraction, duration, wid))
        p.start()
        procs.append(p)

    for p in procs:
        p.join()

    measure_memory("after")

    rapl_after = read_rapl_energy()
    print_rapl("after", rapl_after)

    delta = compute_rapl_delta(rapl_before, rapl_after)
    elapsed = duration
    if delta:
        print("\nRAPL Energy delta (after – before):", flush=True)
        for k, v in delta.items():
            power = v / elapsed
            print(f"  {k:10s}: {v:.3f} J  |  {power:.2f} W", flush=True)

    print("\n✅ Test completed.", flush=True)


# ================================================================
# Entry Point
# ================================================================

if __name__ == "__main__":
    mp.set_start_method("spawn")
    os.environ["NUMBA_NUM_THREADS"] = str(os.cpu_count())
    main()
