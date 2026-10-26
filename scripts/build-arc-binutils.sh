#!/bin/sh
# Builds the ARC binutils LeapLoader's card build assembles its save stubs with
# (research/eestub.py, nativechip.py, streamstub.py: as, ld, nm, objcopy), from
# GNU's source, for Linux and macOS packages. (The Windows package takes the
# ready-made ones from Ribbit's tools/arc-gnu: the same binutils 2.45.1.)
#
# Run:    sh scripts/build-arc-binutils.sh OUT_DIR [WORK_DIR]
# Output: OUT_DIR/arc-elf32-as, -ld, -nm, -objcopy
# Needs:  a C compiler, make, curl (or wget), xz.
set -eu

VERSION=2.45.1
SHA256=5fe101e6fe9d18fdec95962d81ed670fdee5f37e3f48f0bef87bddf862513aa5
URL="https://ftp.gnu.org/gnu/binutils/binutils-$VERSION.tar.xz"

out=$(mkdir -p "$1" && cd "$1" && pwd)
work=${2:-${TMPDIR:-/tmp}/leaploader-binutils}
mkdir -p "$work"
cd "$work"

if [ ! -f "binutils-$VERSION.tar.xz" ]; then
    if command -v curl >/dev/null; then curl -fsSL -o "binutils-$VERSION.tar.xz" "$URL"
    else wget -q -O "binutils-$VERSION.tar.xz" "$URL"; fi
fi
if command -v sha256sum >/dev/null; then sum=$(sha256sum "binutils-$VERSION.tar.xz" | cut -d' ' -f1)
else sum=$(shasum -a 256 "binutils-$VERSION.tar.xz" | cut -d' ' -f1); fi
if [ "$sum" != "$SHA256" ]; then
    echo "binutils-$VERSION.tar.xz: checksum $sum, expected $SHA256" >&2
    exit 1
fi

rm -rf "binutils-$VERSION" build
tar -xJf "binutils-$VERSION.tar.xz"
mkdir build
cd build
# Only what the stubs need: no gdb, gprof, plugins or translations; the
# documentation is not built (MAKEINFO=true).
"../binutils-$VERSION/configure" --target=arc-elf32 --disable-nls --disable-werror --disable-gdb \
    --disable-gdbserver --disable-sim --disable-gprof --disable-gprofng --disable-plugins --without-zstd \
    --disable-sframe MAKEINFO=true >configure.log
jobs=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)
if ! make -j"$jobs" MAKEINFO=true all-gas all-ld all-binutils >make.log 2>&1; then
    # Again one step at a time, so the error is the log's last lines (not mixed with other jobs').
    make MAKEINFO=true all-gas all-ld all-binutils >make-serial.log 2>&1 || {
        grep -n -i -E "error|undefined|not found" make-serial.log | tail -20 >&2
        tail -30 make-serial.log >&2
        exit 1
    }
fi

cp gas/as-new "$out/arc-elf32-as"
cp ld/ld-new "$out/arc-elf32-ld"
cp binutils/nm-new "$out/arc-elf32-nm"
cp binutils/objcopy "$out/arc-elf32-objcopy"
strip "$out"/arc-elf32-* 2>/dev/null || true
"$out/arc-elf32-as" --version | head -1
