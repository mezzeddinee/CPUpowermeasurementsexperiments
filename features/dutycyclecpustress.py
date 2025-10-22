import argparse
import multiprocessing
import psutil
import time
import math
import os
import glob
import signal

# --------------------------------------------
# CPU UTILIZATION MEASUREMENT
# --------------------------------------------
def measure_cpu(label, duration=1.0):
    """Measure and print average CPU utilization over `duration` seconds."""
    print(f"\nMeasuring CPU utilization: {label} ...")
    usage = psutil.cpu_percent(interval=duration)
    print(f"CPU Utilization {label}: {usage:.2f}%")
    return usage

# --------------------------------------------
# RAPL ENERGY MEASUREMENT (CORE DOMAIN ONLY)
# --------------------------------------------
def find_rapl_domain(domain_name="core"):
    """Return the path of the given RAPL domain (e.g., 'core', 'package-0')."""
    for path in glob.glob("/sys/class/powercap/intel-rapl:*"):
        name_file = os.path.join(path, "name")
        try:
            with open(name_file) as f:
                if f.read().strip() == domain_name:
                    return path
        except FileNotFoundError:
            continue
    raise RuntimeError(f"RAPL domain '{domain_name}' not found. "
                       "Use `sudo` and check /sys/class/powercap/intel-rapl:*/name")

def read_energy_j(path):
    """Read energy (in joules) from a RAPL domain path."""
    with open(os.path.join(path, "energy_uj")) as f:
        return int(f.read().strip()) / 1e6  # µJ → J

def read_max_energy_j(path):
    """Read max counter range (in joules) from a RAPL domain path."""
    with open(os.path.join(path, "max_energy_range_uj")) as f:
        return int(f.read().strip()) / 1e6  # µJ → J

def delta_energy_wrap(prev_j, curr_j, max_j):
    """Handle RAPL counter wraparound."""
    if curr_j >= prev_j:
        return curr_j - prev_j
    else:
        return (max_j - prev_j) + curr_j

# --------------------------------------------
# DUTY-CYCLE CPU STRESS FUNCTION
# --------------------------------------------
def cpu_worker(a, interval, total_duration):
    """Worker that runs factorial computation for fraction `a` of each interval."""
    n = 5000
    end_time = time.time() + total_duration

    while time.time() < end_time:
        active_time = a * interval
        idle_time = (1 - a) * interval

        t0 = time.time()
        while (time.time() - t0) < active_time:
            math.factorial(n)
        if idle_time > 0:
            time.sleep(idle_time)

# --------------------------------------------
# SPAWN & MANAGE PROCESSES
# --------------------------------------------
def start_stress_processes(a, interval, duration):
    total_cores = multiprocessing.cpu_count()
    print(f"Total cores: {total_cores}")
    print(f"Spawning {total_cores} processes for {duration}s with a={a:.2f}, interval={interval}s")

    processes = []
    for _ in range(total_cores):
        p = multiprocessing.Process(target=cpu_worker, args=(a, interval, duration))
        p.start()
        processes.append(p)
    return processes

def stop_processes(processes):
    for p in processes:
        if p.is_alive():
            p.terminate()
    for p in processes:
        p.join(timeout=1)

# --------------------------------------------
# MAIN EXECUTION
# --------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Duty-cycled CPU stress test using RAPL core energy measurement."
    )
    parser.add_argument("a", type=float, help="Active fraction per interval (0–1)")
    parser.add_argument("--interval", type=float, default=10, help="Duty-cycle interval in seconds (default: 10)")
    parser.add_argument("--duration", type=int, default=60, help="Total test duration in seconds (default: 60)")
    args = parser.parse_args()

    a = args.a
    interval = args.interval
    duration = args.duration

    if not (0 <= a <= 1):
        print("Error: fraction 'a' must be between 0 and 1.")
        return
    if interval <= 0 or duration <= 0:
        print("Error: interval and duration must be positive.")
        return

    # Find RAPL core domain
    try:
        rapl_path = find_rapl_domain("core")
        max_j = read_max_energy_j(rapl_path)
        print(f"\nUsing RAPL domain: {rapl_path} (core)\n")
    except Exception as e:
        print(f"Warning: {e}")
        rapl_path = None
        max_j = None

    print("\n--- BASELINE MEASUREMENT ---")
    measure_cpu("before")
    e_before = read_energy_j(rapl_path) if rapl_path else 0.0
    print(f"Energy (before): {e_before:.3f} J")

    print(f"\n--- STARTING DUTY-CYCLED STRESS (a={a:.2f}, interval={interval}s, duration={duration}s) ---\n")
    processes = start_stress_processes(a, interval, duration)

    try:
        measure_cpu("during", duration)
    finally:
        print("\n--- STOPPING STRESS ---")
        stop_processes(processes)

    e_after = read_energy_j(rapl_path) if rapl_path else 0.0
    if rapl_path:
        e_delta = delta_energy_wrap(e_before, e_after, max_j)
        print(f"Energy (after): {e_after:.3f} J")
        print(f"Core-domain energy consumed during test: {e_delta:.3f} J")

    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    # Requires psutil: pip install psutil
    main()