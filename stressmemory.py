import argparse
import psutil
import time

def measure_memory(label):
    """Print total and used memory."""
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    percent = mem.percent
    print(f"\nMemory {label}: {used_gb:.2f} GB used / {total_gb:.2f} GB total ({percent:.2f}%)")


def stress_memory(target_fraction):
    """
    Allocate approximately target_fraction of total RAM.
    """
    total_mem = psutil.virtual_memory().total
    bytes_to_allocate = int(total_mem * target_fraction)

    print(f"Total RAM: {total_mem / (1024 ** 3):.2f} GB")
    print(f"Attempting to allocate ~{bytes_to_allocate / (1024 ** 3):.2f} GB "
          f"({target_fraction * 100:.0f}%)")

    try:
        block_size = 1024 * 1024  # 1 MB chunks
        blocks = bytes_to_allocate // block_size
        allocated = ['x' * block_size for _ in range(blocks)]
        print("Memory allocation successful.")
        return allocated
    except MemoryError:
        print("Memory allocation failed.")
        return []


def main():
    # Report memory before
    measure_memory("before")

    print(f"\nStarting memory stress at ~{0.4 * 100:.0f}% load...")
    allocated_blocks = stress_memory(0.4)

    # Allow some time for system to update memory stats
    time.sleep(4)
    measure_memory("during")
    del allocated_blocks


if __name__ == "__main__":
    # Requires psutil: pip install psutil
    main()
