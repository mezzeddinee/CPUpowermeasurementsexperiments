import argparse
import multiprocessing
import psutil
import threading
import time

def measure_cpu(label, duration=1.0):
    """Measure and print average CPU utilization over `duration` seconds."""
    print(f"\nMeasuring CPU utilization: {label} ...")
    usage = psutil.cpu_percent(interval=duration)
    print(f"CPU Utilization {label}: {usage:.2f}%")
    return usage

def stress_cpu(target_fraction):
    """
    Use only the necessary number of cores at 100% to match overall CPU load.
    Example: 12 cores, target_fraction = 0.6 → use 7 cores fully.
    """
    total_cores = multiprocessing.cpu_count()
    cores_to_use = max(1, int(total_cores * target_fraction))

    print(f"Total cores: {total_cores}")
    print(f"Using {cores_to_use} core(s) at 100% to achieve ~{target_fraction * 100:.0f}% total CPU load")

    def burn():
        while True:
            pass

    threads = []
    for _ in range(cores_to_use):
        t = threading.Thread(target=burn)
        t.daemon = True
        t.start()
        threads.append(t)

    return threads

def main():
    parser = argparse.ArgumentParser(
        description="Stress CPU by fraction A using 100% load on only required cores and report utilization."
    )
    parser.add_argument("a", type=float, help="CPU usage fraction (0–1)")
    args = parser.parse_args()

    a = args.a
    if not (0 <= a <= 1):
        print("Error: CPU fraction 'a' must be between 0 and 1.")
        return

    # Report CPU utilization before stress
    measure_cpu("before")

    print(f"\nStarting CPU stress at ~{a * 100:.0f}% total load...\n")
    threads = stress_cpu(a)

    # Allow threads to ramp up
    time.sleep(2)
    measure_cpu("during")

    print("\nPress Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    # Requires psutil: pip install psutil
    main()