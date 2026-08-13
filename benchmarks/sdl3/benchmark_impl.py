#!/usr/bin/env python3

import json
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SDL_REPO = "https://github.com/libsdl-org/SDL.git"
BASE = "b340ddcd7b44511f7b49005ba4a91a3c9907f77e"
CHANGE = "b640b804a8cfe9f998ac82650a32c5e6e6cd4571"
CHANGE_FILE = "src/core/linux/SDL_evdev.c"
COLD_RUNS = 3
NOOP_RUNS = 10
CHANGE_RUNS = 5

ROOT = Path(__file__).resolve().parents[2]
C_BIN = ROOT / "build" / "c"


def run(cmd, *, cwd=None, env=None, quiet=False, check=True):
    kwargs = {
        "cwd": cwd,
        "env": env,
        "text": True,
        "check": check,
    }
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kwargs)


def timed(cmd, *, cwd=None, env=None):
    started = time.perf_counter_ns()
    run(cmd, cwd=cwd, env=env, quiet=True)
    return (time.perf_counter_ns() - started) / 1_000_000.0


def median(values):
    return statistics.median(values)


def cmake_args(source, build):
    return [
        "cmake", "-S", str(source), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DSDL_SHARED=OFF",
        "-DSDL_STATIC=ON",
        "-DSDL_TESTS=OFF",
        "-DSDL_EXAMPLES=OFF",
        "-DSDL_TEST_LIBRARY=OFF",
        "-DSDL_INSTALL=OFF",
        # Keep this benchmark deterministic and dependency-light.
        # It is still SDL3 itself, including the Linux evdev code changed by CHANGE.
        "-DSDL_X11=OFF",
        "-DSDL_WAYLAND=OFF",
        "-DSDL_KMSDRM=OFF",
        "-DSDL_ALSA=OFF",
        "-DSDL_PULSEAUDIO=OFF",
        "-DSDL_PIPEWIRE=OFF",
        "-DSDL_JACK=OFF",
        "-DSDL_SNDIO=OFF",
        "-DSDL_LIBUDEV=OFF",
        "-DSDL_HIDAPI=OFF",
        "-DSDL_OPENGL=OFF",
        "-DSDL_OPENGLES=OFF",
        "-DSDL_VULKAN=OFF",
    ]


def entry_args(entry):
    if "arguments" in entry:
        return list(entry["arguments"])
    return shlex.split(entry["command"])


def static_entries(db_path):
    data = json.loads(db_path.read_text())
    out = []
    for entry in data:
        args = entry_args(entry)
        joined = " ".join(args)
        if "SDL3-static.dir" not in joined:
            continue
        source = Path(entry["file"]).resolve()
        if source.suffix.lower() not in {".c", ".cc", ".cpp", ".cxx", ".s"} and source.suffix != ".S":
            continue
        out.append((entry, args, source))
    if not out:
        raise RuntimeError("No SDL3-static compile commands found")
    return out


def semantic_flags(args, source):
    flags = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in {"-o", "-MF", "-MT", "-MQ"}:
            i += 2
            continue
        if arg in {"-c", "-MD", "-MMD", "-MP"}:
            i += 1
            continue
        if arg == str(source):
            i += 1
            continue
        if arg.startswith("-O") or arg == "-g" or arg.startswith("-g") or arg.startswith("-W"):
            i += 1
            continue
        if arg in {"-I", "-isystem", "-include", "-imacros"} and i + 1 < len(args):
            flags.extend([arg, args[i + 1]])
            i += 2
            continue
        if (
            arg.startswith("-I") or arg.startswith("-D") or arg.startswith("-U")
            or arg.startswith("-std=") or arg.startswith("-f") or arg.startswith("-m")
            or arg in {"-pthread"}
        ):
            flags.append(arg)
        i += 1
    return tuple(flags)


