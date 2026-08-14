#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- benchmark-suite:start -->'
END = '<!-- benchmark-suite:end -->'
OLD_START = '<!-- sdl3-benchmark:start -->'
OLD_END = '<!-- sdl3-benchmark:end -->'


def load(name):
    path = ROOT / 'benchmarks' / name / 'results.json'
    if not path.exists():
        raise RuntimeError(f'missing benchmark result: {path.relative_to(ROOT)}')
    return json.loads(path.read_text())


def fmt(ms):
    return f'{ms / 1000:.2f} s' if ms >= 1000 else f'{ms:.1f} ms'


def verdict(c_ms, ninja_ms):
    if not ninja_ms:
        return 'n/a'
    if c_ms < ninja_ms:
        return f'`c` {(ninja_ms - c_ms) / ninja_ms * 100:.1f}% faster'
    if c_ms > ninja_ms:
        return f'`c` {(c_ms - ninja_ms) / ninja_ms * 100:.1f}% slower'
    return 'equal'


def row(label, c_ms, ninja_ms):
    return f'| {label} | {fmt(c_ms)} | {fmt(ninja_ms)} | {verdict(c_ms, ninja_ms)} |'


def section_body(path):
    lines = path.read_text().strip().splitlines()
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    return '\n'.join(lines).strip()


def point(result, changed):
    for item in result.get('points', []):
        if item.get('changed_sources') == changed:
            return item
    raise RuntimeError(f'missing {changed}-source point in Wireshark results')


def runner_line(label, result):
    m = result['machine']
    jobs = result.get('jobs', '?')
    return f"| {label} | {m.get('date', '?')} | {m.get('cpu_model', 'unknown')} | {m.get('cpu_count', '?')} | {jobs} |"


def update_readme(section):
    path = ROOT / 'README.md'
    text = path.read_text()
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
    elif OLD_START in text and OLD_END in text:
        before, rest = text.split(OLD_START, 1)
        _, after = rest.split(OLD_END, 1)
    else:
        anchor = '\n## Notes\n'
        if anchor not in text:
            raise RuntimeError('README benchmark insertion point not found')
        before, after = text.split(anchor, 1)
        after = anchor + after
    path.write_text(before.rstrip() + '\n\n' + section.strip() + '\n\n' + after.lstrip())


def main():
    cjson = load('cjson')
    sdl = load('sdl3')
    fanout = load('fanout')
    large = load('large')

    sdl_report = ROOT / 'benchmarks' / 'sdl3' / 'report.md'
    if not sdl_report.exists():
        raise RuntimeError('benchmarks/sdl3/report.md is missing; run the SDL3 benchmark workflow first')

    cjson_setup_c = cjson['configuration']['c_fresh_build_script_cache']['wall_ms']
    cjson_setup_n = cjson['configuration']['cmake_configure']['wall_ms']
    cjson_noop_c = cjson['c']['noop']['wall_ms']
    cjson_noop_n = cjson['cmake_ninja']['noop']['wall_ms']
    sdl_noop_c = sdl['c']['noop']['wall_ms']
    sdl_noop_n = sdl['cmake_ninja']['noop']['wall_ms']
    sdl_clean_c = sdl['c']['clean']['wall_ms']
    sdl_clean_n = sdl['cmake_ninja']['clean']['wall_ms']
    fan_c = fanout['c']['header_change']['wall_ms']
    fan_n = fanout['cmake_ninja']['header_change']['wall_ms']
    large10 = point(large, 10)
    large_clean_c = large['c']['clean']['wall_ms']
    large_clean_n = large['cmake_ninja']['clean']['wall_ms']

    overview_rows = [
        row('cJSON fresh setup', cjson_setup_c, cjson_setup_n),
        row('cJSON no-op (1 TU)', cjson_noop_c, cjson_noop_n),
        row(f"SDL3 no-op ({sdl['source_count']} TUs)", sdl_noop_c, sdl_noop_n),
        row(f"SDL3 clean ({sdl['source_count']} TUs)", sdl_clean_c, sdl_clean_n),
        row(f"libcurl common-header fan-out ({fanout['invalidated_tus']} TUs)", fan_c, fan_n),
        row('Wireshark 10 source changes', large10['c']['wall_ms'], large10['cmake_ninja']['wall_ms']),
        row(f"Wireshark clean ({large['source_count']} TUs)", large_clean_c, large_clean_n),
    ]

    readme_section = f'''{START}
## Performance

Real C projects, identical CMake-derived source sets and semantic compile flags. Lower is better.

| Workload | `c` | CMake + Ninja | Result |
| --- | ---: | ---: | --- |
{chr(10).join(overview_rows)}

The projects are pinned and raw samples are checked in. Hosted-runner results should be compared **within a row**, not across separate workflow runs.

Full methodology, scaling data and raw measurements: [BENCHMARK.md](BENCHMARK.md)
{END}'''
    update_readme(readme_section)

    full = f'''# Benchmark suite

_Generated from pinned, reproducible benchmark workflows. Do not edit benchmark numbers by hand._

## Overview

| Workload | `c` | CMake + Ninja | Result |
| --- | ---: | ---: | --- |
{chr(10).join(overview_rows)}

Each row compares the two build systems on the same hosted runner, source tree, source set, semantic flags and build-job count. Object caching is disabled for measured compilation. Cross-row timing comparisons are not meaningful because separate workflow runs may land on different hosted machines.

## SDL3 — incremental scaling

{section_body(sdl_report)}

Raw samples: [`benchmarks/sdl3/results.json`](benchmarks/sdl3/results.json)

## cJSON — startup and tiny-project overhead

{section_body(ROOT / 'benchmarks' / 'cjson' / 'README.md')}

Raw samples: [`benchmarks/cjson/results.json`](benchmarks/cjson/results.json)

## libcurl — header fan-out

{section_body(ROOT / 'benchmarks' / 'fanout' / 'README.md')}

Raw samples: [`benchmarks/fanout/results.json`](benchmarks/fanout/results.json)

## Wireshark — large-project stress

{section_body(ROOT / 'benchmarks' / 'large' / 'README.md')}

Raw samples: [`benchmarks/large/results.json`](benchmarks/large/results.json)

## Runner snapshots

| Benchmark | Date | CPU | vCPUs | Jobs |
| --- | --- | --- | ---: | ---: |
{runner_line('SDL3', sdl)}
{runner_line('cJSON', cjson)}
{runner_line('libcurl', fanout)}
{runner_line('Wireshark', large)}

## What each workload tests

- **cJSON:** startup, graph checking and fixed overhead where compiler work is tiny.
- **SDL3:** controlled incremental scaling from no changes through a clean build, plus a real historical update.
- **libcurl:** dependency invalidation after changing one widely included header; the workflow fails if the two systems disagree on rebuilt TU count.
- **Wireshark:** a 1,000+ TU stress workload with controlled 1- and 10-source edits; Ninja receives a timestamp-aware archive step so both sides perform compile + static-archive work.
'''
    (ROOT / 'BENCHMARK.md').write_text(full)


if __name__ == '__main__':
    main()
