# Wireshark large-project stress benchmark

Pinned Wireshark `wireshark-4.4.9` dissector workload: **1640 translation units**, 2 build jobs. Lower is better.

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean compile + archive | 119.98 s | 127.47 s |
| No changes | 60.0 ms | 58.7 ms |
| 1 source changed | 1.48 s | 4.14 s |
| 10 sources changed | 1.78 s | 4.62 s |

The Ninja path includes a timestamp-aware archive of the same object target so both sides perform compile + static-archive work. Object caching is disabled. Controlled source points fail unless both systems rebuild exactly the requested TU count.
