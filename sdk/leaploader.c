/* LeapLoader homebrew SDK runtime (zlib licence: sdk/LICENSE.txt).
   Every BIOS call goes through the BIOS's service tables, so the same app runs
   on Leapster 2 BIOS 0.6 and the Connected's B5 (research/bioscall.py). */
#include "leaploader.h"

typedef unsigned u32;

/* ---- BIOS services: [[gp + 4] + service] is a function table */
#define SVC_KERNEL 0x10
#define SVC_BOOT   0x28   /* 0x1003 */
#define SVC_SYS    0xAC   /* SysMgrMPI */
#define SVC_LCD    0xB8   /* LcdMPI */
#define SVC_FILE   0x280  /* 0x1035: C library files */
static void *svc(u32 service, u32 slot)
{
    u32 gp;
    __asm__ volatile("mov %0, gp" : "=r"(gp));
    return *(void **)(*(u32 *)(*(u32 *)(gp + 4) + service) + slot);
}

LL_FILE *ll_fopen(const char *path, const char *mode)
{ return ((void *(*)(const char *, const char *))svc(SVC_FILE, 0x28))(path, mode); }
int ll_fclose(LL_FILE *f) { return ((int (*)(void *))svc(SVC_FILE, 0x2C))(f); }
int ll_fread(void *buf, int size, int n, LL_FILE *f)
{ return ((int (*)(void *, int, int, void *))svc(SVC_FILE, 0x30))(buf, size, n, f); }
int ll_fwrite(const void *buf, int size, int n, LL_FILE *f)
{ return ((int (*)(const void *, int, int, void *))svc(SVC_FILE, 0x34))(buf, size, n, f); }
int ll_fseek(LL_FILE *f, long offset, int whence)
{ return ((int (*)(void *, long, int))svc(SVC_FILE, 0x38))(f, offset, whence); }
static void lcd_base(void);
unsigned long long ll_ticks(void);
void ll_awake(void)
{
    /* at most every 2 s, and the LCD back on the app's frame after it */
    static unsigned long long last;
    unsigned long long t = ll_ticks();
    if (last && t - last < 2ull * LL_TICKS_PER_SECOND) return;
    last = t;
    ((void (*)(void))svc(SVC_SYS, 0x14))();
    lcd_base();
}

/* ---- C basics (the app links no C library: newlib's would use gp) */
void *memset(void *d, int c, unsigned n)
{
    unsigned char *p = d;
    while (n--) *p++ = (unsigned char)c;
    return d;
}
void *memcpy(void *d, const void *s, unsigned n)
{
    unsigned char *p = d;
    const unsigned char *q = s;
    while (n--) *p++ = *q++;
    return d;
}
unsigned strlen(const char *s)
{
    const char *p = s;
    while (*p) p++;
    return p - s;
}

extern char __bss_end[], __heap_end[];
static char *heap = __bss_end;
void *ll_alloc(unsigned n)
{
    char *p = heap;
    n = (n + 15) & ~15u;
    if ((unsigned)(__heap_end - p) < n) return 0;
    heap = p + n;
    return p;
}

/* ---- buttons: the GPIO lines, low while pressed */
static inline u32 io_rd(u32 a)
{
    u32 v;
    __asm__ volatile("ld.di %0, [%1]" : "=r"(v) : "r"(a));
    return v;
}
unsigned ll_keys(void) { return ~io_rd(0x0180004C) & 0xB703E380; }

/* ---- the app's folder: while an app runs, b:\Leapster\PlayGame.lnk holds the
   path of its game.bin (the menu wrote it to start the app) */
#define LNK "b:\\Leapster\\PlayGame.lnk"
#define MENU "b:\\Leapster\\System\\SDMenu\\SDMenu.bin"
static char app_dir[128];
static void find_app_dir(void)
{
    LL_FILE *f = ll_fopen(LNK, "rb");
    int n = 0, i;
    if (f) {
        n = ll_fread(app_dir, 1, sizeof app_dir - 1, f);
        ll_fclose(f);
    }
    if (n < 0) n = 0;
    app_dir[n] = 0;
    for (i = n; i > 0 && app_dir[i - 1] != '\\'; i--) {}
    app_dir[i] = 0;  /* "b:\Leapster\Apps\<id>\" (empty if unknown) */
}
const char *ll_app_path(const char *name)
{
    static char path[192];
    unsigned a = strlen(app_dir), b = strlen(name);
    if (a + b >= sizeof path) b = sizeof path - 1 - a;
    memcpy(path, app_dir, a);
    memcpy(path + a, name, b);
    path[a + b] = 0;
    return path;
}

