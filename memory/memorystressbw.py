import argparse

import numpy as np
import time
import os
import glob

import psutil


# ---------------------------
# Utility functions
# ---------------------------

def measure_memory(label):
    """Print total and used memory."""
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    percent = mem.percent
    print(f"\nMemory {label}: {used_gb:.2f} GB used / {total_gb:.2f} GB total ({percent:.2f}%)")

def read_rapl_energy():
    """Read energy (J) for all available RAPL domains."""
    rapl_data = {}
    for path in glob.glob("/sys/class/powercap/intel-rapl:*"):
        domain_name = os.path.basename(path)
        name_path = os.path.join(path, "name")
        energy_path = os.path.join(path, "energy_uj")

        if os.path.exists(name_path):
            with open(name_path) as f:
                domain_name = f.read().strip()

        if os.path.exists(energy_path):
            with open(energy_path) as f:
                energy_uj = int(f.read().strip())
                rapl_data[domain_name] = energy_uj / 1e6  # µJ → J
    return rapl_data

def print_rapl(label, data):
    """Pretty-print RAPL readings."""
    print(f"\nRAPL Energy {label}:")
    if not data:
        print("  (No RAPL data found — requires Intel RAPL support)")
        return
    for k, v in data.items():
        print(f"  {k:10s}: {v:.3f} J")

def compute_rapl_delta(before, after):
    """Return dict of deltas (after - before)."""
    delta = {}
    for k in after.keys():
        if k in before:
            delta[k] = after[k] - before[k]
    return delta

# ---------------------------
# Memory Bandwidth Stress
# ---------------------------

def memory_bandwidth_stress(fraction=0.5, iterations=20):
    """
    Stress the memory subsystem by performing large streaming operations.
    - fraction: fraction of total RAM to use
    - iterations: number of compute passes over the data
    """
    total_mem = psutil.virtual_memory().total
    bytes_to_use = int(total_mem * fraction)
    n_elements = bytes_to_use // 8   # float64 → 8 bytes each
    size_gb = bytes_to_use / (1024 ** 3)

    print(f"\n→ Creating two arrays of ~{size_gb/2:.2f} GB each ({fraction*100:.0f}% of total RAM)")
    print(f"  Total elements per array: {n_elements:,}")

    # Allocate two large arrays in RAM
    a = np.ones(n_elements, dtype=np.float64)
    b = np.ones(n_elements, dtype=np.float64)

    print(f"  Running {iterations} streaming additions ...")
    measure_memory("before compute")

    start = time.time()
    for i in range(iterations):
        # Each pass touches every memory location
        a += b
        if (i + 1) % max(1, iterations // 5) == 0:
            print(f"    Iteration {i+1}/{iterations} done.")
    end = time.time()

    measure_memory("after compute")

    elapsed = end - start
    total_bytes = a.nbytes * iterations * 2  # read + write
    bandwidth_gbps = (total_bytes / elapsed) / (1024 ** 3)
    print(f"  Elapsed: {elapsed:.2f} s | Approx. memory bandwidth: {bandwidth_gbps:.2f} GB/s")

    # keep arrays alive briefly to stabilize power readings
    time.sleep(1)

# ---------------------------
# Main Timed Loop
# ---------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Periodic RAPL measurement with high-bandwidth memory stress."
    )
    parser.add_argument("a", type=float, help="Memory usage fraction (0–1)")
    parser.add_argument("-d", "--duration", type=int, default=60,
                        help="Total test duration in seconds (default: 60)")
    parser.add_argument("-i", "--interval", type=int, default=10,
                        help="Interval between stress events in seconds (default: 10)")
    parser.add_argument("-n", "--iterations", type=int, default=10,
                        help="Compute iterations per stress phase (default: 10)")
    args = parser.parse_args()

    a = args.a
    if not (0 <= a <= 1):
        print("Error: Memory fraction 'a' must be between 0 and 1.")
        return

    total_time = args.duration
    interval = args.interval
    iterations = args.iterations

    print(f"\n=== RAPL + Memory Bandwidth Stress Test ===")
    print(f"  Duration: {total_time}s | Interval: {interval}s | Memory: {a*100:.0f}% | Iterations per phase: {iterations}\n")

    start_time = time.time()
    iteration = 1

    while (time.time() - start_time) < total_time:
        print(f"\n=== Iteration {iteration} ===")

        measure_memory("before")
        rapl_before = read_rapl_energy()
        print_rapl("before", rapl_before)

        # Run bandwidth-intensive memory workload
        memory_bandwidth_stress(fraction=a, iterations=iterations)

        rapl_after = read_rapl_energy()
        print_rapl("after", rapl_after)

        delta = compute_rapl_delta(rapl_before, rapl_after)
        if delta:
            print("\nRAPL Energy delta (after - before):")
            for k, v in delta.items():
                print(f"  {k:10s}: {v:.3f} J")

        iteration += 1

        # Sleep until next interval
        elapsed = time.time() - start_time
        if elapsed < total_time:
            next_wait = min(interval, total_time - elapsed)
            print(f"\nWaiting {next_wait:.1f}s before next iteration...")
            time.sleep(next_wait)

    print("\n✅ Test completed.")

# ---------------------------
# Entry Point
# ---------------------------

if __name__ == "__main__":
    # Requires: pip install psutil numpy
    main()