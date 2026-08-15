#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

static void fuzz_check_deps(const StrVec *deps) {
    for (size_t i = 0; i < deps->count; ++i) {
        if (!deps->items[i]) abort();
        size_t n = strlen(deps->items[i]);
        if (n == 0 || n >= PATH_MAX) abort();
    }
}

static bool fuzz_deps_equal(const StrVec *a, const StrVec *b) {
    if (a->count != b->count) return false;
    for (size_t i = 0; i < a->count; ++i) {
        if (strcmp(a->items[i], b->items[i])) return false;
    }
    return true;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 1024 * 1024) return 0;
    if (!fuzz_write_file("input.d", data, size)) return 0;

    StrVec first = {0};
    StrVec second = {0};
    bool ok_first = compiler_read_depfile("input.d", &first);
    bool ok_second = compiler_read_depfile("input.d", &second);

    fuzz_check_deps(&first);
    fuzz_check_deps(&second);
    if (ok_first != ok_second || !fuzz_deps_equal(&first, &second)) abort();

    vec_free(&first);
    vec_free(&second);
    unlink("input.d");
    return 0;
}
