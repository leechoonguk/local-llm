The following function is supposed to merge overlapping OR touching closed intervals and return them sorted, but it has bugs. Fix it.
```python
def merge(intervals):
    out = []
    for s, e in intervals:
        if out and s < out[-1][1]:
            out[-1][1] = e
        else:
            out.append([s, e])
    return out
```
Requirements: input may be unsorted; intervals like [1,3] and [3,5] touch and must merge to [1,5]; [1,10],[2,3] must give [1,10]; return list of [start,end] lists.
Output ONLY the corrected function in a single ```python block, no explanation.
