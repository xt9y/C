#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

static bool fuzz_cache_ready = false;
static CompilerStamp fuzz_source_stamp;
static CompilerStamp fuzz_dep_stamp;
static char fuzz_hash_meta[PATH_MAX];
static char fuzz_dep_meta[PATH_MAX];
static char fuzz_time_meta[PATH_MAX];

static void fuzz_cache_init(void) {
    if (fuzz_cache_ready) return;
    if (setenv("C_CACHE_DIR", ".c-fuzz-cache", 1) != 0) abort();

    static const uint8_t source[] = "int fuzz_source(void) { return 1; }\n";
    static const uint8_t depfile[] = "build/fuzz.o: source.c include/fuzz.h\n";
    if (!fuzz_write_file("source.c", source, sizeof(source) - 1)) abort();
    if (!fuzz_write_file("input.d", depfile, sizeof(depfile) - 1)) abort();

    fuzz_source_stamp = compiler_stat_now("source.c");
    fuzz_dep_stamp = compiler_stat_now("input.d");
    if (!fuzz_source_stamp.exists || !fuzz_dep_stamp.exists) abort();

    compiler_perf_cache_path("hash", "source.c", ".hash", fuzz_hash_meta);
    compiler_perf_cache_path("deps", "input.d", ".deps", fuzz_dep_meta);
    compiler_perf_cache_path("timings", "source.c", ".time", fuzz_time_meta);
    fuzz_cache_ready = true;
}

static void fuzz_hash_cache(const uint8_t *data, size_t size) {
    uint64_t out = 0;
    if (fuzz_write_file(fuzz_hash_meta, data, size)) {
        (void)compiler_persistent_hash_lookup(
            "source.c",
            fuzz_source_stamp.sec,
            fuzz_source_stamp.nsec,
            fuzz_source_stamp.size,
            &out);
    }

    FILE *f = fopen(fuzz_hash_meta, "wb");
    if (!f) return;
    fprintf(f, "%lld %ld %lld %016llx\n",
            (long long)fuzz_source_stamp.sec,
            fuzz_source_stamp.nsec,
            (long long)fuzz_source_stamp.size,
            (unsigned long long)fuzz_u64(data, size));
    if (size) fwrite(data, 1, size, f);
    fputc('\n', f);
    fclose(f);

    (void)compiler_persistent_hash_lookup(
        "source.c",
        fuzz_source_stamp.sec,
        fuzz_source_stamp.nsec,
        fuzz_source_stamp.size,
        &out);
}

static void fuzz_dep_cache(const uint8_t *data, size_t size) {
    StrVec deps = {0};
    if (fuzz_write_file(fuzz_dep_meta, data, size)) {
        (void)compiler_dep_cache_load("input.d", &deps);
        vec_free(&deps);
    }

    FILE *f = fopen(fuzz_dep_meta, "wb");
    if (!f) return;
    fprintf(f, "%lld %ld %lld\n",
            (long long)fuzz_dep_stamp.sec,
            fuzz_dep_stamp.nsec,
            (long long)fuzz_dep_stamp.size);
    if (size) fwrite(data, 1, size, f);
    fputc('\n', f);
    fclose(f);

    deps = (StrVec){0};
    (void)compiler_dep_cache_load("input.d", &deps);
    for (size_t i = 0; i < deps.count; ++i) {
        if (!deps.items[i]) abort();
    }
    vec_free(&deps);
}

static void fuzz_history_cache(const uint8_t *data, size_t size) {
    if (!fuzz_write_file(fuzz_time_meta, data, size)) return;
    (void)compiler_history_read("source.c");

    double sample_ms = (double)(fuzz_u64(data, size) % 1000000ULL) / 1000.0 + 0.001;
    compiler_profile_reset();
    compiler_history_record("source.c", sample_ms);
    (void)compiler_history_read("source.c");
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 1024 * 1024) return 0;
    fuzz_cache_init();
    fuzz_hash_cache(data, size);
    fuzz_dep_cache(data, size);
    fuzz_history_cache(data, size);
    return 0;
}
