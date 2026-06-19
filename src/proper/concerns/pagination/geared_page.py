import math
from collections.abc import Sequence

from ...errors import InvalidPage


class GearedPerPage:
    """Resolve a *geared* page-size progression.

    Given a list of sizes such as `[15, 30, 50, 100]`, page 1 holds 15
    records, page 2 holds 30, page 3 holds 50, and every page from 4 onward
    holds 100 (the last size repeats). A bare `int` behaves like a classic
    fixed page size.
    """

    def __init__(self, sizes: int | Sequence[int]):
        if isinstance(sizes, int):
            sizes = [sizes]
        sizes = list(sizes)
        if not sizes:
            raise ValueError("per_page must contain at least one size")
        if any(not isinstance(s, int) or s <= 0 for s in sizes):
            raise ValueError("per_page sizes must be positive integers")
        self.sizes: list[int] = sizes

    def size_of(self, number: int) -> int:
        """Number of records that page `number` (1-based) holds."""
        if number < 1:
            raise InvalidPage(f"page number must be >= 1, got {number}")
        index = min(number, len(self.sizes)) - 1
        return self.sizes[index]

    def offset_of(self, number: int) -> int:
        """Accumulated record offset before page `number` (1-based)."""
        if number < 1:
            raise InvalidPage(f"page number must be >= 1, got {number}")
        prev = number - 1
        last_index = len(self.sizes) - 1
        if prev <= last_index:
            return sum(self.sizes[:prev])
        # Pages 1..last_index use distinct sizes; the rest repeat the last one.
        return sum(self.sizes[:last_index]) + (prev - last_index) * self.sizes[-1]

    def page_count(self, total: int) -> int:
        """How many pages are needed to cover `total` records."""
        if total <= 0:
            return 0
        head_sum = 0
        for i in range(len(self.sizes) - 1):  # pages 1 .. len-1
            head_sum += self.sizes[i]
            if head_sum >= total:
                return i + 1
        remaining = total - head_sum
        extra = math.ceil(remaining / self.sizes[-1])
        return (len(self.sizes) - 1) + extra

    @property
    def cache_key(self) -> str:
        """The geared sizes as a stable string, e.g. `15-30-50-100`."""
        return "-".join(str(s) for s in self.sizes)
