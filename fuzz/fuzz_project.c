#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

#ifndef C_FUZZ_INCLUDE_DIR
#define C_FUZZ_INCLUDE_DIR "include"
#endif

static bool fuzz_project_ready = false;
static char fuzz_project_root[PATH_MAX];
static char fuzz_project_repo[PATH_MAX];
static char fuzz_project_cache[PATH_MAX];

static const char fuzz_build_script[] =
    "#include <cbuild.h>\n"
    "#include <stdio.h>\n"
    "#include <stdlib.h>\n"
    "static unsigned char bytes[512];\n"
    "static size_t count, pos;\n"
    "static unsigned take(void) { return count ? bytes[(pos++) % count] : 0; }\n"
    "void build(C_Build *b) {\n"
    "  FILE *f = fopen(\"scenario.bin\", \"rb\");\n"
    "  if (f) { count = fread(bytes, 1, sizeof(bytes), f); fclose(f); }\n"
    "  C_Target *targets[4] = {0};\n"
    "  const char *names[4] = {\"app\", \"aux1\", \"aux2\", \"aux3\"};\n"
    "  unsigned nt = 1 + take() % 4;\n"
    "  for (unsigned i = 0; i < nt; ++i) {\n"
    "    targets[i] = c_executable(b, names[i]);\n"
    "    c_sources(targets[i], \"src/*.c\");\n"
    "    c_include(targets[i], \"src\");\n"
    "    if (take() & 1) c_define(targets[i], \"C_FUZZ_BUILD=1\");\n"
    "    switch (take() % 3) {\n"
    "      case 1: c_unity(targets[i], 2); break;\n"
    "      case 2: c_unity_auto(targets[i]); break;\n"
    "      default: c_no_unity(targets[i]); break;\n"
    "    }\n"
    "  }\n"
    "  c_default_target(b, targets[take() % nt]);\n"
    "  const char *repo = getenv(\"C_FUZZ_DEP_REPO\");\n"
    "  unsigned nd = repo ? take() % 5 : 0;\n"
    "  const char *depnames[4] = {\"dep0\", \"dep1\", \"dep2\", \"dep3\"};\n"
    "  for (unsigned i = 0; i < nd; ++i) {\n"
    "    C_Dependency *d = c_git(b, depnames[i], repo, \"HEAD\");\n"
    "    if (take() & 1) { c_dep_source(d); c_dep_sources(d, \"dep.c\"); }\n"
    "    else c_dep_header_only(d);\n"
    "    c_dep_include(d, \".\");\n"
    "    if (take() & 1) c_dep_flag(d, \"-DDEP_FUZZ=1\");\n"
    "    unsigned owner = take() % nt;\n"
    "    c_use(targets[owner], d);\n"
    "    if (owner != 0 && (take() & 1)) c_use(targets[0], d);\n"
    "  }\n"
    "}\n";

static int fuzz_run_args(const char *cwd, const char *const args[]) {
    StrVec v = {0};
    for (size_t i = 0; args[i]; ++i) vec_push(&v, args[i]);
    int rc = run_process(&v, false, cwd);
    vec_free(&v);
    return rc;
}

static void fuzz_project_git_init(void) {
    static const uint8_t dep_c[] = "int dep_value(void) { return 7; }\n";
    static const uint8_t dep_h[] = "int dep_value(void);\n";
    char path[PATH_MAX];

    mkdir_p(fuzz_project_repo);
    path_join(path, fuzz_project_repo, "dep.c");
    if (!fuzz_write_file(path, dep_c, sizeof(dep_c) - 1)) abort();
    path_join(path, fuzz_project_repo, "dep.h");
    if (!fuzz_write_file(path, dep_h, sizeof(dep_h) - 1)) abort();

    const char *init[] = {"git", "init", "-q", NULL};
    const char *add[] = {"git", "add", "dep.c", "dep.h", NULL};
    const char *commit[] = {
        "git", "-c", "user.name=c-fuzz", "-c", "user.email=c-fuzz@example.invalid",
        "commit", "-qm", "seed", NULL
    };
    if (fuzz_run_args(fuzz_project_repo, init) != 0) abort();
    if (fuzz_run_args(fuzz_project_repo, add) != 0) abort();
    if (fuzz_run_args(fuzz_project_repo, commit) != 0) abort();
}

