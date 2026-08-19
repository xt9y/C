from pathlib import Path

p = Path('src/main.c')
s = p.read_text()
old = '''    char inc[PATH_MAX + 3]; snprintf(inc, sizeof(inc), "-I%s", script_dir); vec_push(&a, inc);
    vec_push(&a, "build.c");
    vec_push(&a, "-o"); vec_push(&a, so_path);
    note("CONFIG", "build.c");
    if (run_process(&a, opt->verbose, NULL) != 0) die("failed to compile build.c");
    vec_free(&a);
}'''
new = '''    char inc[PATH_MAX + 3]; snprintf(inc, sizeof(inc), "-I%s", script_dir); vec_push(&a, inc);
    vec_push(&a, "build.c");
    char temp_so[PATH_MAX];
    if (snprintf(temp_so, sizeof(temp_so), "%s.tmp.%ld", so_path, (long)getpid()) >= (int)sizeof(temp_so))
        die("build script cache path too long");
    vec_push(&a, "-o"); vec_push(&a, temp_so);
    note("CONFIG", "build.c");
    int rc = run_process(&a, opt->verbose, NULL);
    vec_free(&a);
    if (rc != 0) {
        unlink(temp_so);
        die("failed to compile build.c");
    }
    if (rename(temp_so, so_path) != 0) {
        unlink(temp_so);
        die("cannot publish compiled build.c: %s", strerror(errno));
    }
}'''
if s.count(old) != 1:
    raise SystemExit(f'compile block match count: {s.count(old)}')
s = s.replace(old, new, 1)
old = '''    char so[PATH_MAX];
    compile_build_script(opt, so);
    void *h = dlopen(so, RTLD_NOW | RTLD_LOCAL);
    if (!h) die("cannot load build.c: %s", dlerror());
    void (*fn)(C_Build *) = NULL;'''
new = '''    char so[PATH_MAX];
    compile_build_script(opt, so);
    void *h = dlopen(so, RTLD_NOW | RTLD_LOCAL);
    if (!h) {
        const char *why = dlerror();
        char first_error[512];
        snprintf(first_error, sizeof(first_error), "%s", why ? why : "invalid cached module");
        if (unlink(so) != 0 && errno != ENOENT) die("cannot remove invalid build.c cache entry: %s", strerror(errno));
        compile_build_script(opt, so);
        h = dlopen(so, RTLD_NOW | RTLD_LOCAL);
        if (!h) die("cannot load build.c after cache recovery (previous error: %s): %s", first_error, dlerror());
    }
    void (*fn)(C_Build *) = NULL;'''
if s.count(old) != 1:
    raise SystemExit(f'load block match count: {s.count(old)}')
s = s.replace(old, new, 1)
p.write_text(s)
print('atomic build-script cache repair applied')
