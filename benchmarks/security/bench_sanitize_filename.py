# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import random
import string
import timeit

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.security import sanitize_filename

random.seed(42)


def generate_random_filename(
    length: int = 10,
) -> str:
    stem = "".join(random.choices(string.ascii_letters + string.digits, k=length))
    return stem + ".txt"


def benchmark() -> None:
    #? Mix of mostly normal filenames and a few reserved
    filenames = [generate_random_filename(random.randint(5, 20)) for _ in range(1000)]

    #? Pre-warm
    for f in filenames:
        sanitize_filename(f)

    def run_benchmark() -> None:
        for f in filenames:
            sanitize_filename(f)

    time_taken = timeit.timeit(run_benchmark, number=1000)
    print(
        f"Time taken to sanitize {len(filenames)} normal files 1000 times: "
        f"{time_taken:.4f} seconds"
    )


if __name__ == "__main__":
    benchmark()
