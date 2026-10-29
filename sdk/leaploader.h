/* LeapLoader homebrew SDK for the Leapster 2 (zlib licence: sdk/LICENSE.txt).

   A homebrew app is native ARC600 code that LeapLoader puts on the SD card and
   lists in its menu with a blue check (docs/homebrew.md). Write `int main(void)`;
   the SDK's entry.S calls it once the BIOS has loaded the app, and returning
   from it goes back to the LeapLoader menu.

   Build: ARC GCC with -mcpu=arc600 -mno-sdata (the BIOS owns gp), linked with
   sdk/link.ld; objcopy the .text/.rodata/.data sections to code.bin. See
   sdk/example/build.sh. */
#ifndef LEAPLOADER_H
#define LEAPLOADER_H

#define LL_SDK_VERSION 1

/* ---- buttons (ll_keys): set while held */
#define LL_UP     0x80000000u
#define LL_DOWN   0x00000100u
#define LL_LEFT   0x00000200u
#define LL_RIGHT  0x00000080u
#define LL_A      0x00004000u
#define LL_B      0x00002000u
#define LL_HINT   0x10000000u
#define LL_HOME   0x20000000u
#define LL_PAUSE  0x04000000u
#define LL_VOLUP  0x00010000u
#define LL_VOLDN  0x00008000u

unsigned ll_keys(void);

/* Call once a frame with ll_keys(): after HINT + A + B have been held for
   2.5 s (LeapLoader's "back to the menu" in every game) it calls
   `before` (if not 0: write your saves there) and goes back to the menu. */
void ll_menu_combo(unsigned keys, void (*before)(void));

/* Back to the LeapLoader menu now (the console restarts into it). */
void ll_to_menu(void);

/* ---- the screen: 160 x 160 pixels, 12 bits each (0xRGB), two pixels in
   three bytes: g0b0, r0r1, g1b1. Draw in ll_screen (RAM); ll_show puts it on the LCD. */
#define LL_W 160
#define LL_H 160
extern unsigned char *const ll_screen;
void ll_pixel(int x, int y, unsigned rgb);
void ll_fill(int x, int y, int w, int h, unsigned rgb);
/* After drawing a frame: copies ll_screen to the LCD. */
void ll_show(void);

/* ---- time: a 16 MHz count since the console started */
unsigned long long ll_ticks(void);
#define LL_TICKS_PER_SECOND 16000000u
/* Waits until the next 1/60 s since the last call (or returns at once if late). */
void ll_wait_frame(void);
/* Tells the console someone is playing (else it powers off when idle). */
void ll_awake(void);

/* ---- files (the BIOS's C library). Paths look like "b:\\NES\\x.nes" (b: = the
   SD card). ll_app_path makes a path in the app's own card folder,
   b:\Leapster\Apps\<id>\ (files/ of the package goes there). */
typedef void LL_FILE;
LL_FILE *ll_fopen(const char *path, const char *mode);  /* "rb", "wb", "w+", ... */
int ll_fread(void *buf, int size, int n, LL_FILE *f);
int ll_fwrite(const void *buf, int size, int n, LL_FILE *f);
int ll_fseek(LL_FILE *f, long offset, int whence);      /* 0 set, 1 current, 2 end */
int ll_fclose(LL_FILE *f);
const char *ll_app_path(const char *name);              /* a static buffer: copy it to keep it */

/* ---- saves: save.bin in the app's folder. ll_load_save returns the bytes
   read (0: no save yet); ll_write_save returns 1 when written. */
int ll_load_save(void *buf, int size);
int ll_write_save(const void *buf, int size);

/* ---- memory: the heap runs from the app's end to below the stack (most of 8 MiB). */
void *ll_alloc(unsigned n);  /* 16-byte aligned, never freed */
void *memset(void *d, int c, unsigned n);
void *memcpy(void *d, const void *s, unsigned n);
unsigned strlen(const char *s);

#endif
