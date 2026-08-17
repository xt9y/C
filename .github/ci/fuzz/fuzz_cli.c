#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

static unsigned fuzz_take(const uint8_t *data, size_t size, size_t *pos) {
    if (!size) return 0;
    unsigned value = data[*pos % size];
    ++*pos;
    return value;
}

static void fuzz_cli_clear_env(void) {
    static const char *vars[] = {
        "C_JOBS", "C_UNITY", "C_OBJECT_CACHE", "C_PROFILE",
        "C_FAST_DEBUG", "C_ADAPTIVE_JOBS", "C_LINKER"
    };
    for (size_t i = 0; i < sizeof(vars) / sizeof(vars[0]); ++i) {
        if (unsetenv(vars[i]) != 0) abort();
    }
}

static void fuzz_cli_defaults(const uint8_t *data, size_t size, size_t *pos) {
    char jobs[8];
    char unity[8];
    unsigned j = 1u + fuzz_take(data, size, pos) % 64u;
    unsigned u = 2u + fuzz_take(data, size, pos) % 15u;
    snprintf(jobs, sizeof(jobs), "%u", j);
    snprintf(unity, sizeof(unity), "%u", u);

    fuzz_cli_clear_env();
    if (fuzz_take(data, size, pos) & 1u) setenv("C_JOBS", jobs, 1);
    if (fuzz_take(data, size, pos) & 1u) {
        setenv("C_UNITY", (fuzz_take(data, size, pos) & 1u) ? "auto" : unity, 1);
    }
    if (fuzz_take(data, size, pos) & 1u) setenv("C_OBJECT_CACHE", "off", 1);
    if (fuzz_take(data, size, pos) & 1u) setenv("C_PROFILE", "1", 1);
    if (fuzz_take(data, size, pos) & 1u) setenv("C_FAST_DEBUG", "1", 1);
    if (fuzz_take(data, size, pos) & 1u) setenv("C_ADAPTIVE_JOBS", "1", 1);
    if (fuzz_take(data, size, pos) & 1u) setenv("C_LINKER", "lld", 1);

    compiler_perf_defaults();
    if (compiler_perf.jobs < 1 || compiler_perf.jobs > 1024) abort();
    if (compiler_perf.unity != -1 && compiler_perf.unity != 0 && compiler_perf.unity < 2) abort();
}

static void fuzz_cli_filter(const uint8_t *data, size_t size, size_t *pos) {
    char jobs_short[16];
    char jobs_long[16];
    char unity[16];
    char linker[24];
    unsigned jobs = 1u + fuzz_take(data, size, pos) % 64u;
    unsigned chunk = 2u + fuzz_take(data, size, pos) % 15u;
    snprintf(jobs_short, sizeof(jobs_short), "-j%u", jobs);
    snprintf(jobs_long, sizeof(jobs_long), "--jobs=%u", jobs);
    snprintf(unity, sizeof(unity), "--unity=%u", chunk);
    snprintf(linker, sizeof(linker), "--linker=%s", (fuzz_take(data, size, pos) & 1u) ? "lld" : "mold");

    char *argv[32];
    int argc = 0;
    argv[argc++] = (char *)"c";
    argv[argc++] = (char *)"build";
    argv[argc++] = (char *)"app";

    switch (fuzz_take(data, size, pos) % 4u) {
        case 0: argv[argc++] = jobs_short; break;
        case 1:
            argv[argc++] = (char *)"--jobs";
            argv[argc++] = jobs_short + 2;
            break;
        case 2: argv[argc++] = jobs_long; break;
        default: break;
    }

    switch (fuzz_take(data, size, pos) % 4u) {
        case 0: argv[argc++] = (char *)"--unity"; break;
        case 1: argv[argc++] = (char *)"--unity=auto"; break;
        case 2: argv[argc++] = unity; break;
        default: argv[argc++] = (char *)"--no-unity"; break;
    }

    argv[argc++] = (fuzz_take(data, size, pos) & 1u) ? (char *)"--object-cache" : (char *)"--no-object-cache";
    if (fuzz_take(data, size, pos) & 1u) argv[argc++] = (char *)"--profile";
    if (fuzz_take(data, size, pos) & 1u) argv[argc++] = (char *)"--fast-debug";
    argv[argc++] = (fuzz_take(data, size, pos) & 1u) ? (char *)"--adaptive-jobs" : (char *)"--no-adaptive-jobs";

    if (fuzz_take(data, size, pos) & 1u) {
        argv[argc++] = (char *)"--linker";
        argv[argc++] = (char *)"lld";
    } else {
        argv[argc++] = linker;
    }

    bool forwarded = (fuzz_take(data, size, pos) & 1u) != 0;
    if (forwarded) {
        argv[argc++] = (char *)"--";
        argv[argc++] = (char *)"-j0";
        argv[argc++] = (char *)"--unity=1";
    }
    argv[argc] = NULL;

    compiler_perf_defaults();
    int filtered_argc = 0;
    char **filtered = compiler_filter_perf_options(argc, argv, &filtered_argc);
    if (!filtered || filtered_argc < 3) abort();
    if (strcmp(filtered[0], "c") || strcmp(filtered[1], "build") || strcmp(filtered[2], "app")) abort();

    if (forwarded) {
        bool saw_dashdash = false;
        bool saw_j0 = false;
        bool saw_unity1 = false;
        for (int i = 0; i < filtered_argc; ++i) {
            if (!strcmp(filtered[i], "--")) saw_dashdash = true;
            if (!strcmp(filtered[i], "-j0")) saw_j0 = true;
            if (!strcmp(filtered[i], "--unity=1")) saw_unity1 = true;
        }
        if (!saw_dashdash || !saw_j0 || !saw_unity1) abort();
    }

    if (compiler_perf.jobs < 1 || compiler_perf.jobs > 1024) abort();
    if (compiler_perf.unity != -1 && compiler_perf.unity != 0 && compiler_perf.unity < 2) abort();
    free(filtered);
}

static void fuzz_cli_source_kinds(const uint8_t *data, size_t size, size_t *pos) {
    static const char *sources[] = {
        "a.c", "b.cpp", "c.cc", "d.cxx", "e.mm", "noext", "odd.C"
    };
    const char *source = sources[fuzz_take(data, size, pos) % (sizeof(sources) / sizeof(sources[0]))];
    bool cpp = compiler_cpp_source(source);
    const char *ext = strrchr(source, '.');
    bool expected = ext && (!strcmp(ext, ".cpp") || !strcmp(ext, ".cc") || !strcmp(ext, ".cxx") || !strcmp(ext, ".mm"));
    if (cpp != expected) abort();

    if (!compiler_c_standard_flag("-std=c11")) abort();
    if (compiler_c_standard_flag("-std=gnu11")) abort();
    if (compiler_cpp_standard_flag("-std=gnu11")) abort();
    if (compiler_c_standard_flag("-std=c++20")) abort();
    if (!compiler_cpp_standard_flag("-std=c++20")) abort();
    if (!compiler_cpp_standard_flag("-std=gnu++17")) abort();
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 512) return 0;
    size_t pos = 0;
    fuzz_cli_defaults(data, size, &pos);
    fuzz_cli_filter(data, size, &pos);
    fuzz_cli_source_kinds(data, size, &pos);
    fuzz_cli_clear_env();
    return 0;
}
