/* LeapLoader homebrew SDK linker script (zlib licence: sdk/LICENSE.txt).
   The BIOS loads game.bin at 0x3C80_0000; the card builder puts code.bin at
   offset 0x1_0000 of it, so the code runs at 0x3C81_0000. code.bin plus .bss
   must end below the heap's end; the stack is the Flash player task's own. */
ENTRY(_start)
SECTIONS
{
    . = 0x3C810000;
    .text : { *(.text.start) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.*) *(.sdata .sdata.*) . = ALIGN(16); }
    __file_end = .;
    .bss (NOLOAD) : { __bss_start = .; *(.sbss .sbss.*) *(.bss .bss.* COMMON) . = ALIGN(16); __bss_end = .; }
    __heap_end = 0x3CFF0000;
    /DISCARD/ : { *(.comment) *(.note*) *(.init_array*) *(.ctors) }
}
