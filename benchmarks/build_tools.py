#!/usr/bin/env python3

import os
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

FILES = 200
COLD_RUNS = 3
NOOP_RUNS = 10
EDIT_RUNS = 8
CPUS = os.cpu_count() or 1


def timed(cmd, cwd, env=None):
    start = time.perf_counter()
    subprocess.run(cmd, cwd=cwd, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (time.perf_counter() - start) * 1000.0


def median(values):
    return statistics.median(values)


def make_project(root):
    src = root / "src"
    src.mkdir(parents=True)

    with (src / "bench.h").open("w") as f:
        f.write("#ifndef BENCH_H\n#define BENCH_H\n#include <stdint.h>\n")
        for i in range(FILES):
            f.write(f"uint64_t module_{i}(uint64_t x);\n")
        f.write("#endif\n")

    for i in range(FILES):
        lines = ['#include "bench.h"\n']
        for j in range(48):
            value = i * 131 + j + 1
            shift = j % 17 + 1
            lines.append(
                f"static uint64_t h_{i}_{j}(uint64_t x) {{ "
                f"x ^= {value}ULL; x *= 1099511628211ULL; "
                f"x ^= x >> {shift}; return x; }}\n"
            )
        lines.append(f"uint64_t module_{i}(uint64_t x) {{\n")
        for j in range(48):
            lines.append(f"    x = h_{i}_{j}(x);\n")
        lines.append("    return x;\n}\n")
        (src / f"module_{i:03d}.c").write_text("".join(lines))

    with (src / "main.c").open("w") as f:
        f.write('#include "bench.h"\n#include <stdio.h>\n')
        f.write("int main(void) { uint64_t x = 1;\n")
        for i in range(FILES):
            f.write(f"x ^= module_{i}(x + {i});\n")
        f.write('printf("%llu\\n", (unsigned long long)x); return 0; }\n')

    (root / "build.c").write_text(
        '#include <cbuild.h>\n'
        'void build(C_Build *b) {\n'
        '    C_Target *app = c_executable(b, "bench");\n'
        '    c_sources(app, "src/*.c");\n'
        '    c_include(app, "src");\n'
        '}\n'
    )

    (root / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(cbench C)\n"
        'file(GLOB SOURCES "src/*.c")\n'
        "add_executable(bench ${SOURCES})\n"
        "target_include_directories(bench PRIVATE src)\n"
        "target_compile_options(bench PRIVATE -std=c11 -O0 -g)\n"
    )

    (root / "Makefile").write_text(
        "CC ?= cc\n"
        "CFLAGS := -std=c11 -O0 -g -MMD -MP -Isrc\n"
        "SOURCES := $(wildcard src/*.c)\n"
        "OBJECTS := $(patsubst src/%.c,build-make/%.o,$(SOURCES))\n"
        "DEPS := $(OBJECTS:.o=.d)\n"
        "all: build-make/bench\n"
        "build-make/bench: $(OBJECTS)\n\t$(CC) $(OBJECTS) -o $@\n"
        "build-make/%.o: src/%.c\n\t@mkdir -p build-make\n"
        "\t$(CC) $(CFLAGS) -c $< -o $@\n"
        "-include $(DEPS)\n"
    )


def copy_project(base, root, name):
    dest = root / name
    shutil.copytree(base, dest)
    return dest


def bench_c(base, root, jobs=None):
    name = "c-default" if jobs is None else f"c-j{jobs}"
    work = copy_project(base, root, name)
    cache = root / f"{name}-cache"
    env = os.environ.copy()
    env["C_CACHE_DIR"] = str(cache)
    env["CC"] = "cc"
    cmd = ["c", "build"]
    if jobs is not None:
        cmd.append(f"-j{jobs}")

    cold = []
    for _ in range(COLD_RUNS):
        shutil.rmtree(work / "build", ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
        cold.append(timed(cmd, work, env))

    noop = [timed(cmd, work, env) for _ in range(NOOP_RUNS)]
    edit = []
    for i in range(EDIT_RUNS):
        os.utime(work / "src" / f"module_{120 + i:03d}.c", None)
        edit.append(timed(cmd, work, env))
    return median(cold), median(noop), median(edit)


def bench_ninja(base, root):
    work = copy_project(base, root, "cmake-ninja")
    build = work / "build-cmake"
    cold = []
    for _ in range(COLD_RUNS):
        shutil.rmtree(build, ignore_errors=True)
        start = time.perf_counter()
        subprocess.run([
            "cmake", "-S", ".", "-B", "build-cmake", "-G", "Ninja",
            "-DCMAKE_C_COMPILER=cc", "-DCMAKE_BUILD_TYPE=Debug"
        ], cwd=work, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ninja", "-C", "build-cmake", f"-j{CPUS}"], cwd=work,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cold.append((time.perf_counter() - start) * 1000.0)

    cmd = ["ninja", "-C", "build-cmake", f"-j{CPUS}"]
    noop = [timed(cmd, work) for _ in range(NOOP_RUNS)]
    edit = []
    for i in range(EDIT_RUNS):
        os.utime(work / "src" / f"module_{120 + i:03d}.c", None)
        edit.append(timed(cmd, work))
    return median(cold), median(noop), median(edit)


def bench_make(base, root):
    work = copy_project(base, root, "make")
    cmd = ["make", f"-j{CPUS}"]
    cold = []
    for _ in range(COLD_RUNS):
        shutil.rmtree(work / "build-make", ignore_errors=True)
        cold.append(timed(cmd, work))
    noop = [timed(cmd, work) for _ in range(NOOP_RUNS)]
    edit = []
    for i in range(EDIT_RUNS):
        os.utime(work / "src" / f"module_{120 + i:03d}.c", None)
        edit.append(timed(cmd, work))
    return median(cold), median(noop), median(edit)


def main():
    for tool in ("c", "cc", "cmake", "ninja", "make"):
        if not shutil.which(tool):
            raise SystemExit(f"missing: {tool}")

    with tempfile.TemporaryDirectory(prefix="c-build-bench-") as temp:
        root = Path(temp)
        base = root / "base"
        make_project(base)

        rows = [
            (f"c default (~{max(1, CPUS // 2)} jobs)", bench_c(base, root)),
            (f"c -j{CPUS}", bench_c(base, root, CPUS)),
            (f"CMake + Ninja -j{CPUS}", bench_ninja(base, root)),
            (f"Make -j{CPUS}", bench_make(base, root)),
        ]

    print("| Build | First | No changes | One file |")
    print("| --- | ---: | ---: | ---: |")
    for name, values in rows:
        cold, noop, edit = values
        print(f"| {name} | {cold:.1f} ms | {noop:.1f} ms | {edit:.1f} ms |")


if __name__ == "__main__":
    main()