static void fuzz_project_init(void) {
    if (fuzz_project_ready) return;

    char cwd[PATH_MAX];
    if (!getcwd(cwd, sizeof(cwd))) abort();
    path_join(fuzz_project_root, cwd, "project");
    path_join(fuzz_project_repo, cwd, "dep-repo");
    path_join(fuzz_project_cache, cwd, ".c-fuzz-project-cache");

    mkdir_p(fuzz_project_root);
    char src[PATH_MAX];
    path_join(src, fuzz_project_root, "src");
    mkdir_p(src);

    char build_path[PATH_MAX];
    path_join(build_path, fuzz_project_root, "build.c");
    if (!fuzz_write_file(build_path, (const uint8_t *)fuzz_build_script, strlen(fuzz_build_script))) abort();

    fuzz_project_git_init();
    if (setenv("C_CACHE_DIR", fuzz_project_cache, 1) != 0) abort();
    if (setenv("C_FUZZ_DEP_REPO", fuzz_project_repo, 1) != 0) abort();
    if (setenv("C_INCLUDE_DIR", C_FUZZ_INCLUDE_DIR, 1) != 0) abort();
    fuzz_project_ready = true;
}

static void fuzz_reset_runtime_caches(void) {
    for (size_t i = 0; i < COMPILER_PATH_CACHE_SIZE; ++i) {
        free(compiler_stat_cache[i].path);
        compiler_stat_cache[i].path = NULL;
        free(compiler_hash_cache[i].path);
        compiler_hash_cache[i].path = NULL;
    }
    memset(compiler_stat_cache, 0, sizeof(compiler_stat_cache));
    memset(compiler_hash_cache, 0, sizeof(compiler_hash_cache));
    compiler_profile_reset();
}

static void fuzz_project_write_sources(unsigned value, uint64_t salt) {
    char path[PATH_MAX];
    char text[512];

    path_join(path, fuzz_project_root, "src/shared.h");
    int n = snprintf(text, sizeof(text), "#define FUZZ_VALUE %u\n#define FUZZ_SALT %lluULL\n",
                     value, (unsigned long long)salt);
    if (n < 0 || n >= (int)sizeof(text) ||
        !fuzz_write_file(path, (const uint8_t *)text, (size_t)n)) abort();

    path_join(path, fuzz_project_root, "src/main.c");
    static const char main_c[] = "#include \"shared.h\"\nint main(void) { return FUZZ_VALUE; }\n";
    if (!fuzz_write_file(path, (const uint8_t *)main_c, sizeof(main_c) - 1)) abort();

    path_join(path, fuzz_project_root, "src/a.c");
    n = snprintf(text, sizeof(text), "#include \"shared.h\"\nunsigned long long fuzz_a(void) { return FUZZ_SALT + %lluULL; }\n",
                 (unsigned long long)(salt & 0xffffULL));
    if (n < 0 || n >= (int)sizeof(text) ||
        !fuzz_write_file(path, (const uint8_t *)text, (size_t)n)) abort();

    path_join(path, fuzz_project_root, "src/b.c");
    n = snprintf(text, sizeof(text), "#include \"shared.h\"\nunsigned long long fuzz_b(void) { return FUZZ_SALT ^ %lluULL; }\n",
                 (unsigned long long)((salt >> 16) & 0xffffULL));
    if (n < 0 || n >= (int)sizeof(text) ||
        !fuzz_write_file(path, (const uint8_t *)text, (size_t)n)) abort();
}

static int fuzz_run_built_app(bool release) {
    const char *path = release ? "./build/release/app" : "./build/debug/app";
    StrVec args = {0};
    vec_push(&args, path);
    int rc = compiler_run_process(&args, false);
    vec_free(&args);
    return rc;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 512) return 0;
    fuzz_project_init();

    unsigned expected = (unsigned)(fuzz_u64(data, size) % 64ULL);
    uint64_t salt = fuzz_u64(data + (size > 8 ? 8 : size), size > 8 ? size - 8 : 0);
    fuzz_project_write_sources(expected, salt);

    char scenario[PATH_MAX];
    path_join(scenario, fuzz_project_root, "scenario.bin");
    if (!fuzz_write_file(scenario, data, size)) return 0;

    char oldcwd[PATH_MAX];
    if (!getcwd(oldcwd, sizeof(oldcwd))) abort();
    if (chdir(fuzz_project_root) != 0) abort();

    fuzz_reset_runtime_caches();
    bool release = size > 0 && (data[0] & 1u);
    bool object_cache = size > 1 && (data[1] & 1u);
    unsigned unity = size > 2 ? data[2] % 3u : 0u;

    char *argv[12];
    int argc = 0;
    argv[argc++] = (char *)"c";
    argv[argc++] = (char *)"build";
    argv[argc++] = (char *)"--cc";
    argv[argc++] = (char *)"clang";
    argv[argc++] = (char *)"--jobs=2";
    argv[argc++] = object_cache ? (char *)"--object-cache" : (char *)"--no-object-cache";
    if (release) argv[argc++] = (char *)"--release";
    if (unity == 1) argv[argc++] = (char *)"--unity=2";
    else if (unity == 2) argv[argc++] = (char *)"--unity=auto";
    argv[argc] = NULL;

    if (compiler_dispatch(argc, argv) != 0) abort();
    int actual = fuzz_run_built_app(release);
    if (actual != (int)expected) abort();

    if (chdir(oldcwd) != 0) abort();
    return 0;
}
