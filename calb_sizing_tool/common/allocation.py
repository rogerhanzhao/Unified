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


def allocate_balanced(total: int, buckets: int, min_per_bucket: int = 0) -> List[int]:
    if buckets <= 0:
        return []
    total = int(total)
    if total <= 0:
        return [0 for _ in range(buckets)]
    min_per_bucket = max(0, int(min_per_bucket))
    minimum_total = min_per_bucket * buckets
    if min_per_bucket > 0 and total >= minimum_total:
        remaining = total - minimum_total
        extra = evenly_distribute(remaining, buckets)
        return [min_per_bucket + extra[idx] for idx in range(buckets)]
    return evenly_distribute(total, buckets)


def allocate_dc_blocks(total_blocks: int, pcs_count: int) -> List[int]:
    min_per_pcs = 1 if int(total_blocks) >= int(pcs_count or 0) and pcs_count else 0
    return allocate_balanced(total_blocks, pcs_count, min_per_bucket=min_per_pcs)
