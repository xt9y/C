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

    c_dep_source(raylib);
    c_dep_subdir(raylib, "src");
    c_dep_include(raylib, ".");
    c_dep_include(raylib, "external/glfw/include");

    c_dep_sources(raylib, "rcore.c");
    c_dep_sources(raylib, "rshapes.c");
    c_dep_sources(raylib, "rtextures.c");
    c_dep_sources(raylib, "rtext.c");
    c_dep_sources(raylib, "utils.c");
    c_dep_sources(raylib, "rmodels.c");
    c_dep_sources(raylib, "raudio.c");
    c_dep_sources(raylib, "rglfw.c");

    c_dep_flag(raylib, "-std=gnu99");
    c_dep_flag(raylib, "-D_GNU_SOURCE");
    c_dep_flag(raylib, "-DPLATFORM_DESKTOP_GLFW");
    c_dep_flag(raylib, "-DGRAPHICS_API_OPENGL_33");
    c_dep_flag(raylib, "-Wno-missing-braces");
    c_dep_flag(raylib, "-fno-strict-aliasing");

#ifdef __APPLE__
    c_dep_flag(raylib, "-x");
    c_dep_flag(raylib, "objective-c");
#else
    c_dep_flag(raylib, "-D_GLFW_X11");
    c_dep_flag(raylib, "-fPIC");
#endif

    c_use(app, raylib);

#ifdef __APPLE__
    c_framework(app, "OpenGL");
    c_framework(app, "Cocoa");
    c_framework(app, "IOKit");
    c_framework(app, "CoreAudio");
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
