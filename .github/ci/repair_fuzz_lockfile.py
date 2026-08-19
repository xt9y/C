from pathlib import Path
p=Path('.github/ci/fuzz/fuzz_lockfile.c')
s=p.read_text()
s=s.replace('#include <unistd.h>\n', '#include <unistd.h>\n#include <sys/wait.h>\n')
start=s.index('int LLVMFuzzerTestOneInput(')
new=r'''int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 1024 * 1024) return 0;
    if (!fuzz_write_file("c.lock", data, size)) return 0;

    /* load_lock() is intentionally a CLI-style parser: malformed input is
       rejected through c__fatal()/exit().  Running it directly inside
       libFuzzer makes an expected validation rejection look like a fuzz
       crash.  Isolate parsing in a child: ordinary non-zero exits are valid
       rejected inputs, while signals still indicate a real crash. */
    pid_t pid = fork();
    if (pid < 0) { unlink("c.lock"); return 0; }
    if (pid == 0) {
        LockFile first;
        load_lock(&first);
        fuzz_check_lock(&first);

        if (first.count) {
            save_lock(&first);
            LockFile second;
            load_lock(&second);
            fuzz_check_lock(&second);
            if (!fuzz_lock_equal(&first, &second)) abort();
        }
        _exit(0);
    }

    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        /* EINTR is harmless; any other wait failure just rejects this input. */
        if (errno != EINTR) { unlink("c.lock"); return 0; }
    }
    unlink("c.lock");
    if (WIFSIGNALED(status)) abort();
    return 0;
}
'''
s=s[:start]+new
# errno is needed by wait loop
s=s.replace('#include <stdint.h>\n', '#include <stdint.h>\n#include <errno.h>\n')
p.write_text(s)
