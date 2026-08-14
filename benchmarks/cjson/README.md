# cJSON overhead benchmark

Pinned cJSON v1.7.19, one C translation unit. Lower is better.

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Fresh build-system setup | 58.6 ms | 214.4 ms |
| Clean build | 169.1 ms | 217.6 ms |
| No changes | 4.1 ms | 5.2 ms |
| One source changed | 170.5 ms | 220.0 ms |

No-op is the median of 30 runs. Object caching is disabled. Both systems rebuild exactly one TU after the source edit.
