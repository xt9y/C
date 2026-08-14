# cJSON overhead benchmark

Pinned cJSON v1.7.19, one C translation unit. Lower is better.

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Fresh build-system setup | 57.3 ms | 203.1 ms |
| Clean build | 167.5 ms | 213.7 ms |
| No changes | 4.1 ms | 5.2 ms |
| One source changed | 167.9 ms | 215.5 ms |

No-op is the median of 30 runs. Object caching is disabled. Both systems rebuild exactly one TU after the source edit.
