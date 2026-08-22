from sol import merge
assert merge([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]
assert merge([[1,3],[3,5]])==[[1,5]]
assert merge([[1,10],[2,3]])==[[1,10]]
assert merge([[5,7],[1,2],[2,4],[6,9]])==[[1,4],[5,9]]
assert merge([])==[]
print("T2 OK")
