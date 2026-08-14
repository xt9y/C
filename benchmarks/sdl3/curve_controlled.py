#!/usr/bin/env python3

import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

import benchmark_impl as impl
import benchmark_stats as stats


# Dense enough to show the shape of the curve without turning the manually
# triggered benchmark into a very long CI job. Every point is cumulative.
TARGET_FILES = (7, 21, 42, 63, 105, 147, 189)
RUNS = 3
CHANGE = stats.CHANGE


def reset_endpoint(repo):
    impl.run(["git", "reset", "--hard", "--quiet", CHANGE], cwd=repo, quiet=True)


def ordered_sources(meta, sdl):
    """Return endpoint SDL translation units in a deterministic mixed order."""
    root = sdl.resolve()
    sources = []
    seen = set()
    for _, _, source in impl.static_entries(meta / "compile_commands.json"):
        source = source.resolve()
        try:
            rel = str(source.relative_to(root))
        except ValueError:
            continue
        if rel in seen:
            continue
        seen.add(rel)
        sources.append((rel, source))

    # Hash ordering avoids making the first N points accidentally represent one
    # SDL subsystem just because paths sort next to each other alphabetically.
    sources.sort(key=lambda item: hashlib.sha256(item[0].encode()).digest())
    return sources


def marker_for(path):
    if path.suffix.lower() == ".s":
        return b"\n# c-buildsystem scaling benchmark edit\n"
    return b"\n/* c-buildsystem scaling benchmark edit */\n"


def apply_source_edits(paths):
    for path in paths:
        with path.open("ab") as handle:
            handle.write(marker_for(path))


def profile_size(repo, command, paths, root, *, marker=None, cwd=None, env=None):
    samples = []
    rebuilt = None

    try:
        for index in range(RUNS):
            reset_endpoint(repo)
            # Return objects to the exact endpoint state before every sample.
            impl.run(command, cwd=cwd, env=env, quiet=True)
            before = stats.object_snapshot(root, marker=marker) if index == 0 else None

            # Keep mtimes unambiguous even on filesystems with coarse timestamp
            # resolution, then make a real content change to each selected TU.
            time.sleep(1.05)
            apply_source_edits(paths)
            samples.append(stats.profiled(command, cwd=cwd, env=env))

            if before is not None:
                after = stats.object_snapshot(root, marker=marker)
                rebuilt = len(stats.changed_objects(before, after))
    finally:
        reset_endpoint(repo)

    if rebuilt is None:
        raise RuntimeError("failed to count rebuilt translation units")
    return stats.summarize(samples), rebuilt


def main():
    jobs = int(__import__("os").environ.get("BENCH_JOBS", 2))
    impl.run(["make"], cwd=stats.ROOT, quiet=True)

    with tempfile.TemporaryDirectory(prefix="c-sdl3-curve-") as directory:
        work = Path(directory)
        sdl = work / "SDL"
        impl.run(["git", "clone", "--quiet", impl.SDL_REPO, str(sdl)])
        impl.checkout(sdl, CHANGE)

        meta = work / "meta"
        impl.run(stats.cmake_args(sdl, meta), quiet=True)
        cproj = work / "cproj"
        source_count, _ = impl.generate_build_c(meta, cproj, sdl)
        sources = ordered_sources(meta, sdl)

        if len(sources) != source_count:
            raise RuntimeError(
                f"controlled curve found {len(sources)} endpoint sources; expected {source_count}"
            )
        if max(TARGET_FILES) >= source_count:
            raise RuntimeError(
                f"largest controlled point ({max(TARGET_FILES)}) must be below clean build ({source_count})"
            )

        ninja_build = work / "ninja"
        impl.run(stats.cmake_args(sdl, ninja_build), quiet=True)
        ninja_cmd = impl.cmake_build_cmd(ninja_build, jobs)
        impl.run(ninja_cmd, quiet=True)

        c_cache = work / "c-cache"
        c_env = stats.c_env(c_cache)
        c_cmd = stats.c_cmd(jobs)
        impl.run(c_cmd, cwd=cproj, env=c_env, quiet=True)

        points = []
        for changed_files in TARGET_FILES:
            selected = sources[:changed_files]
            selected_paths = [path for _, path in selected]

            ninja_profile, ninja_tus = profile_size(
                sdl,
                ninja_cmd,
                selected_paths,
                ninja_build,
                marker="SDL3-static.dir",
            )
            c_profile, c_tus = profile_size(
                sdl,
                c_cmd,
                selected_paths,
                cproj / "build",
                cwd=cproj,
                env=c_env,
            )

            if c_tus != changed_files or ninja_tus != changed_files:
                raise RuntimeError(
                    f"controlled {changed_files}-file point rebuilt unexpected TUs: "
                    f"c={c_tus} ninja={ninja_tus}"
                )

            points.append(
                {
                    "changed_files": changed_files,
                    "rebuilt_tus": changed_files,
                    "source_paths": [rel for rel, _ in selected],
                    "c": c_profile,
                    "cmake_ninja": ninja_profile,
                }
            )
            print(
                f"curve changed_files={changed_files} rebuilt_tus={changed_files} "
                f"c={c_profile['wall_ms']:.1f}ms "
                f"ninja={ninja_profile['wall_ms']:.1f}ms"
            )

        result = {
            "endpoint": CHANGE,
            "source_count": source_count,
            "jobs": jobs,
            "runs_per_point": RUNS,
            "targets": list(TARGET_FILES),
            "x_axis": "changed SDL source files",
            "mode": "controlled cumulative endpoint-source comment edits",
            "points": points,
        }
        print("CURVE_JSON=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
