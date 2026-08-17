#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

typedef enum BackendKind {
    BACKEND_NONE = 0,
    BACKEND_NATIVE,
    BACKEND_CMAKE,
    BACKEND_MAKE
} BackendKind;

typedef struct Backend {
    BackendKind kind;
    char source[PATH_MAX];
    bool converted_bridge;
} Backend;

typedef struct BuildArgs {
    const char *target;
    const char *cc;
    bool cc_cli;
    bool release;
    bool verbose;
    int jobs;
    int forwarded_index;
} BuildArgs;

static bool file_exists(const char *path) {
    struct stat st;
    return path && stat(path, &st) == 0 && S_ISREG(st.st_mode);
}

static void copy_string(char *dst, size_t cap, const char *src) {
    if (!cap) return;
    if (!src) src = "";
    snprintf(dst, cap, "%s", src);
}

static void path_join(char *out, size_t cap, const char *a, const char *b) {
    if (!a || !*a) snprintf(out, cap, "%s", b ? b : "");
    else if (!b || !*b) snprintf(out, cap, "%s", a);
    else if (a[strlen(a) - 1] == '/') snprintf(out, cap, "%s%s", a, b);
    else snprintf(out, cap, "%s/%s", a, b);
}

static int mkdir_p(const char *path) {
    char tmp[PATH_MAX];
    copy_string(tmp, sizeof(tmp), path);
    size_t n = strlen(tmp);
    if (!n) return 0;
    if (tmp[n - 1] == '/') tmp[n - 1] = '\0';
    for (char *p = tmp + 1; *p; ++p) {
        if (*p != '/') continue;
        *p = '\0';
        if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
        *p = '/';
    }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
    return 0;
}

static bool executable_path(char out[PATH_MAX]) {
#ifdef __APPLE__
    uint32_t size = PATH_MAX;
    char tmp[PATH_MAX];
    if (_NSGetExecutablePath(tmp, &size) != 0) return false;
    return realpath(tmp, out) != NULL;
#else
    ssize_t n = readlink("/proc/self/exe", out, PATH_MAX - 1);
    if (n <= 0) return false;
    out[n] = '\0';
    return true;
#endif
}

static bool native_path(char out[PATH_MAX]) {
    const char *override = getenv("C_NATIVE_BIN");
    if (override && *override && access(override, X_OK) == 0) {
        copy_string(out, PATH_MAX, override);
        return true;
    }

    char exe[PATH_MAX];
    if (executable_path(exe)) {
        char *slash = strrchr(exe, '/');
        if (slash) {
            *slash = '\0';
            char sibling[PATH_MAX];
            path_join(sibling, sizeof(sibling), exe, "c-native");
            if (access(sibling, X_OK) == 0) {
                copy_string(out, PATH_MAX, sibling);
                return true;
            }

            char prefix[PATH_MAX];
            path_join(prefix, sizeof(prefix), exe, "..");
            char libexec[PATH_MAX];
            path_join(libexec, sizeof(libexec), prefix, "libexec/c-buildsystem/c-native");
            if (access(libexec, X_OK) == 0) {
                copy_string(out, PATH_MAX, libexec);
                return true;
            }
        }
    }
    return false;
}

static int wait_status(pid_t pid) {
    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) continue;
        return 1;
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return 1;
}

static void print_command(char *const argv[]) {
    fputs("  $", stderr);
    for (size_t i = 0; argv[i]; ++i) fprintf(stderr, " %s", argv[i]);
    fputc('\n', stderr);
}

static int run_argv(char *const argv[], bool verbose) {
    if (verbose) print_command(argv);
    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "c: error: fork: %s\n", strerror(errno));
        return 1;
    }
    if (pid == 0) {
        execvp(argv[0], argv);
        fprintf(stderr, "c: error: cannot start %s: %s\n", argv[0], strerror(errno));
        _exit(127);
    }
    return wait_status(pid);
}

