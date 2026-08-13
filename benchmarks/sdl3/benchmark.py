#!/usr/bin/env python3

import benchmark_impl as impl

_base_cmake_args = impl.cmake_args


def cmake_args(source, build):
    return _base_cmake_args(source, build) + [
        "-DSDL_UNIX_CONSOLE_BUILD=ON",
        "-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON",
    ]


impl.cmake_args = cmake_args
impl.main()