def c_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def generate_build_c(meta_build, cproj, sdl):
    entries = static_entries(meta_build / "compile_commands.json")
    per_file = [(source, semantic_flags(args, source)) for _, args, source in entries]
    common = set(per_file[0][1])
    for _, flags in per_file[1:]:
        common.intersection_update(flags)

    # SDL's compile-affecting defines/includes must be target-wide for this c benchmark.
    # Warning-only differences are intentionally ignored.
    important = lambda f: f.startswith(("-D", "-U", "-I", "-std=", "-f", "-m")) or f in {"-pthread", "-isystem", "-include", "-imacros"}
    mismatches = []
    for source, flags in per_file:
        extra = [f for f in flags if important(f) and f not in common]
        missing = [f for f in common if important(f) and f not in flags]
        if extra or missing:
            mismatches.append((source, extra, missing))
    if mismatches:
        for source, extra, missing in mismatches[:20]:
            print(f"flag mismatch: {source}")
            if extra:
                print("  extra:", extra)
            if missing:
                print("  missing:", missing)
        raise RuntimeError("SDL3 has per-source semantic flags; refusing an unfair benchmark")

    sources = sorted({source for source, _ in per_file})
    wanted = (sdl / CHANGE_FILE).resolve()
    if wanted not in sources:
        raise RuntimeError(f"real-change file is not in SDL3-static target: {wanted}")

    # Preserve command order for paired flags.
    ordered_flags = []
    seen = set()
    first_flags = per_file[0][1]
    for f in first_flags:
        if f in common and f not in seen:
            ordered_flags.append(f)
            seen.add(f)

    lines = [
        "#include <cbuild.h>",
        "",
        "void build(C_Build *b) {",
        "    C_Target *sdl = c_static_library(b, \"SDL3\");",
    ]
    for source in sources:
        lines.append(f'    c_sources(sdl, "{c_string(str(source))}");')

    i = 0
    while i < len(ordered_flags):
        flag = ordered_flags[i]
        if flag.startswith("-I") and len(flag) > 2:
            lines.append(f'    c_include(sdl, "{c_string(flag[2:])}");')
        elif flag.startswith("-D") and len(flag) > 2:
            lines.append(f'    c_define(sdl, "{c_string(flag[2:])}");')
        elif flag in {"-isystem", "-include", "-imacros"} and i + 1 < len(ordered_flags):
            lines.append(f'    c_flag(sdl, "{c_string(flag)}");')
            lines.append(f'    c_flag(sdl, "{c_string(ordered_flags[i + 1])}");')
            i += 1
        else:
            lines.append(f'    c_flag(sdl, "{c_string(flag)}");')
        i += 1
    lines.extend(["}", ""])
    cproj.mkdir(parents=True, exist_ok=True)
    (cproj / "build.c").write_text("\n".join(lines))
    return len(sources), ordered_flags


def checkout(repo, rev):
    run(["git", "checkout", "--quiet", rev], cwd=repo)


def cmake_build_cmd(build, jobs):
    return ["cmake", "--build", str(build), "--target", "SDL3-static", "--parallel", str(jobs)]


def bench_ninja(repo, work, jobs):
    build = work / "ninja"
    if build.exists():
        shutil.rmtree(build)
    run(cmake_args(repo, build), quiet=True)

    # Prepare once, then clean outputs while keeping configuration/build graph.
    run(cmake_build_cmd(build, jobs), quiet=True)
    cold = []
    for _ in range(COLD_RUNS):
        run(["ninja", "-C", str(build), "-t", "clean"], quiet=True)
        cold.append(timed(cmake_build_cmd(build, jobs)))

    noop = [timed(cmake_build_cmd(build, jobs)) for _ in range(NOOP_RUNS)]

    changed = []
    for _ in range(CHANGE_RUNS):
        checkout(repo, BASE)
        run(cmake_build_cmd(build, jobs), quiet=True)
        checkout(repo, CHANGE)
        changed.append(timed(cmake_build_cmd(build, jobs)))
    checkout(repo, BASE)
    return cold, noop, changed


