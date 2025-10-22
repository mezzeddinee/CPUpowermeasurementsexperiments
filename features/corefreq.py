import argparse
import multiprocessing
import psutil
import time
import math
import os
import glob

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
# PER-CORE FREQUENCY MEASUREMENT
# --------------------------------------------
def get_core_frequencies():
    """Return a dict {core_id: freq_MHz} for all cores with readable data."""
    freqs = {}
    for path in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")):
        try:
            cpu = int(path.split("/cpu")[-1].split("/")[0])
            with open(path) as f:
                freq_khz = int(f.read().strip())
                freqs[cpu] = freq_khz / 1000.0  # kHz → MHz
        except (FileNotFoundError, ValueError):
            continue
    return freqs

def print_all_core_frequencies(label):
    """Print current frequency of each core."""
    freqs = get_core_frequencies()
    if not freqs:
        print(f"{label}: Unable to read per-core frequencies (no cpufreq data).")
        return None
    print(f"\n{label}:")
    for core_id in sorted(freqs.keys()):
        print(f"  Core {core_id}: {freqs[core_id]:.1f} MHz")
    return freqs

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
    return curr_j - prev_j if curr_j >= prev_j else (max_j - prev_j) + curr_j

# --------------------------------------------
# CPU STRESS FUNCTION
# --------------------------------------------
def cpu_worker():
    """Continuously compute factorials to stress CPU."""
    n = 5000
    while True:
        math.factorial(n)

def stress_cpu(target_fraction):
    """Spawn processes at 100% CPU usage to match the target load."""
    total_cores = multiprocessing.cpu_count()
    cores_to_use = max(1, int(total_cores * target_fraction))

    print(f"Total cores: {total_cores}")
    print(f"Starting {cores_to_use} process(es) to achieve ~{target_fraction * 100:.0f}% total CPU load")

    processes = []
    for _ in range(cores_to_use):
        p = multiprocessing.Process(target=cpu_worker)
        p.daemon = True
        p.start()
        processes.append(p)

    return processes

def stop_processes(processes):
    """Terminate all stress processes."""
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
        description="Stress CPU by fraction A using multiprocessing factorial computation "
                    "and measure per-core frequencies plus RAPL core-domain energy."
    )
    parser.add_argument("a", type=float, help="CPU usage fraction (0–1)")
    parser.add_argument("--duration", type=int, default=10, help="Stress duration in seconds (default: 10)")
    args = parser.parse_args()

    a = args.a
    if not (0 <= a <= 1):
        print("Error: CPU fraction 'a' must be between 0 and 1.")
        return

    duration = args.duration

    # Find RAPL core domain
    rapl_path = find_rapl_domain("core")
    max_j = read_max_energy_j(rapl_path)
    print(f"\nUsing RAPL domain: {rapl_path} (core)\n")

    print("\n--- BASELINE MEASUREMENT ---")
    measure_cpu("before")
    print_all_core_frequencies("Frequencies before stress")
    e_before = read_energy_j(rapl_path)
    print(f"Energy (before): {e_before:.3f} J")

    print(f"\n--- STARTING CPU STRESS (~{a * 100:.0f}% load for {duration}s) ---\n")
    processes = stress_cpu(a)

    time.sleep(2)
    measure_cpu("during")

    time.sleep(max(0, duration - 2))

    print("\n--- STOPPING STRESS ---")
    stop_processes(processes)

    e_after = read_energy_j(rapl_path)
    e_delta = delta_energy_wrap(e_before, e_after, max_j)
    print_all_core_frequencies("Frequencies after stress")
    print(f"Energy (after): {e_after:.3f} J")

    print("\n--- SUMMARY ---")
    print(f"Core-domain energy consumed during test: {e_delta:.3f} J")

if __name__ == "__main__":
    # Requires psutil: pip install psutil
    main()
