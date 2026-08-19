from pathlib import Path

p = Path('src/main.c')
s = p.read_text()

old = '''static void cmd_deps(const Options *opt) {
    C_Build *b = alloc_build();
    load_build(opt, b);
    if (!b->dep_count) {
        puts("No dependencies.");
        free_build(b);
        return;
    }
    for (size_t i = 0; i < b->dep_count; ++i) {
        printf("%s  %s  %s  [%s]\\n", b->deps[i].name, b->deps[i].git, b->deps[i].ref,
               b->deps[i].kind == C_DEP_CMAKE ? "cmake" : (b->deps[i].kind == C_DEP_SOURCE ? "source" : "header"));
    }
    free_build(b);
}
'''
new = '''static const char *dep_kind_name(C_DepKind kind) {
    return kind == C_DEP_CMAKE ? "cmake" : kind == C_DEP_SOURCE ? "source" : "header";
}

static void cmd_deps(const Options *opt) {
    C_Build *b = alloc_build();
    load_build(opt, b);
    if (opt->target_name && !strcmp(opt->target_name, "clean")) {
        char cache[PATH_MAX], path[PATH_MAX];
        cache_root(cache);
        static const char *dirs[] = {"git", "src", "pkg", "dep-build"};
        for (size_t i = 0; i < C_ARRAY_LEN(dirs); ++i) {
            path_join(path, cache, dirs[i]);
            if (is_dir(path) && remove_tree(path) != 0) die("cannot remove dependency cache: %s", path);
        }
        note("CLEAN", "dependency cache");
        free_build(b);
        return;
    }
    if (opt->target_name && strcmp(opt->target_name, "tree"))
        die("unknown deps action: %s (expected tree or clean)", opt->target_name);
    if (opt->target_name && !strcmp(opt->target_name, "tree")) {
        puts("Targets:");
        for (size_t i = 0; i < b->target_count; ++i) {
            C_Target *t = &b->targets[i];
            printf("  %s\\n", t->name);
            for (size_t j = 0; j < t->target_dep_count; ++j)
                printf("    -> target %s\\n", t->target_deps[j]->name);
            for (size_t j = 0; j < t->dep_count; ++j)
                printf("    -> dependency %s [%s]\\n", t->deps[j]->name, dep_kind_name(t->deps[j]->kind));
        }
        if (b->dep_count) {
            puts("Dependencies:");
            for (size_t i = 0; i < b->dep_count; ++i)
                printf("  %s  %s  %s  [%s]\\n", b->deps[i].name, b->deps[i].git, b->deps[i].ref, dep_kind_name(b->deps[i].kind));
        }
        free_build(b);
        return;
    }
    if (!b->dep_count) {
        puts("No dependencies.");
        free_build(b);
        return;
    }
    for (size_t i = 0; i < b->dep_count; ++i)
        printf("%s  %s  %s  [%s]\\n", b->deps[i].name, b->deps[i].git, b->deps[i].ref, dep_kind_name(b->deps[i].kind));
    free_build(b);
}
'''
if s.count(old) != 1:
    raise SystemExit(f'cmd_deps block matches: {s.count(old)}')
s = s.replace(old, new, 1)

old = '''static void cmd_cache(const Options *opt) {
    char cache[PATH_MAX];
    cache_root(cache);
    if (opt->target_name && !strcmp(opt->target_name, "clean")) {
        if (is_dir(cache) && remove_tree(cache) != 0) die("cannot remove cache: %s", cache);
        note("CLEAN", "%s", cache);
        return;
    }
    printf("%s\\n", cache);
}
'''
new = '''static void cache_stats_walk(const char *path, unsigned long long *files, unsigned long long *bytes) {
    DIR *d = opendir(path);
    if (!d) return;
    struct dirent *ent;
    while ((ent = readdir(d))) {
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..")) continue;
        char child[PATH_MAX]; path_join(child, path, ent->d_name);
        struct stat st;
        if (lstat(child, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) cache_stats_walk(child, files, bytes);
        else if (S_ISREG(st.st_mode)) { ++*files; *bytes += (unsigned long long)st.st_size; }
    }
    closedir(d);
}

static void cmd_cache(const Options *opt) {
    char cache[PATH_MAX];
    cache_root(cache);
    if (opt->target_name && !strcmp(opt->target_name, "clean")) {
        if (is_dir(cache) && remove_tree(cache) != 0) die("cannot remove cache: %s", cache);
        note("CLEAN", "%s", cache);
        return;
    }
    if (opt->target_name && !strcmp(opt->target_name, "stats")) {
        unsigned long long files = 0, bytes = 0;
        if (is_dir(cache)) cache_stats_walk(cache, &files, &bytes);
        printf("Path   %s\\nFiles  %llu\\nBytes  %llu\\n", cache, files, bytes);
        return;
    }
    if (opt->target_name) die("unknown cache action: %s (expected stats or clean)", opt->target_name);
    printf("%s\\n", cache);
}
'''
if s.count(old) != 1:
    raise SystemExit(f'cmd_cache block matches: {s.count(old)}')
s = s.replace(old, new, 1)

s = s.replace('''         "  c deps\\n"''', '''         "  c deps [tree|clean]\\n"''', 1)
s = s.replace('''         "  c cache [clean]\\n"''', '''         "  c cache [stats|clean]\\n"''', 1)
p.write_text(s)
print('CLI inspection upgrade applied')
