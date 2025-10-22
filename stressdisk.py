import argparse
import psutil
import os
import time
import tempfile
import shutil
import threading

def measure_disk(label, path="/"):
    """Report total and used disk space for the filesystem containing `path`."""
    usage = psutil.disk_usage(path)
    used_gb = usage.used / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    percent = usage.percent
    print(f"\nDisk {label}: {used_gb:.2f} GB used / {total_gb:.2f} GB total ({percent:.2f}%)")


def stress_disk(target_fraction, path="/"):
    """
    Write a large temp file approximating target_fraction of total disk space.
    """
    usage = psutil.disk_usage(path)
    total_bytes = usage.total
    to_write = int(total_bytes * target_fraction)

    print(f"Total disk: {usage.total / (1024 ** 3):.2f} GB")
    print(f"Attempting to write ~{to_write / (1024 ** 3):.2f} GB "
          f"({target_fraction * 100:.0f}%)")

    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "disk_stress.tmp")

    written = 0
    block_size = 1024 * 1024  # 1MB

    def write_data():
        nonlocal written
        try:
            with open(temp_file_path, "wb") as f:
                block = b"x" * block_size
                while written < to_write:
                    f.write(block)
                    written += block_size
        except Exception as e:
            print(f"\nWrite stopped early due to error: {e}")

    thread = threading.Thread(target=write_data)
    thread.daemon = True
    thread.start()

    return temp_dir, temp_file_path, thread


def main():
    parser = argparse.ArgumentParser(
        description="Stress disk I/O by fraction A and report disk usage before/during."
    )
    parser.add_argument("a", type=float, help="Disk usage fraction (0–1)")
    parser.add_argument(
        "--path",
        type=str,
        default="/",
        help="Path to determine which filesystem to stress (defaults to root)."
    )
    args = parser.parse_args()

    a = args.a
    if not (0 <= a <= 1):
        print("Error: Disk fraction 'a' must be between 0 and 1.")
        return

    target_path = args.path

    # Report disk usage before
    measure_disk("before", target_path)

    print(f"\nStarting disk stress at ~{a * 100:.0f}% load...")
    temp_dir, temp_file_path, thread = stress_disk(a, target_path)

    # Let some data get written, then measure again
    time.sleep(3)
    measure_disk("during", target_path)

    print("\nWriting continues until target is reached or you press Ctrl+C.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCleaning up temporary files...")
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            print(f"Error removing temporary directory: {e}")
        print("Stopping.")


if __name__ == "__main__":
    # Requires psutil: pip install psutil
    main()