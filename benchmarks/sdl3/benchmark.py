#!/usr/bin/env python3

import benchmark_impl as impl

# Real SDL update spanning several commits and several changed files,
# without a public-header change that forces an almost complete rebuild.
impl.BASE = "b07d48821698af08545cb38e293ead99753bfc35"
impl.CHANGE = "eba3c7ae0ad85c13051179d196e5187ccb96cf6a"
impl.CHANGE_FILE = "src/joystick/SDL_gamepad.c"

_base_cmake_args = impl.cmake_args


def cmake_args(source, build):
    return _base_cmake_args(source, build) + [
        "-DSDL_UNIX_CONSOLE_BUILD=ON",
        "-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON",
    ]


impl.cmake_args = cmake_args
impl.main()
