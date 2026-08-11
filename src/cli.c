#define main c_legacy_main
#include "main.c"
#undef main

static bool cli_is_command(const char *s) {
    static const char *commands[] = {
        "init", "build", "run", "fetch", "update", "deps", "test",
        "clean", "cache", "doctor", "help", "--help", "-h",
        "version", "--version"
    };
    for (size_t i = 0; i < C_ARRAY_LEN(commands); ++i) {
        if (!strcmp(s, commands[i])) return true;
    }
    return false;
}

static bool cli_is_version_or_help(const char *s) {
    return !strcmp(s, "help") || !strcmp(s, "--help") || !strcmp(s, "-h") ||
           !strcmp(s, "version") || !strcmp(s, "--version");
}

static bool cli_is_action(const char *s) {
    return !strcmp(s, "init") || !strcmp(s, "build") || !strcmp(s, "run") ||
           !strcmp(s, "fetch") || !strcmp(s, "update") || !strcmp(s, "test") ||
           !strcmp(s, "clean") || !strcmp(s, "cache");
}

static bool cli_has_flag(int argc, char **argv, const char *a, const char *b) {
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--")) break;
        if (!strcmp(argv[i], a) || (b && !strcmp(argv[i], b))) return true;
        if (!strcmp(argv[i], "--cc") && i + 1 < argc) ++i;
    }
    return false;
}

static const char *cli_target(int argc, char **argv) {
    for (int i = 2; i < argc; ++i) {
        const char *arg = argv[i];
        if (!strcmp(arg, "--")) break;
        if (!strcmp(arg, "--release") || !strcmp(arg, "-Drelease") ||
            !strcmp(arg, "-v") || !strcmp(arg, "--verbose")) continue;
        if (!strcmp(arg, "--cc") && i + 1 < argc) { ++i; continue; }
        if (arg[0] != '-') return arg;
    }
    return NULL;
}

static bool cli_color(void) {
    const char *term = getenv("TERM");
    return isatty(STDERR_FILENO) && !getenv("NO_COLOR") &&
           (!term || strcmp(term, "dumb"));
}

static const char *cli_style(bool color, const char *code) {
    return color ? code : "";
}

static double cli_now_ms(void) {
    struct timespec ts = {0};
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0.0;
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1000000.0;
}

static const char *cli_step_name(const char *kind) {
    if (!strcmp(kind, "CONFIG")) return "configure";
    if (!strcmp(kind, "FETCH")) return "fetch";
    if (!strcmp(kind, "UPDATE")) return "update";
    if (!strcmp(kind, "DEP")) return "dependency";
    if (!strcmp(kind, "CC")) return "compile";
    if (!strcmp(kind, "AR")) return "archive";
    if (!strcmp(kind, "LINK")) return "link";
    if (!strcmp(kind, "CACHED")) return "cached";
    if (!strcmp(kind, "RUN")) return "run";
    if (!strcmp(kind, "DONE")) return "done";
    if (!strcmp(kind, "TEST")) return "test";
    if (!strcmp(kind, "PASS")) return "pass";
    if (!strcmp(kind, "CLEAN")) return "clean";
    if (!strcmp(kind, "INIT")) return "init";
    return NULL;
}

static bool cli_parse_note(const char *line, char kind[8], const char **message) {
    size_t n = strlen(line);
    if (n < 10 || line[0] != ' ' || line[1] != ' ' || line[9] != ' ') return false;
    memcpy(kind, line + 2, 7);
    kind[7] = '\0';
    for (int i = 6; i >= 0 && kind[i] == ' '; --i) kind[i] = '\0';
    if (!cli_step_name(kind)) return false;
    *message = line + 10;
    return true;
}

static void cli_heading(const char *command, int argc, char **argv) {
    if (!cli_is_action(command)) return;
    bool color = cli_color();
    const char *bold = cli_style(color, "\x1b[1m");
    const char *dim = cli_style(color, "\x1b[2m");
    const char *reset = cli_style(color, "\x1b[0m");
    const char *target = cli_target(argc, argv);

    fprintf(stderr, "%s%s%s", bold, command, reset);
    if (target && strcmp(command, "cache")) fprintf(stderr, " %s", target);
    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "test")) {
        fprintf(stderr, " %s[%s]%s", dim,
                cli_has_flag(argc, argv, "--release", "-Drelease") ? "release" : "debug",
                reset);
    }
    fputc('\n', stderr);
}

static void cli_step(const char *kind, const char *message) {
    bool color = cli_color();
    const char *dim = cli_style(color, "\x1b[2m");
    const char *cyan = cli_style(color, "\x1b[36m");
    const char *green = cli_style(color, "\x1b[32m");
    const char *reset = cli_style(color, "\x1b[0m");
    const char *name = cli_step_name(kind);
    const char *style = (!strcmp(kind, "CACHED")) ? dim :
                        (!strcmp(kind, "PASS") || !strcmp(kind, "DONE")) ? green : cyan;

    fprintf(stderr, "%s  ├─%s %s%-10s%s %s", dim, reset, style, name, reset, message);
    size_t n = strlen(message);
    if (!n || message[n - 1] != '\n') fputc('\n', stderr);
}

