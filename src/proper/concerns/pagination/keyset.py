"""Keyset (a.k.a. seek) predicate construction for Peewee.

Given an ordering `[(k1, d1), ..., (kn, dn)]` and the values
`(v1, ..., vn)` of the last row already seen, the rows that come strictly
*after* it in that same lexicographic order satisfy::

```sql
OR over j=1..n of:
    (k1 = v1 AND ... AND k_{j-1} = v_{j-1} AND cmp_j(k_j, v_j))
```

where `cmp_j` is `k_j < v_j` when column j is descending, and
`k_j > v_j` when ascending.

This OR-of-ANDs form is used instead of SQL row-value comparison
`(a, b) > (x, y)` because the latter is not portable across the backends
Peewee supports.
"""

import operator
from collections.abc import Sequence
from functools import reduce


def keyset_predicate(ordered_by: Sequence[tuple], values: list):
    if len(ordered_by) != len(values):
        raise ValueError("ordered_by and values must have the same length")

    or_terms = []
    for j, (field_j, direction_j) in enumerate(ordered_by):
        and_terms = []
        for i in range(j):
            field_i, _ = ordered_by[i]
            and_terms.append(field_i == values[i])
        if direction_j == "desc":
            and_terms.append(field_j < values[j])
        else:
            and_terms.append(field_j > values[j])
        or_terms.append(reduce(operator.and_, and_terms))

    return reduce(operator.or_, or_terms)
