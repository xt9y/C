# libcurl header fan-out benchmark

Pinned libcurl curl-8_21_0. A harmless content change is made to `lib/curl_setup.h`. Both systems must invalidate the same number of translation units.

- Target translation units: **192**
- Translation units invalidated: **192**

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| No changes | 13.0 ms | 15.4 ms |
| Header fan-out rebuild | 6.50 s | 6.74 s |
| Invocation to first compiler | 22.6 ms | 18.7 ms |
| Clean build | 6.48 s | 6.71 s |

Object caching is disabled. Fan-out wall time is the median of 3 runs; no-op is the median of 10.
