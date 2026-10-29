; LeapLoader homebrew SDK: the start of an app's code (zlib licence: sdk/LICENSE.txt).
; code.bin begins here, at 0x3C81_0000 (link.ld). LeapLoader's card builder
; wraps it into game.bin with a movie whose first frame calls the native
; __llapp(), and points the image's 0x1009 resource at `blob`.
    .cpu    arc600
    .section .text.start, "ax"
    .global _start
_start:
; ---- the native list: {0x100, 0, count << 16, pairs}, then (name, function)
blob:
    .word   0x100, 0, 0x00010000, pairs
pairs:
    .word   name, llapp
name:
    .asciz  "__llapp"
    .align  4

; ---- __llapp(ctx): never returns (ll_start goes back to the menu after main).
; gp stays the BIOS's: every BIOS call needs it, so the code is built with
; -mno-sdata. It runs on the Flash player task's stack.
llapp:
    bl      ll_start
1:  b       1b
