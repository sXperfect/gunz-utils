import timeit
import random
import string
import sys
import os

# Ensure the local `src` is correctly importable
sys.path.insert(0, os.path.abspath('src'))

from gunz_utils.security import sanitize_filename

random.seed(42)

def generate_random_filename(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length)) + ".txt"

def benchmark():
    # Mix of mostly normal filenames and a few reserved
    filenames = [generate_random_filename(random.randint(5, 20)) for _ in range(1000)]

    # Pre-warm
    for f in filenames:
        sanitize_filename(f)

    def run_benchmark():
        for f in filenames:
            sanitize_filename(f)

    time_taken = timeit.timeit(run_benchmark, number=1000)
    print(f"Time taken to sanitize {len(filenames)} normal files 1000 times: {time_taken:.4f} seconds")

if __name__ == "__main__":
    benchmark()
