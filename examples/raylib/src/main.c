#include <raylib.h>
#include <stdbool.h>
#include <string.h>

int main(int argc, char **argv) {
    const bool ci = argc > 1 && strcmp(argv[1], "--ci") == 0;

    if (ci) SetConfigFlags(FLAG_WINDOW_HIDDEN);

    InitWindow(800, 450, "C + raylib");
    SetTargetFPS(60);

    int frames = 0;
    while (!WindowShouldClose()) {
        BeginDrawing();
        ClearBackground(RAYWHITE);
        DrawText("Built with c", 300, 190, 30, BLACK);
        DrawText("raylib came from the global dependency cache", 155, 235, 20, DARKGRAY);
        EndDrawing();

        if (ci && ++frames >= 3) break;
    }

    CloseWindow();
    return 0;
}
