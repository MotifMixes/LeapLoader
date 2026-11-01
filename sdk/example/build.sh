#!/bin/sh
# Builds the example into a homebrew package folder, package/ (app.txt + code.bin).
# ARC: the ARC GCC prefix (default arc-elf32, on PATH), e.g.
#   ARC=/d/arc-gcc/arc-elf32-win/bin/arc-elf32 sh build.sh
set -e
ARC=${ARC:-arc-elf32}
HERE=$(cd "$(dirname "$0")" && pwd)
SDK=$HERE/..
# -fno-branch-count-reg: no zero-overhead (LP) loops; on a real Leapster 2 they broke native code
# that ran right in the emulator. The check after linking stops the build if any LP is left.
CFLAGS="-mcpu=arc600 -fno-branch-count-reg -mbarrel-shifter -mnorm -mno-sdata -Os -ffreestanding -fno-builtin -I$SDK"
mkdir -p "$HERE/obj" "$HERE/package"
cd "$HERE/obj"
$ARC-gcc $CFLAGS -c "$SDK/entry.S" -o entry.o
$ARC-gcc $CFLAGS -c "$SDK/leaploader.c" -o leaploader.o
$ARC-gcc $CFLAGS -c "$HERE/hello.c" -o hello.o
$ARC-gcc -mcpu=arc600 -nostdlib -Wl,--no-warn-rwx-segments -T "$SDK/link.ld" -o hello.elf entry.o leaploader.o hello.o -lgcc
if $ARC-objdump -d hello.elf | grep -E '	lp(ne|eq|nz|z|hs|lo)?	' ; then
  echo "hello.elf has zero-overhead loops (above): they can fail on the console" >&2
  exit 1
fi
$ARC-objcopy -O binary -j .text -j .rodata -j .data hello.elf "$HERE/package/code.bin"
printf 'name=Hello Homebrew\nid=HelloLL\nauthor=LeapLoader SDK example\nversion=1\ncode=code.bin\n' \
  > "$HERE/package/app.txt"
ls -l "$HERE/package"
