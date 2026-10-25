//! nativescan IMAGE [--relocs OUT.txt] [--verbose]
//!
//! Finds every absolute address into the image in a cartridge's native ARC
//! code and its data, so LeapLoader can relocate the code from the cartridge
//! window (0x8000_0000) to the SD load address. Research tool.
//!
//! 1. Entry points: the function of every (name, function) pair in the native
//!    resource blobs (tags 0x1000/0x1001/0x1009/0x100D/0x3001) and in the
//!    tables their headers point to, whose name is a C string.
//! 2. Speculative recursive descent with Ribbit's decoder from each entry
//!    (branches, calls, switch tables `ld.as rX,[table,rY]` bounded by the
//!    preceding compare): an entry whose paths reach an illegal instruction, or
//!    overlap known code out of step, is dropped as a whole. Code addresses held
//!    in the native data are tried the same way, to a fixed point.
//! 3. Each stretch between verified code inside the code span is code if it
//!    decodes cleanly and ends in step with the next verified instruction,
//!    otherwise data.
//! 4. Long immediates (stored high halfword first) that point into the image are
//!    relocated, except operands of bit operations (masks such as 0x8000_0000).
//!    Words that point into the image are relocated in data: switch tables, data
//!    stretches in the code span, and the native data around the code up to the
//!    end of the native area, stopping at opaque (high-entropy) data, past which
//!    they are only counted as uncertain.
//!
//! --relocs writes one line per word to change: `OFFSET limm|word VALUE`
//! (hex; OFFSET is the file offset, VALUE the address it holds now).

use ribbit_cpu::decode::decode_with;
use ribbit_cpu::disasm::disassemble;
use ribbit_cpu::isa::{BrCond, COND_AL, Dst, Instr, Op, Size, Src, WriteBack};
use std::collections::{BTreeMap, BTreeSet};

/// Tags whose resources are native code or its tables.
const NATIVE_TAGS: [u16; 5] = [0x1000, 0x1001, 0x1009, 0x100D, 0x3001];

struct Image {
    d: Vec<u8>,
    base: u32,
}

impl Image {
    fn inside(&self, v: u32) -> bool {
        v >= self.base && ((v - self.base) as usize) < self.d.len()
    }
    fn word(&self, a: u32) -> Option<u32> {
        let o = a.wrapping_sub(self.base) as usize;
        self.d.get(o..o + 4).map(|b| u32::from_le_bytes(b.try_into().unwrap()))
    }
    fn half(&self, a: u32) -> u16 {
        let o = a.wrapping_sub(self.base) as usize;
        self.d.get(o..o + 2).map_or(0, |b| u16::from_le_bytes([b[0], b[1]]))
    }
    /// A NUL-terminated printable string of 2..=64 characters at `a`.
    fn is_name(&self, a: u32) -> bool {
        let o = a.wrapping_sub(self.base) as usize;
        let Some(s) = self.d.get(o..(o + 65).min(self.d.len())) else { return false };
        match s.iter().position(|&c| c == 0) {
            Some(n) => n >= 2 && s[..n].iter().all(|&c| (0x20..0x7F).contains(&c)),
            None => false,
        }
    }
    fn decode(&self, a: u32) -> Instr {
        decode_with(a, |x| self.half(x))
    }
    /// Shannon entropy (bits per byte) of the 64 bytes at `a`.
    fn entropy(&self, a: u32) -> f64 {
        let o = (a - self.base) as usize;
        let s = &self.d[o..(o + 64).min(self.d.len())];
        let mut n = [0u32; 256];
        s.iter().for_each(|&c| n[c as usize] += 1);
        let len = s.len() as f64;
        n.iter().filter(|&&c| c > 0).map(|&c| -(c as f64 / len) * (c as f64 / len).log2()).sum()
    }
}

fn bad(i: &Instr) -> bool {
    matches!(i.op, Op::Illegal(_) | Op::Arc700Only(_) | Op::Extension { .. })
}