static int run_native(int argc, char **argv, bool replace) {
    char native[PATH_MAX];
    if (!native_path(native)) {
        fputs("c: error: cannot locate c-native; reinstall C-BuildSystem or set C_NATIVE_BIN\n", stderr);
        return 127;
    }

    char **args = calloc((size_t)argc + 1, sizeof(*args));
    if (!args) {
        fputs("c: error: out of memory\n", stderr);
        return 1;
    }
    args[0] = native;
    for (int i = 1; i < argc; ++i) args[i] = argv[i];

    if (replace) {
        execv(native, args);
        fprintf(stderr, "c: error: cannot start %s: %s\n", native, strerror(errno));
        free(args);
        return 127;
    }
    int rc = run_argv(args, false);
    free(args);
    return rc;
}

static const char *default_makefile(void) {
    static const char *names[] = {"GNUmakefile", "Makefile", "makefile"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
        if (file_exists(names[i])) return names[i];
    return NULL;
}

static void trim_line(char *s) {
    size_t n = strlen(s);
    while (n && (s[n - 1] == '\n' || s[n - 1] == '\r' || s[n - 1] == ' ' || s[n - 1] == '\t')) s[--n] = '\0';
    while (*s == ' ' || *s == '\t') memmove(s, s + 1, strlen(s));
}

static bool parse_bridge(Backend *out) {
    FILE *f = fopen("build.c", "r");
    if (!f) return false;
    char line[PATH_MAX + 128];
    char backend[32] = "";
    char source[PATH_MAX] = "";
    bool bridge_v1 = false;
    int lines = 0;
    while (lines++ < 80 && fgets(line, sizeof(line), f)) {
        if (strstr(line, "c-buildsystem:bridge=v1")) bridge_v1 = true;
        char *p = strstr(line, "c-buildsystem:backend=");
        if (p) {
            p += strlen("c-buildsystem:backend=");
            copy_string(backend, sizeof(backend), p);
            trim_line(backend);
            char *end = strpbrk(backend, " */");
            if (end) *end = '\0';
        }
        p = strstr(line, "c-buildsystem:source=");
        if (p) {
            p += strlen("c-buildsystem:source=");
            copy_string(source, sizeof(source), p);
            trim_line(source);
            char *end = strstr(source, " */");
            if (end) *end = '\0';
            else {
                end = strchr(source, '*');
                if (end) *end = '\0';
                trim_line(source);
            }
        }
    }
    fclose(f);

    if (!bridge_v1) return false;
    if (!strcmp(backend, "cmake")) out->kind = BACKEND_CMAKE;
    else if (!strcmp(backend, "make")) out->kind = BACKEND_MAKE;
    else return false;
    if (!*source) copy_string(source, sizeof(source), out->kind == BACKEND_CMAKE ? "CMakeLists.txt" : "Makefile");
    copy_string(out->source, sizeof(out->source), source);
    out->converted_bridge = true;
    return true;
}

static Backend detect_backend(void) {
    Backend out = {0};
    if (file_exists("build.c")) {
        if (parse_bridge(&out)) return out;
        out.kind = BACKEND_NATIVE;
        copy_string(out.source, sizeof(out.source), "build.c");
        return out;
    }
    if (file_exists("CMakeLists.txt")) {
        out.kind = BACKEND_CMAKE;
        copy_string(out.source, sizeof(out.source), "CMakeLists.txt");
        return out;
    }
    const char *mk = default_makefile();
    if (mk) {
        out.kind = BACKEND_MAKE;
        copy_string(out.source, sizeof(out.source), mk);
    }
    return out;
}

static int default_jobs(void) {
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    if (n < 1) n = 1;
    n /= 2;
    if (n < 1) n = 1;
    if (n > 1024) n = 1024;
    return (int)n;
}

static bool parse_positive(const char *s, int *out) {
    if (!s || !*s) return false;
    char *end = NULL;
    errno = 0;
    long n = strtol(s, &end, 10);
    if (errno || !end || *end || n < 1 || n > 1024) return false;
    *out = (int)n;
    return true;
}

static int parse_build_args(int argc, char **argv, BuildArgs *out) {
    memset(out, 0, sizeof(*out));
    out->jobs = default_jobs();
    out->cc = getenv("CC");
    if (out->cc && !*out->cc) out->cc = NULL;
    out->forwarded_index = argc;

    for (int i = 2; i < argc; ++i) {
        const char *arg = argv[i];
        if (!strcmp(arg, "--")) {
            out->forwarded_index = i + 1;
            return 0;
        }
        if (!strcmp(arg, "--release") || !strcmp(arg, "-Drelease")) {
            out->release = true;
            continue;
        }
        if (!strcmp(arg, "-v") || !strcmp(arg, "--verbose")) {
            out->verbose = true;
            continue;
        }
        if (!strcmp(arg, "--cc")) {
            if (++i >= argc) {
                fputs("c: error: --cc requires a value\n", stderr);
                return 2;
            }
            out->cc = argv[i];
            out->cc_cli = true;
            continue;
        }
        if (!strcmp(arg, "-j") || !strcmp(arg, "--jobs")) {
            if (++i >= argc || !parse_positive(argv[i], &out->jobs)) {
                fputs("c: error: jobs requires a positive integer\n", stderr);
                return 2;
            }
            continue;
        }
        if (!strncmp(arg, "-j", 2) && arg[2]) {
            if (!parse_positive(arg + 2, &out->jobs)) {
                fprintf(stderr, "c: error: invalid jobs: %s\n", arg + 2);
                return 2;
            }
            continue;
        }
        if (!strncmp(arg, "--jobs=", 7)) {
            if (!parse_positive(arg + 7, &out->jobs)) {
                fprintf(stderr, "c: error: invalid jobs: %s\n", arg + 7);
                return 2;
            }
            continue;
        }
        if (arg[0] == '-') {
            fprintf(stderr, "c: error: wrapper backend does not understand %s; pass backend-specific arguments after `--`\n", arg);
            return 2;
        }
        if (!out->target) out->target = arg;
        else {
            fprintf(stderr, "c: error: multiple wrapper targets: %s and %s\n", out->target, arg);
            return 2;
        }
    }
    return 0;
}

static void cmake_source_dir(const Backend *backend, char out[PATH_MAX]) {
    copy_string(out, PATH_MAX, backend->source);
    char *slash = strrchr(out, '/');
    if (slash) {
        *slash = '\0';
        if (!*out) copy_string(out, PATH_MAX, ".");
    } else copy_string(out, PATH_MAX, ".");
}

static void cmake_build_dir(bool release, char out[PATH_MAX]) {
    const char *override = getenv("C_CMAKE_BUILD_DIR");
    if (override && *override) {
        copy_string(out, PATH_MAX, override);
        return;
    }
    copy_string(out, PATH_MAX, release ? ".c-build/cmake/release" : ".c-build/cmake/debug");
}

static int ensure_cmake_configured(const Backend *backend, const BuildArgs *opt, char build_dir[PATH_MAX]) {
    cmake_build_dir(opt->release, build_dir);
    if (mkdir_p(build_dir) != 0) {
        fprintf(stderr, "c: error: cannot create %s: %s\n", build_dir, strerror(errno));
        return 1;
    }
    char cache[PATH_MAX];
    path_join(cache, sizeof(cache), build_dir, "CMakeCache.txt");
    if (file_exists(cache)) return 0;

    char source_dir[PATH_MAX];
    cmake_source_dir(backend, source_dir);
    char type[64];
    snprintf(type, sizeof(type), "-DCMAKE_BUILD_TYPE=%s", opt->release ? "Release" : "Debug");
    char compiler[PATH_MAX + 64];
    char *cmd[10] = {0};
    size_t n = 0;
    cmd[n++] = "cmake";
    cmd[n++] = "-S";
    cmd[n++] = source_dir;
    cmd[n++] = "-B";
    cmd[n++] = build_dir;
    cmd[n++] = type;
    cmd[n++] = "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON";
    if (opt->cc_cli) {
        snprintf(compiler, sizeof(compiler), "-DCMAKE_C_COMPILER=%s", opt->cc);
        cmd[n++] = compiler;
    }
    cmd[n] = NULL;
    fprintf(stderr, "c: CMake wrapper -> configure %s\n", build_dir);
    return run_argv(cmd, opt->verbose);
}

static int cmake_build(const Backend *backend, int argc, char **argv) {
    BuildArgs opt;
    int rc = parse_build_args(argc, argv, &opt);
    if (rc) return rc;

    char build_dir[PATH_MAX];
    rc = ensure_cmake_configured(backend, &opt, build_dir);
    if (rc) return rc;

    char jobs[32];
    snprintf(jobs, sizeof(jobs), "%d", opt.jobs);
    size_t extra = opt.forwarded_index < argc ? (size_t)(argc - opt.forwarded_index) : 0;
    size_t cap = 16 + extra;
    char **cmd = calloc(cap, sizeof(*cmd));
    if (!cmd) return 1;
    size_t n = 0;
    cmd[n++] = "cmake";
    cmd[n++] = "--build";
    cmd[n++] = build_dir;
    cmd[n++] = "--parallel";
    cmd[n++] = jobs;
    cmd[n++] = "--config";
    cmd[n++] = opt.release ? "Release" : "Debug";
    if (opt.target) {
        cmd[n++] = "--target";
        cmd[n++] = (char *)opt.target;
    }
    if (opt.verbose) cmd[n++] = "--verbose";
    if (extra) {
        cmd[n++] = "--";
        for (int i = opt.forwarded_index; i < argc; ++i) cmd[n++] = argv[i];
    }
    cmd[n] = NULL;
    fprintf(stderr, "c: CMake wrapper -> build%s%s\n", opt.target ? " target " : "", opt.target ? opt.target : "");
    rc = run_argv(cmd, opt.verbose);
    free(cmd);
    return rc;
}

static int make_build(const Backend *backend, int argc, char **argv, const char *forced_target) {
    BuildArgs opt;
    int rc = parse_build_args(argc, argv, &opt);
    if (rc) return rc;
    if (opt.release) {
        fputs("c: error: --release has no portable Makefile meaning; pass the project's release variable after `--`\n", stderr);
        return 2;
    }

    const char *make = getenv("MAKE");
    if (!make || !*make) make = "make";
    char jobs[32];
    snprintf(jobs, sizeof(jobs), "-j%d", opt.jobs);
    char ccarg[PATH_MAX + 8];
    if (opt.cc_cli) snprintf(ccarg, sizeof(ccarg), "CC=%s", opt.cc);
    size_t extra = opt.forwarded_index < argc ? (size_t)(argc - opt.forwarded_index) : 0;
    char **cmd = calloc(12 + extra, sizeof(*cmd));
    if (!cmd) return 1;
    size_t n = 0;
    cmd[n++] = (char *)make;
    if (strcmp(backend->source, "Makefile") && strcmp(backend->source, "GNUmakefile") && strcmp(backend->source, "makefile")) {
        cmd[n++] = "-f";
        cmd[n++] = (char *)backend->source;
    }
    cmd[n++] = jobs;
    if (opt.cc_cli) cmd[n++] = ccarg;
    if (forced_target) cmd[n++] = (char *)forced_target;
    else if (opt.target) cmd[n++] = (char *)opt.target;
    for (int i = opt.forwarded_index; i < argc; ++i) cmd[n++] = argv[i];
    cmd[n] = NULL;
    fprintf(stderr, "c: Make wrapper -> %s%s%s\n", forced_target ? forced_target : opt.target ? "target " : "build", forced_target ? "" : opt.target ? opt.target : "", "");
    rc = run_argv(cmd, opt.verbose);
    free(cmd);
    return rc;
}

static int cmake_clean(void) {
    const char *override = getenv("C_CMAKE_BUILD_DIR");
    const char *dirs[] = {".c-build/cmake/debug", ".c-build/cmake/release"};
    bool any = false;
    int rc = 0;
    size_t count = override && *override ? 1 : sizeof(dirs) / sizeof(dirs[0]);
    for (size_t i = 0; i < count; ++i) {
        const char *dir = override && *override ? override : dirs[i];
        char cache[PATH_MAX];
        path_join(cache, sizeof(cache), dir, "CMakeCache.txt");
        if (!file_exists(cache)) continue;
        any = true;
        char *cmd[] = {"cmake", "--build", (char *)dir, "--target", "clean", NULL};
        int one = run_argv(cmd, false);
        if (one && !rc) rc = one;
    }
    if (!any) fputs("c: CMake wrapper -> nothing configured yet\n", stderr);
    return rc;
}

static int cmake_test(const Backend *backend, int argc, char **argv) {
    BuildArgs opt;
    int rc = parse_build_args(argc, argv, &opt);
    if (rc) return rc;
    char build_dir[PATH_MAX];
    rc = ensure_cmake_configured(backend, &opt, build_dir);
    if (rc) return rc;

    char jobs[32];
    snprintf(jobs, sizeof(jobs), "%d", opt.jobs);
    char *build_cmd[] = {"cmake", "--build", build_dir, "--parallel", jobs, "--config", opt.release ? "Release" : "Debug", NULL};
    rc = run_argv(build_cmd, opt.verbose);
    if (rc) return rc;

    size_t extra = opt.forwarded_index < argc ? (size_t)(argc - opt.forwarded_index) : 0;
    char **cmd = calloc(12 + extra, sizeof(*cmd));
    if (!cmd) return 1;
    size_t n = 0;
    cmd[n++] = "ctest";
    cmd[n++] = "--test-dir";
    cmd[n++] = build_dir;
    cmd[n++] = "--output-on-failure";
    cmd[n++] = "-C";
    cmd[n++] = opt.release ? "Release" : "Debug";
    if (opt.target) {
        cmd[n++] = "-R";
        cmd[n++] = (char *)opt.target;
    }
    for (int i = opt.forwarded_index; i < argc; ++i) cmd[n++] = argv[i];
    cmd[n] = NULL;
    rc = run_argv(cmd, opt.verbose);
    free(cmd);
    return rc;
}

static int write_bridge(const Backend *backend, bool force) {
    if (file_exists("build.c") && !force) {
        fputs("c: error: build.c already exists (use `c convert --force` to replace it)\n", stderr);
        return 2;
    }

    const char *kind = backend->kind == BACKEND_CMAKE ? "cmake" : "make";
    char text[PATH_MAX + 1024];
    int n = snprintf(
        text, sizeof(text),
        "#include <cbuild.h>\n\n"
        "/*\n"
        " * Generated by `c convert`.\n"
        " * Compatibility bridge: the original build configuration remains authoritative.\n"
        " * c-buildsystem:bridge=v1\n"
        " * c-buildsystem:backend=%s\n"
        " * c-buildsystem:source=%s\n"
        " */\n"
        "void build(C_Build *b) {\n"
        "    (void)b;\n"
        "}\n",
        kind, backend->source
    );
    if (n < 0 || (size_t)n >= sizeof(text)) {
        fputs("c: error: converted build.c is too large\n", stderr);
        return 1;
    }

    int flags = O_WRONLY | O_CREAT | O_TRUNC;
    if (!force) flags |= O_EXCL;
    int fd = open("build.c", flags, 0644);
    if (fd < 0) {
        fprintf(stderr, "c: error: cannot write build.c: %s\n", strerror(errno));
        return 1;
    }
    size_t len = strlen(text);
    ssize_t wrote = write(fd, text, len);
    int saved = errno;
    if (close(fd) != 0 || wrote != (ssize_t)len) {
        fprintf(stderr, "c: error: cannot write build.c: %s\n", strerror(saved));
        return 1;
    }
    printf("converted %s -> build.c (%s compatibility bridge)\n", backend->source, kind);
    return 0;
}

static int convert_command(int argc, char **argv) {
    bool force = false;
    const char *source = NULL;
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--force")) force = true;
        else if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) {
            puts("usage: c convert [CMakeLists.txt|Makefile] [--force]\n\nCreates a build.c compatibility bridge. The original CMake/Make configuration stays authoritative, so existing project behavior is preserved.");
            return 0;
        } else if (argv[i][0] == '-') {
            fprintf(stderr, "c: error: unknown convert option: %s\n", argv[i]);
            return 2;
        } else if (!source) source = argv[i];
        else {
            fputs("c: error: c convert accepts one build configuration path\n", stderr);
            return 2;
        }
    }

    Backend backend = {0};
    if (source) {
        if (!file_exists(source)) {
            fprintf(stderr, "c: error: %s not found\n", source);
            return 2;
        }
        const char *base = strrchr(source, '/');
        base = base ? base + 1 : source;
        if (!strcmp(base, "CMakeLists.txt")) backend.kind = BACKEND_CMAKE;
        else backend.kind = BACKEND_MAKE;
        copy_string(backend.source, sizeof(backend.source), source);
    } else {
        if (file_exists("CMakeLists.txt")) {
            backend.kind = BACKEND_CMAKE;
            copy_string(backend.source, sizeof(backend.source), "CMakeLists.txt");
        } else {
            const char *mk = default_makefile();
            if (mk) {
                backend.kind = BACKEND_MAKE;
                copy_string(backend.source, sizeof(backend.source), mk);
            }
        }
    }
    if (backend.kind == BACKEND_NONE) {
        fputs("c: error: no CMakeLists.txt, GNUmakefile, Makefile, or makefile found\n", stderr);
        return 2;
    }
    return write_bridge(&backend, force);
}

