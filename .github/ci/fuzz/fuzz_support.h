#ifndef C_FUZZ_SUPPORT_H
#define C_FUZZ_SUPPORT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

static bool fuzz_write_file(const char *path, const uint8_t *data, size_t size) {
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    bool ok = size == 0 || fwrite(data, 1, size, f) == size;
    if (fclose(f) != 0) ok = false;
    return ok;
}

static uint64_t fuzz_u64(const uint8_t *data, size_t size) {
    uint64_t value = 0;
    size_t n = size < sizeof(value) ? size : sizeof(value);
    for (size_t i = 0; i < n; ++i) value |= (uint64_t)data[i] << (i * 8);
    return value;
}

#endif
