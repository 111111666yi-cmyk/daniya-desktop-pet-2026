from time import perf_counter


PROCESS_STARTED_AT = perf_counter()

from src.app import run


if __name__ == "__main__":
    run(process_started_at=PROCESS_STARTED_AT)