static void cli_finish(int rc, double elapsed_ms) {
    bool color = cli_color();
    const char *dim = cli_style(color, "\x1b[2m");
    const char *green = cli_style(color, "\x1b[32m");
    const char *red = cli_style(color, "\x1b[31m");
    const char *reset = cli_style(color, "\x1b[0m");

    if (rc == 0) {
        fprintf(stderr, "%s  └─%s %ssuccess%s %s%.0f ms%s\n",
                dim, reset, green, reset, dim, elapsed_ms, reset);
    } else {
        fprintf(stderr, "%s  └─%s %sfailed%s %s(exit %d, %.0f ms)%s\n",
                dim, reset, red, reset, dim, rc, elapsed_ms, reset);
    }
}

static bool cli_quiet_stdout(const char *command, const char *target) {
    if (!strcmp(command, "build") || !strcmp(command, "run") ||
        !strcmp(command, "fetch") || !strcmp(command, "update") ||
        !strcmp(command, "test") || !strcmp(command, "clean") ||
        !strcmp(command, "init")) return true;
    return !strcmp(command, "cache") && target && !strcmp(target, "clean");
}

static int cli_run_segment(int argc, char **argv) {
    const char *command = argc > 1 ? argv[1] : "help";
    const char *target = cli_target(argc, argv);
    bool action = cli_is_action(command);
    bool verbose = cli_has_flag(argc, argv, "-v", "--verbose");
    bool quiet = cli_quiet_stdout(command, target);
    bool show_program_output = false;
    double started = cli_now_ms();

    if (action) cli_heading(command, argc, argv);

    int fds[2];
    if (pipe(fds) != 0) {
        perror("pipe");
        return 1;
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        close(fds[0]);
        close(fds[1]);
        return 1;
    }

    if (pid == 0) {
        close(fds[0]);
        if (dup2(fds[1], STDOUT_FILENO) < 0) _exit(127);
        close(fds[1]);
        int rc = c_legacy_main(argc, argv);
        fflush(NULL);
        _exit(rc);
    }

    close(fds[1]);
    FILE *stream = fdopen(fds[0], "r");
    if (!stream) {
        close(fds[0]);
        waitpid(pid, NULL, 0);
        return 1;
    }

    char *line = NULL;
    size_t cap = 0;
    while (getline(&line, &cap, stream) >= 0) {
        char kind[8];
        const char *message = NULL;
        if (cli_parse_note(line, kind, &message)) {
            if (action) cli_step(kind, message);
            else fputs(line, stdout);
            if (!strcmp(kind, "RUN") || !strcmp(kind, "TEST")) show_program_output = true;
            continue;
        }
        if (!quiet || verbose || show_program_output) {
            fputs(line, stdout);
            fflush(stdout);
        }
    }
    free(line);
    fclose(stream);

    int status = 0;
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    int rc = 1;
    if (WIFEXITED(status)) rc = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) rc = 128 + WTERMSIG(status);

    if (action) cli_finish(rc, cli_now_ms() - started);

    if (rc == 0 && cli_is_version_or_help(command) &&
        (!strcmp(command, "help") || !strcmp(command, "--help") || !strcmp(command, "-h"))) {
        fputs("\nchaining:\n"
              "  c clean build run\n"
              "  c fetch build test\n\n"
              "Commands run left-to-right and stop on the first failure.\n"
              "Arguments after `--` belong to `c run` and end the command chain.\n",
              stdout);
    }

    return rc;
}

static bool cli_cache_clean_argument(int start, int i, char **argv) {
    return i == start + 1 && !strcmp(argv[start], "cache") && !strcmp(argv[i], "clean");
}

int main(int argc, char **argv) {
    if (argc < 2) return cli_run_segment(argc, argv);

    int start = 1;
    bool first_action = true;
    while (start < argc) {
        int end = argc;
        bool forwarded_args = false;
        for (int i = start + 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--")) {
                forwarded_args = true;
                break;
            }
            if (cli_is_command(argv[i]) && !cli_cache_clean_argument(start, i, argv)) {
                end = i;
                break;
            }
        }
        if (forwarded_args) end = argc;

        int seg_argc = 1 + (end - start);
        char **seg_argv = calloc((size_t)seg_argc + 1, sizeof(*seg_argv));
        if (!seg_argv) {
            fputs("c: error: out of memory\n", stderr);
            return 1;
        }
        seg_argv[0] = argv[0];
        for (int i = start; i < end; ++i) seg_argv[1 + i - start] = argv[i];

        bool segment_action = seg_argc > 1 && cli_is_action(seg_argv[1]);
        if (segment_action && !first_action) fputc('\n', stderr);
        if (segment_action) first_action = false;

        int rc = cli_run_segment(seg_argc, seg_argv);
        free(seg_argv);
        if (rc != 0) return rc;
        if (end >= argc) break;
        start = end;
    }
    return 0;
}
