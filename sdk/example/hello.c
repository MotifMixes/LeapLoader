/* The SDK's example app: move a square with the D-pad, A changes its colour.
   Its place and colour are saved (save.bin) when leaving with HINT + A + B. */
#include "leaploader.h"

static struct { int x, y, colour; } state = {72, 72, 0};
static const unsigned colours[] = {0xF80, 0x0CF, 0x8F4, 0xF4A};

static void save(void) { ll_write_save(&state, sizeof state); }

int main(void)
{
    unsigned held = 0;
    ll_load_save(&state, sizeof state);
    for (;;) {
        unsigned k = ll_keys(), pressed = k & ~held;
        held = k;
        if (k) ll_awake();
        ll_menu_combo(k, save);
        if (k & LL_LEFT && state.x > 0) state.x--;
        if (k & LL_RIGHT && state.x < LL_W - 16) state.x++;
        if (k & LL_UP && state.y > 12) state.y--;
        if (k & LL_DOWN && state.y < LL_H - 16) state.y++;
        if (pressed & LL_A) state.colour = (state.colour + 1) % 4;
        ll_fill(0, 0, LL_W, 10, 0x226);
        ll_fill(0, 10, LL_W, LL_H - 10, 0x000);
        ll_fill(state.x, state.y, 16, 16, colours[state.colour]);
        ll_show();
        ll_wait_frame();
    }
}
