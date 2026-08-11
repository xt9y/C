#include <cbuild.h>

void build(C_Build *b) {
    C_Target *app = c_executable(b, "raylib-example");
    c_sources(app, "src/*.c");

    C_Dependency *raylib = c_git(
        b,
        "raylib",
        "https://github.com/raysan5/raylib.git",
        "5.5"
    );

    c_dep_cmake(raylib);
    c_dep_link(raylib, "raylib");
    c_dep_cmake_option(raylib, "-DBUILD_EXAMPLES=OFF");

#ifndef __APPLE__
    c_dep_cmake_option(raylib, "-DGLFW_BUILD_WAYLAND=OFF");
    c_dep_cmake_option(raylib, "-DGLFW_BUILD_X11=ON");
#endif

    c_use(app, raylib);

#ifdef __APPLE__
    c_framework(app, "OpenGL");
    c_framework(app, "Cocoa");
    c_framework(app, "IOKit");
    c_framework(app, "CoreFoundation");
    c_framework(app, "CoreVideo");
#else
    c_link_system(app, "GL");
    c_link_system(app, "m");
    c_link_system(app, "pthread");
    c_link_system(app, "dl");
    c_link_system(app, "rt");
    c_link_system(app, "X11");
    c_link_system(app, "Xrandr");
    c_link_system(app, "Xi");
    c_link_system(app, "Xinerama");
    c_link_system(app, "Xcursor");
    c_link_system(app, "Xext");
#endif
}