int ll_load_save(void *buf, int size)
{
    LL_FILE *f = ll_fopen(ll_app_path("save.bin"), "rb");
    int n;
    if (!f) return 0;
    n = ll_fread(buf, 1, size, f);
    ll_fclose(f);
    return n > 0 ? n : 0;
}
int ll_write_save(const void *buf, int size)
{
    LL_FILE *f = ll_fopen(ll_app_path("save.bin"), "wb");
    int n;
    if (!f) return 0;
    n = ll_fwrite(buf, 1, size, f);
    ll_fclose(f);
    return n == size;
}

/* ---- back to the menu: PlayGame.lnk = the menu, then LC_Boot("ExtStorage")
   restarts the console into it (docs/how-it-works.md section 3) */
void ll_to_menu(void)
{
    static const char menu[] = MENU;
    LL_FILE *f = ll_fopen(LNK, "w+");
    if (f) {
        ll_fwrite(menu, 1, sizeof menu - 1, f);
        ll_fclose(f);
    }
    ((void (*)(const char *))svc(SVC_BOOT, 0x34))("ExtStorage");
    for (;;) {}
}
void ll_menu_combo(unsigned keys, void (*before)(void))
{
    static unsigned long long since;
    unsigned long long t = ll_ticks();
    if ((keys & (LL_HINT | LL_A | LL_B)) != (LL_HINT | LL_A | LL_B)) {
        since = 0;
        return;
    }
    if (!since) since = t;
    if (t - since >= LL_TICKS_PER_SECOND * 5ull / 2) {
        if (before) before();
        ll_to_menu();
    }
}

/* ---- time: the kernel's tick count (10 ms) and timer 0 within the tick */
#define TIMER0 0x0180D084
#define TICK_START (0x1000000 - 0x27100)
#define KERNEL 0x3C7FACB0
unsigned long long ll_ticks(void)
{
    static unsigned long long last;
    volatile u32 *ticks = (volatile u32 *)(*(volatile u32 *)KERNEL + 0x34);
    u32 lo, hi, c;
    unsigned long long t;
    do {
        lo = ticks[0], hi = ticks[1];
        c = io_rd(TIMER0);
    } while (lo != ticks[0]);
    t = ((unsigned long long)hi << 32 | lo) * 0x27100 + (c >= TICK_START ? c - TICK_START : c + 0x27100);
    if (t > last) last = t;
    return last;
}
void ll_wait_frame(void)
{
    static unsigned long long due;
    unsigned long long t = ll_ticks(), per = LL_TICKS_PER_SECOND / 60;
    if (!due || t > due + 6 * per) due = t;  /* first frame, or far behind: start again */
    due += per;
    while (ll_ticks() < due) {}
}

/* ---- the screen: the LCD shows on-chip RAM at 0x0300_0000 (LcdMPI SetFrameBuffer) */
/* ---- the screen: the app draws in RAM (ll_screen); ll_show copies it to the
   LCD's VRAM at 0x0300_0000 with uncached word stores (drawing straight into
   VRAM went black after button presses in the emulator) */
#define VRAM 0x03000000u
static u32 frame_words[LL_W * LL_H * 3 / 2 / 4];
unsigned char *const ll_screen = (unsigned char *)frame_words;
static void lcd_base(void) { ((void (*)(u32))svc(SVC_LCD, 0x28))(VRAM); }
void ll_pixel(int x, int y, unsigned rgb)
{
    unsigned char *p;
    if ((unsigned)x >= LL_W || (unsigned)y >= LL_H) return;
    p = ll_screen + y * (LL_W * 3 / 2) + (x >> 1) * 3;
    if (!(x & 1)) {
        p[0] = rgb & 0xFF;
        p[1] = (p[1] & 0x0F) | (rgb >> 4 & 0xF0);
    } else {
        p[1] = (p[1] & 0xF0) | (rgb >> 8 & 0x0F);
        p[2] = rgb & 0xFF;
    }
}
void ll_fill(int x, int y, int w, int h, unsigned rgb)
{
    int i, j;
    for (j = y; j < y + h; j++)
        for (i = x; i < x + w; i++) ll_pixel(i, j, rgb);
}
void ll_show(void)
{
    const u32 *w = frame_words, *e = w + sizeof frame_words / 4;
    u32 a = VRAM;
    for (; w < e; w += 4, a += 16) {
        u32 w0 = w[0], w1 = w[1], w2 = w[2], w3 = w[3];
        __asm__ volatile("st.di %0, [%1]\n\tst.di %2, [%1, 4]\n\tst.di %3, [%1, 8]\n\tst.di %4, [%1, 12]"
                         : : "r"(w0), "r"(a), "r"(w1), "r"(w2), "r"(w3) : "memory");
    }
}

/* ---- start (entry.S): clear .bss, find the folder, show the screen, run main */
extern char __bss_start[];
int main(void);
void ll_start(void)
{
    memset(__bss_start, 0, __bss_end - __bss_start);
    heap = __bss_end;
    find_app_dir();
    memset(ll_screen, 0, LL_W * LL_H * 3 / 2);
    ll_show();
    lcd_base();
    main();
    ll_to_menu();
}