/// Bit operations: a long immediate there is a mask, not an address.
fn is_bit_op(op: Op) -> bool {
    matches!(op, Op::And | Op::Or | Op::Xor | Op::Bic | Op::Tst | Op::Bset | Op::Bclr | Op::Btst | Op::Bxor | Op::Bmsk)
}

#[derive(Default)]
struct Code {
    ins: BTreeMap<u32, Instr>,
    /// Switch tables: address -> entry count.
    tables: BTreeMap<u32, u32>,
}

impl Code {
    /// The instruction covering byte `a`, if any.
    fn at(&self, a: u32) -> Option<(&u32, &Instr)> {
        self.ins.range(..=a).next_back().filter(|(s, i)| a < *s + i.len)
    }
    fn covered(&self, a: u32) -> bool {
        self.at(a).is_some() || self.tables.range(..=a).next_back().is_some_and(|(t, n)| a < t + 4 * n)
    }
}

/// Speculative descent from `entry` against the verified code `known`: the new code, or None
/// if a path reaches an illegal instruction or runs out of step with known code.
fn descend(img: &Image, known: &Code, entry: u32) -> Option<Code> {
    let trace = std::env::var("NS_TRACE").is_ok_and(|t| u32::from_str_radix(&t, 16) == Ok(entry));
    let fail = |why: &str, a: u32| {
        if trace {
            println!("  descent from {entry:08x} fails at {a:08x}: {why}");
        }
        None
    };
    let mut new = Code::default();
    let mut work = vec![entry];
    while let Some(start) = work.pop() {
        let mut a = start;
        let mut bound: Option<u32> = None;
        loop {
            if !img.inside(a) || a & 1 != 0 {
                return fail("outside the image or odd", a);
            }
            if known.ins.contains_key(&a) || new.ins.contains_key(&a) {
                break;
            }
            if known.covered(a) || new.covered(a) {
                return fail("out of step with code or a table", a);
            }
            let i = img.decode(a);
            if bad(&i) {
                return fail("illegal instruction", a);
            }
            new.ins.insert(a, i);
            // Overlapping the start of known code out of step.
            if (1..i.len).any(|k| known.ins.contains_key(&(a + k)) || new.ins.contains_key(&(a + k))) {
                return fail("overlaps the start of other code", a);
            }
            match (i.op, i.src2) {
                // `brhs rY,N,default` leaves N entries; `cmp rY,N` (then bhi) N + 1.
                (Op::Br(BrCond::Hs), Src::Imm(n)) if n < 1024 => bound = Some(n),
                (Op::Cmp | Op::Br(_), Src::Imm(n)) if n < 1024 => bound = Some(n + 1),
                _ => {}
            }
            let target = match i.op {
                Op::J | Op::Jl => match (i.src1, i.src2) {
                    (Src::Limm(v), _) | (_, Src::Limm(v)) => Some(v),
                    _ => None,
                },
                Op::B | Op::Bl | Op::Br(_) | Op::Bbit0 | Op::Bbit1 | Op::Lp => Some(i.target),
                _ => None,
            };
            if let Some(t) = target {
                work.push(t);
            }
            if i.op == Op::Ld && i.mem.size == Size::Word {
                if let Src::Limm(t) = i.src1 {
                    if img.inside(t) && !known.tables.contains_key(&t) && !new.tables.contains_key(&t) {
                        let mut n = 0;
                        while let Some(v) = img.word(t + 4 * n) {
                            if !img.inside(v) || v & 1 != 0 || n >= bound.unwrap_or(1024) || v.abs_diff(t) > 0x10000 {
                                break;
                            }
                            work.push(v);
                            n += 1;
                        }
                        if n > 0 {
                            new.tables.insert(t, n);
                        }
                    }
                }
            }
            let ends = i.cc == COND_AL && matches!(i.op, Op::B | Op::J);
            if ends {
                if i.delay && !known.ins.contains_key(&i.next()) {
                    let d = img.decode(i.next());
                    if bad(&d) {
                        return None;
                    }
                    new.ins.insert(i.next(), d);
                }
                break;
            }
            a = i.next();
        }
    }
    Some(new)
}

