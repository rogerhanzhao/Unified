from typing import List


def evenly_distribute(total: int, buckets: int) -> List[int]:
    if buckets <= 0:
        return []
    total = int(total)
    buckets = int(buckets)
    if total <= 0:
        return [0 for _ in range(buckets)]
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if idx < remainder else 0) for idx in range(buckets)]