static bool is_help(const char *cmd) {
    return !strcmp(cmd, "help") || !strcmp(cmd, "--help") || !strcmp(cmd, "-h");
}

static void print_wrapper_help(void) {
    puts("\nexisting-project compatibility:\n"
         "  c build [target]            use build.c, or auto-wrap CMake/Make\n"
         "  c test [name]               ctest for CMake, `make test` for Make\n"
         "  c clean                     clean the detected backend\n"
         "  c convert [file] [--force]  create a build.c compatibility bridge\n\n"
         "backend arguments:\n"
         "  c build target -- <args>    forward args to CMake's native build tool or Make\n\n"
         "backend priority:\n"
         "  build.c > CMakeLists.txt > GNUmakefile > Makefile > makefile\n");
}

int main(int argc, char **argv) {
    const char *command = argc > 1 ? argv[1] : "help";
    if (!strcmp(command, "convert")) return convert_command(argc, argv);

    Backend backend = detect_backend();
    if (backend.kind == BACKEND_NATIVE) return run_native(argc, argv, true);

    if (is_help(command)) {
        int rc = run_native(argc, argv, false);
        if (rc == 0) print_wrapper_help();
        return rc;
    }

    if (!strcmp(command, "build")) {
        if (backend.kind == BACKEND_CMAKE) return cmake_build(&backend, argc, argv);
        if (backend.kind == BACKEND_MAKE) return make_build(&backend, argc, argv, NULL);
        fputs("c: error: no build.c, CMakeLists.txt, GNUmakefile, Makefile, or makefile found\n", stderr);
        return 2;
    }

    if (!strcmp(command, "clean")) {
        if (backend.kind == BACKEND_CMAKE) return cmake_clean();
        if (backend.kind == BACKEND_MAKE) return make_build(&backend, argc, argv, "clean");
    }

    if (!strcmp(command, "test")) {
        if (backend.kind == BACKEND_CMAKE) return cmake_test(&backend, argc, argv);
        if (backend.kind == BACKEND_MAKE) return make_build(&backend, argc, argv, "test");
    }

    if ((backend.kind == BACKEND_CMAKE || backend.kind == BACKEND_MAKE) &&
        (!strcmp(command, "run") || !strcmp(command, "watch"))) {
        fprintf(stderr, "c: error: `%s` cannot be mapped portably through a %s backend; use `c build [target]` or write a native build.c\n",
                command, backend.kind == BACKEND_CMAKE ? "CMake" : "Make");
        return 2;
    }

    return run_native(argc, argv, true);
}