/// A weak entry (a code address found in data, or the start of an unreached stretch) is only
/// tried where a function plausibly starts: at a prologue (push_s blink/r13.., st.aw rN,[sp,-4],
/// sub sp, mov rN,blink), or right after an unconditional return or jump of verified code.
/// Misaligned ARCompact often decodes cleanly for a while, so anything else is too risky.
fn plausible_start(img: &Image, code: &Code, v: u32) -> bool {
    let i = img.decode(v);
    let prologue = match i.op {
        Op::Push => true,
        Op::St => i.mem.wb == WriteBack::Pre && i.src1 == Src::Reg(28),
        Op::Sub => i.dst == Dst::Reg(28),
        Op::Mov => i.src1 == Src::Reg(31) || i.src2 == Src::Reg(31),
        _ => false,
    };
    let ends_flow = |j: &Instr| j.cc == COND_AL && matches!(j.op, Op::B | Op::J);
    let mut before = code.ins.range(..v).rev();
    let after_jump = match (before.next(), before.next()) {
        (Some((&a, j)), prev) if a + j.len == v => {
            (ends_flow(j) && !j.delay) || prev.is_some_and(|(&pa, p)| pa + p.len == a && ends_flow(p) && p.delay)
        }
        _ => false,
    };
    prologue || after_jump
}

