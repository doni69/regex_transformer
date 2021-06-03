from hypothesis import given, settings, assume, strategies as st, HealthCheck
import re
from transformer import inter, diff
from sys import argv
from time import time


@given(st.from_regex(inter(argv[1], argv[2]), fullmatch=True))
def re_trans(r):
    global cnt
    cnt += 1
    if cnt <= 5:
        print(repr(r))


@settings(suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow])
@given(st.from_regex(argv[1], fullmatch=True))
def rej_samp(r):
    assume(re.fullmatch(argv[2], r))
    global cnt
    cnt += 1
    if cnt < 5:
        print(repr(r))


print("Transformed regex:")
cnt = 0
t = time()
re_trans()
t = time() - t
if cnt > 5:
    print("...")
print(f"{cnt} example(s) generated in {t:.2f} seconds")

print("Rejection sampling:")
cnt = 0
t = time()
try:
    rej_samp()
except Exception as e:
    print(e)
t = time() - t
if cnt > 5:
    print("...")
print(f"{cnt} example(s) generated in {t:.2f} seconds")