def bench_c(repo, cproj, cache, jobs):
    env = os.environ.copy()
    env["C_CACHE_DIR"] = str(cache)
    env["C_INCLUDE_DIR"] = str(ROOT / "include")
    env["C_OBJECT_CACHE"] = "0"
    cmd = [str(C_BIN), "build", "SDL3", f"-j{jobs}", "--no-object-cache"]

    # Prepare the compiled build.c module once. The benchmark is compile/archive time,
    # matching Ninja after CMake has generated its build graph.
    run(cmd, cwd=cproj, env=env, quiet=True)
    cold = []
    for _ in range(COLD_RUNS):
        shutil.rmtree(cproj / "build", ignore_errors=True)
        cold.append(timed(cmd, cwd=cproj, env=env))

    noop = [timed(cmd, cwd=cproj, env=env) for _ in range(NOOP_RUNS)]

    changed = []
    for _ in range(CHANGE_RUNS):
        checkout(repo, BASE)
        run(cmd, cwd=cproj, env=env, quiet=True)
        checkout(repo, CHANGE)
        changed.append(timed(cmd, cwd=cproj, env=env))
    checkout(repo, BASE)
    return cold, noop, changed


def fmt(ms):
    return f"{ms:.1f} ms" if ms < 1000 else f"{ms / 1000:.2f} s"


def main():
    jobs = int(os.environ.get("BENCH_JOBS", os.cpu_count() or 1))
    print(f"SDL3 benchmark: {BASE[:8]} -> {CHANGE[:8]}")
    print(f"jobs: {jobs}")

    run(["make"], cwd=ROOT, quiet=True)
    if not C_BIN.exists():
        raise RuntimeError("failed to build c")

    with tempfile.TemporaryDirectory(prefix="c-sdl3-bench-") as td:
        work = Path(td)
        sdl = work / "SDL"
        run(["git", "clone", "--quiet", SDL_REPO, str(sdl)])
        checkout(sdl, BASE)

        meta = work / "meta"
        run(cmake_args(sdl, meta), quiet=True)
        cproj = work / "cproj"
        source_count, flags = generate_build_c(meta, cproj, sdl)
        print(f"SDL3 static translation units: {source_count}")
        print(f"shared semantic flags: {len(flags)}")

        ninja = bench_ninja(sdl, work, jobs)
        checkout(sdl, BASE)
        c_times = bench_c(sdl, cproj, work / "c-cache", jobs)

        result = {
            "date": time.strftime("%Y-%m-%d", time.gmtime()),
            "base": BASE,
            "change": CHANGE,
            "change_file": CHANGE_FILE,
            "jobs": jobs,
            "cpu_count": os.cpu_count(),
            "source_count": source_count,
            "compiler": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0],
            "cmake": subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0],
            "ninja": subprocess.check_output(["ninja", "--version"], text=True).strip(),
            "c": {
                "cold_ms": median(c_times[0]),
                "noop_ms": median(c_times[1]),
                "real_commit_ms": median(c_times[2]),
                "cold_samples_ms": c_times[0],
                "noop_samples_ms": c_times[1],
                "real_commit_samples_ms": c_times[2],
            },
            "cmake_ninja": {
                "cold_ms": median(ninja[0]),
                "noop_ms": median(ninja[1]),
                "real_commit_ms": median(ninja[2]),
                "cold_samples_ms": ninja[0],
                "noop_samples_ms": ninja[1],
                "real_commit_samples_ms": ninja[2],
            },
        }
        print("\nRESULT_JSON=" + json.dumps(result, sort_keys=True))
        print("\nMedians")
        print(f"  c             cold {fmt(result['c']['cold_ms'])}  no-op {fmt(result['c']['noop_ms'])}  real commit {fmt(result['c']['real_commit_ms'])}")
        print(f"  CMake + Ninja cold {fmt(result['cmake_ninja']['cold_ms'])}  no-op {fmt(result['cmake_ninja']['noop_ms'])}  real commit {fmt(result['cmake_ninja']['real_commit_ms'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        raise