fn hex(v: u32) -> String {
    format!("{v:08x}")
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let d = ribbit_core::read_image(&args[0]).expect("image");
    let mut relocs_out = None;
    let mut verbose = false;
    let mut it = args[1..].iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--relocs" => relocs_out = it.next().cloned(),
            "--verbose" => verbose = true,
            other => panic!("unknown argument {other}"),
        }
    }
    let u32_at = |o: usize| u32::from_le_bytes(d[o..o + 4].try_into().unwrap());
    let u16_at = |o: usize| u16::from_le_bytes(d[o..o + 2].try_into().unwrap());
    let base = u32_at(0x11C);
    let img = Image { d: d.clone(), base };
    let end = base + d.len() as u32;

    // Resource blobs, native and other.
    let leap = (u32_at(0x140) - base) as usize;
    let (mut native, mut other) = (vec![], vec![]);
    // Where each resource, directory list or header starts: true for native blobs. Native
    // data is only looked for from a native blob to the next start of anything.
    let mut starts: BTreeMap<u32, bool> = BTreeMap::new();
    starts.insert(base, false);
    starts.insert(base + leap as u32, false);
    for i in 0..u16_at(leap + 6) as usize {
        let e = leap + 0x20 + 8 * i;
        let (tag, count, list) = (u16_at(e), u16_at(e + 2), u32_at(e + 4));
        starts.insert(list, false);
        for j in 0..count as usize {
            let v = u32_at((list - base) as usize + 8 * j + 4);
            if img.inside(v) {
                if NATIVE_TAGS.contains(&tag) { native.push((v, tag)) } else { other.push((v, tag)) }
                let is_native = NATIVE_TAGS.contains(&tag);
                starts.entry(v).and_modify(|n| *n &= is_native).or_insert(is_native);
            }
        }
    }
    // Save descriptors (0x1005) have a known size (0x18 bytes, or 0x2C in the long form with
    // function addresses); what follows one is whatever came before it (often native data).
    for &(v, tag) in &other {
        if tag == 0x1005 {
            let len = if img.word(v + 0x18) == Some(0) { 0x2C } else { 0x18 };
            let before = starts.range(..v).next_back().is_some_and(|(_, &n)| n);
            starts.entry(v + len).or_insert(before);
        }
    }
    native.sort();
    if native.is_empty() {
        println!("no native resources");
        return;
    }

    // Named native functions, from the two table layouts that are understood:
    // 0x1009 {0x100, 0, count << 16, pairs}, 0x1000 {0x100, RAM, size, INI, pairs...};
    // pairs are (name, function).
    let mut strong = BTreeSet::new();
    for &(b, tag) in &native {
        let pairs: Vec<(u32, u32)> = match tag {
            0x1009 => {
                let (n, t) = (img.word(b + 8).unwrap_or(0) >> 16, img.word(b + 12).unwrap_or(0));
                (0..n).map(|k| (img.word(t + 8 * k).unwrap_or(0), img.word(t + 8 * k + 4).unwrap_or(0))).collect()
            }
            0x1000 => (0..256)
                .map(|k| (img.word(b + 16 + 8 * k).unwrap_or(0), img.word(b + 20 + 8 * k).unwrap_or(0)))
                .take_while(|&(n, f)| img.inside(n) && img.inside(f) && img.is_name(n))
                .collect(),
            _ => vec![],
        };
        for (n, f) in pairs {
            if img.is_name(n) && img.inside(f) && !img.is_name(f) {
                strong.insert(f);
            }
        }
    }
    // Other candidates: (name, function)-like pairs anywhere in the native blobs.
    let mut seeds = strong.clone();
    for &(b, _) in &native {
        let header = (0..4).filter_map(|k| img.word(b + 4 * k)).filter(|&v| img.inside(v));
        let from = header.fold(b, u32::min) & !3;
        let mut a = from;
        while a < b + 0x1000 {
            if let (Some(n), Some(f)) = (img.word(a), img.word(a + 4)) {
                if img.inside(n) && img.inside(f) && f & 1 == 0 && img.is_name(n) && !img.is_name(f) {
                    seeds.insert(f);
                }
            }
            a += 4;
        }
    }
    let mut code = Code::default();
    let (mut accepted, mut rejected) = (BTreeSet::new(), BTreeSet::new());
    let mut try_entry = |code: &mut Code, e: u32| {
        if code.ins.contains_key(&e) || rejected.contains(&e) {
            return;
        }
        match descend(&img, code, e) {
            Some(new) => {
                code.ins.extend(new.ins);
                code.tables.extend(new.tables);
                accepted.insert(e);
            }
            None => {
                rejected.insert(e);
            }
        }
    };
    for &e in &strong {
        try_entry(&mut code, e);
    }
    // The other candidates only inside the span the named functions cover (if any).
    let span = |c: &Code| c.ins.keys().next().map(|&lo| (lo, c.ins.iter().map(|(a, i)| a + i.len).max().unwrap()));
    let strong_span = span(&code);
    for &e in seeds.difference(&strong) {
        if strong_span.is_none_or(|(lo, hi)| e >= lo && e < hi) && (strong.is_empty() || plausible_start(&img, &code, e)) {
            try_entry(&mut code, e);
        }
    }
    if code.ins.is_empty() {
        println!("no native code found from {} entries", seeds.len());
        return;
    }
    let seeded_hi = code.ins.iter().map(|(a, i)| a + i.len).max().unwrap();
    let code_lo = *code.ins.keys().next().unwrap();

    // The native area: from the lowest native blob or the code, to the first non-native
    // resource above both; the native data in it ends at opaque data.
    let area_lo = code_lo.min(native[0].0) & !3;
    let top = seeded_hi.max(native.last().unwrap().0);
    let area_end = other.iter().map(|o| o.0).filter(|&v| v > top).min().unwrap_or(end).min(end);
    // Opaque: 512 bytes in a row of high-entropy 64-byte windows (compressed data; a table of
    // floating-point constants is shorter).
    let mut data_end = area_end;
    let mut a = (top + 63) & !63;
    let mut run_start = None;
    while a + 64 <= area_end {
        if img.entropy(a) > 5.6 {
            let s = *run_start.get_or_insert(a);
            if a + 64 - s >= 512 {
                data_end = s;
                break;
            }
        } else {
            run_start = None;
        }
        a += 64;
    }

    // RAM initialisers ("INI" blocks, from the 0x1000 headers): records {RAM address, length,
    // data} (a negative length zero-fills). Their data is copied to RAM at start and holds
    // code addresses (constructor tables), wherever the block lies.
    let mut ini_words = vec![];
    for &(b, tag) in &native {
        let Some(ini) = img.word(b + 12).filter(|&v| tag == 0x1000 && img.inside(v)) else { continue };
        if img.word(ini).map(|w| w & 0xFF_FFFF) != Some(0x49_4E49) {
            continue;
        }
        let mut r = ini + 4;
        for _ in 0..64 {
            let (Some(dst), Some(len)) = (img.word(r), img.word(r + 4)) else { break };
            if !(0x3C00_0000..0x3D00_0000).contains(&dst) {
                break;
            }
            if (len as i32) < 0 {
                r += 8;
                continue;
            }
            let n = (len + 3) & !3;
            if n > 0x10_0000 {
                break;
            }
            ini_words.extend((0..n / 4).map(|k| r + 8 + 4 * k));
            r += 8 + n;
        }
    }

    // Code addresses held in the native data (function pointers, vtables), to a fixed point.
    starts.entry(seeded_hi).or_insert(true);
    for &a in &ini_words {
        if let Some(v) = img.word(a).filter(|&v| v >= code_lo && v < seeded_hi && v & 1 == 0) {
            try_entry(&mut code, v);
        }
    }
    loop {
        let before = code.ins.len();
        let mut a = area_lo;
        while a + 4 <= data_end {
            let native_here = starts.range(..=a).next_back().is_some_and(|(_, &n)| n);
            if native_here && !code.covered(a) {
                if let Some(v) = img.word(a) {
                    if v >= code_lo && v < seeded_hi && v & 1 == 0 && plausible_start(&img, &code, v) {
                        try_entry(&mut code, v);
                    }
                }
            }
            a += 4;
        }
        if code.ins.len() == before {
            break;
        }
    }
    // Functions reached only through computed addresses: try each stretch between verified
    // code as an entry (its switch tables are found that way), to a fixed point.
    loop {
        let before = code.ins.len();
        let ends: Vec<u32> = code.ins.iter().map(|(a, i)| a + i.len).collect();
        for e in ends {
            if e < seeded_hi && !code.covered(e) && plausible_start(&img, &code, e) {
                try_entry(&mut code, e);
            }
        }
        if code.ins.len() == before {
            break;
        }
    }
    let span_lo = *code.ins.keys().next().unwrap();
    let span_hi = code.ins.iter().map(|(a, i)| a + i.len).max().unwrap();
    // The code's own data follows it.
    starts.entry(span_hi).or_insert(true);

    // Stretches between verified code: code if they decode cleanly in step, else data.
    let mut data_gaps = vec![];
    let mut code_gaps = 0;
    let verified: Vec<(u32, u32)> = {
        let mut r: Vec<(u32, u32)> = vec![];
        for (&a, i) in &code.ins {
            match r.last_mut() {
                Some(l) if a == l.1 => l.1 = a + i.len,
                _ => r.push((a, a + i.len)),
            }
        }
        for (&t, &n) in &code.tables {
            r.push((t, t + 4 * n));
        }
        r.sort();
        r
    };
    let mut extra = BTreeMap::new();
    for w in verified.windows(2) {
        let (g0, g1) = (w[0].1, w[1].0);
        if g1 <= g0 {
            continue;
        }
        let mut a = g0;
        let mut ok = true;
        let mut ins = vec![];
        while a < g1 {
            let i = img.decode(a);
            if bad(&i) {
                ok = false;
                break;
            }
            ins.push(i);
            a += i.len;
        }
        // All zero or padding-only stretches are left alone either way.
        if ok && a == g1 {
            code_gaps += 1;
            for i in ins {
                extra.insert(i.addr, i);
            }
        } else {
            data_gaps.push((g0, g1));
        }
    }
    code.ins.extend(extra);

    let mut relocs: Vec<(u32, &str, u32)> = vec![];
    let mut masks = vec![];
    for (&a, i) in &code.ins {
        if let Some(v) = i.limm.filter(|&v| img.inside(v)) {
            if is_bit_op(i.op) {
                masks.push((a, v, disassemble(i)));
            } else {
                relocs.push((i.next() - 4, "limm", v));
                if verbose {
                    println!("  limm {} {}  {}: {}", hex(i.next() - 4), hex(v), hex(a), disassemble(i));
                }
            }
        }
    }
    let n_limm = relocs.len();
    // Erased padding (runs of 256+ bytes of 0xFF): no pointer aims into one (past its first
    // 16 bytes, where a resource that ends there might point), so a word that does is a
    // number that only looks like an address (e.g. two 16-bit values 0x806A, 0x806B).
    let mut padding: Vec<(u32, u32)> = vec![];
    let mut run = None;
    for (k, &c) in d.iter().enumerate() {
        match (c == 0xFF, run) {
            (true, None) => run = Some(k),
            (false, Some(s)) => {
                if k - s >= 256 {
                    padding.push((base + s as u32, base + k as u32));
                }
                run = None;
            }
            _ => {}
        }
    }
    if let Some(s) = run.filter(|&s| d.len() - s >= 256) {
        padding.push((base + s as u32, end));
    }
    let in_padding = |v: u32| {
        let i = padding.partition_point(|p| p.0 <= v);
        i > 0 && v >= padding[i - 1].0 + 16 && v < padding[i - 1].1
    };
    let mut not_pointers = 0;
    let mut data_word = |relocs: &mut Vec<(u32, &str, u32)>, a: u32| {
        if let Some(v) = img.word(a).filter(|&v| img.inside(v)) {
            if in_padding(v) {
                not_pointers += 1;
            } else {
                relocs.push((a, "word", v));
            }
        }
    };
    for (&t, &n) in &code.tables {
        (0..n).for_each(|k| data_word(&mut relocs, t + 4 * k));
    }
    for &a in &ini_words {
        data_word(&mut relocs, a);
    }
    // The (name, function) lists that 0x1009 headers point to, wherever they lie (Cosmic Math's
    // follows a non-native resource).
    for &(b, tag) in &native {
        if tag == 0x1009 {
            let (n, t) = (img.word(b + 8).unwrap_or(0) >> 16, img.word(b + 12).unwrap_or(0));
            if img.inside(t) {
                (0..2 * n).for_each(|k| data_word(&mut relocs, t + 4 * k));
            }
        }
    }
    for &(g0, g1) in &data_gaps {
        let mut a = (g0 + 3) & !3;
        while a + 4 <= g1 {
            data_word(&mut relocs, a);
            a += 4;
        }
    }
    let in_native = |a: u32| starts.range(..=a).next_back().is_some_and(|(_, &n)| n);
    let mut a = area_lo;
    while a + 4 <= data_end {
        if (a + 4 <= span_lo || a >= span_hi) && in_native(a) {
            data_word(&mut relocs, a);
        }
        a += 4;
    }
    // Data sections away from the code (the large games keep their C++ data, vtables and
    // strings near the end of the image, e.g. NASCAR's at 0x803E_4xxx): clusters of 8 or more
    // long-immediate targets outside the code and the native area. Their words are scanned
    // from the first target to 1 KiB past the last, skipping high-entropy 64-byte windows.
    let mut targets: Vec<u32> = relocs[..n_limm].iter().map(|r| r.2)
        .filter(|&v| !(v >= span_lo && v < span_hi) && !(v >= area_lo && v < data_end))
        // Not the header and resource directory (code reads the image's own header through
        // the base address; its words are handled by sdpack, and some must not change).
        .filter(|&v| v >= base + 0x2000).collect();
    targets.sort();
    let mut sections: Vec<(u32, u32, usize)> = vec![];
    for v in targets {
        match sections.last_mut() {
            Some(c) if v - c.1 <= 0x4000 => {
                c.1 = v;
                c.2 += 1;
            }
            _ => sections.push((v, v, 1)),
        }
    }
    sections.retain(|c| c.2 >= 8);
    let mut section_words = 0;
    for &(lo, hi, _) in &sections {
        let (lo, hi) = (lo & !3, (hi + 0x400).min(end - 4));
        let mut a = lo;
        while a + 4 <= hi {
            if a & 63 == 0 && img.entropy(a) > 5.6 {
                a += 64;
                continue;
            }
            if !code.covered(a) {
                let n = relocs.len();
                data_word(&mut relocs, a);
                section_words += relocs.len() - n;
            }
            a += 4;
        }
    }
    let before = relocs.len();
    relocs.retain(|r| !in_padding(r.2));
    let n_limm = n_limm - (before - relocs.len());
    let not_pointers = not_pointers + (before - relocs.len());
    let mut uncertain = 0;
    let mut a = (data_end + 3) & !3;
    while a + 4 <= area_end {
        if img.word(a).is_some_and(|v| img.inside(v)) {
            uncertain += 1;
        }
        a += 4;
    }
    relocs.sort();
    relocs.dedup();

    println!("base {base:#010x}, {} native blobs from {}, {} seeds, {} entries accepted, {} rejected",
             native.len(), hex(native[0].0), seeds.len(), accepted.len(), rejected.len());
    println!("code {}-{}: {} instructions, {} switch tables, {} stretches taken as code, {} as data",
             hex(span_lo), hex(span_hi), code.ins.len(), code.tables.len(), code_gaps, data_gaps.len());
    println!("native area {}-{}, native data ends {}{}", hex(area_lo), hex(area_end), hex(data_end),
             if data_end < area_end { " (opaque data follows)" } else { "" });
    println!("{} long immediates and {} data words to relocate; {} masks left alone; {} uncertain words after the native data",
             n_limm, relocs.len() - n_limm, masks.len(), uncertain);
    println!("{not_pointers} data words left alone: they point into erased padding");
    println!("{} data sections away from the code ({} words to relocate){}", sections.len(), section_words,
             sections.iter().map(|c| format!(" {}-{}", hex(c.0), hex(c.1))).collect::<String>());
    if verbose {
        for (a, v, t) in &masks {
            println!("  mask {}: {} ({})", hex(*a), t, hex(*v));
        }
        for (g0, g1) in &data_gaps {
            println!("  data stretch {}-{}", hex(*g0), hex(*g1));
        }
        for e in rejected.iter().filter(|&&e| std::env::var("NS_NEAR").map_or(true, |n| e.abs_diff(u32::from_str_radix(&n, 16).unwrap()) < 0x400)).take(30) {
            println!("  rejected entry {}", hex(*e));
        }
    }
    // Every named native function must decode: otherwise the code is not understood.
    println!("{} named native functions in 0x1000/0x1009 tables", strong.len());
    let bad_seeds: Vec<String> = strong.iter().filter(|e| rejected.contains(e)).map(|&e| hex(e)).collect();
    if bad_seeds.is_empty() {
        println!("VERDICT ok");
    } else {
        println!("VERDICT doubt: {} named native functions do not decode: {}", bad_seeds.len(), bad_seeds.join(" "));
    }
    if let Some(p) = relocs_out {
        let mut out = String::new();
        for (a, k, v) in &relocs {
            out += &format!("{:x} {k} {v:x}\n", a - base);
        }
        std::fs::write(&p, out).expect("write relocs");
        println!("wrote {} relocations to {p}", relocs.len());
    }
}
