//! snesbench: runs a flat ARC binary (linked at its load address) on Ribbit's
//! CPU model with the memory-system timing calibrated against a real Leapster
//! (`ribbit_core::io::memtiming`), and prints the cycles between the frame
//! markers the program writes.
//!
//! Run: snesbench PROGRAM.bin [--base 0x3C100000] [--max-frames N] [--profile SYMBOLS]
//! (--profile: `nm -n` output for the program; cycles per function (or a
//! cache's misses with SNESBENCH_MISSES=i/d/wb) are
//! printed at the end, after the first frame)
//!
//! The program sees plain RAM from 0x3C00_0000 to 0x4000_0000 (64 MiB: more
//! than the console's 16, so a port can be measured before it is made to
//! fit) and three registers:
//!   0x0180_FF00 write: a character of output (stdout)
//!   0x0180_FF04 write: end of an emulated frame (the value is printed)
//!   0x0180_FF08 write: stop, with the value as the exit code
//!   0x0180_FF10/14/18 write: width, height, pitch (bytes) of a screenshot;
//!   then 0x0180_FF0C write: its address (RGB565): saved as shot-NNNNN.ppm
//!   0x0180_FF20 read32: the CPU cycle count (low 32 bits), for frame pacing
//!   in the current folder (NNNNN = frames so far)
//! Cycles are at 96 MHz, the nominal clock (Ribbit's `NOMINAL_CPU_HZ`).

use ribbit_core::io::memtiming::MemTiming;
use ribbit_cpu::{Cpu, CpuConfig};
use ribbit_memory::Bus;
use std::io::Write;

const RAM_BASE: u32 = 0x3C00_0000;
const RAM_SIZE: usize = 64 << 20;
/// The Leapster 2's on-chip video RAM (the LCD scans it), kept after RAM in `ram`
const VRAM_BASE: u32 = 0x0300_0000;
const VRAM_SIZE: usize = 64 << 10;
const PUTC: u32 = 0x0180_FF00;
const FRAME: u32 = 0x0180_FF04;
const EXIT: u32 = 0x0180_FF08;
const SHOT: u32 = 0x0180_FF0C;
const CLOCK: u32 = 0x0180_FF20;
const HZ: f64 = 96_000_000.0;

struct Flat {
    ram: Vec<u8>,
    mem: MemTiming,
    frame: Option<u32>,
    exit: Option<u32>,
    out: Vec<u8>,
    shot: [u32; 3],
    frames: u64,
    clock: u64,
    last_pc: u32,
    /// misaligned 16/32-bit data accesses (the ARC600 has no unaligned access) and the first one's pc
    misaligned: (u64, u32),
}

impl Flat {
    #[inline(always)]
    fn off(&self, addr: u32, len: usize) -> Option<usize> {
        let off = addr.wrapping_sub(RAM_BASE) as usize;
        if off + len <= RAM_SIZE {
            return Some(off);
        }
        let v = addr.wrapping_sub(VRAM_BASE) as usize;
        (v + len <= VRAM_SIZE).then_some(RAM_SIZE + v)
    }
    #[inline(always)]
    fn align(&mut self, addr: u32, len: u32) {
        if addr & (len - 1) != 0 {
            if self.misaligned.0 == 0 {
                self.misaligned.1 = self.last_pc;
            }
            self.misaligned.0 += 1;
        }
    }
    fn bad(&self, what: &str, addr: u32) -> ! {
        panic!("{what} outside RAM at {addr:#010x} (pc {:#010x})", self.last_pc);
    }
    fn device_write(&mut self, addr: u32, value: u32) {
        self.mem.device();
        match addr {
            PUTC => self.out.push(value as u8),
            FRAME => self.frame = Some(value),
            EXIT => self.exit = Some(value),
            SHOT => self.screenshot(value),
            0x0180_FF10..=0x0180_FF18 => self.shot[(addr - 0x0180_FF10) as usize / 4] = value,
            _ => self.bad("write", addr),
        }
    }
}

impl Flat {
    fn screenshot(&self, addr: u32) {
        let [w, h, pitch] = self.shot;
        let mut ppm = format!("P6
{w} {h}
255
").into_bytes();
        for y in 0..h {
            for x in 0..w {
                let Some(o) = self.off(addr + y * pitch + x * 2, 2) else { self.bad("screenshot", addr) };
                let p = u16::from_le_bytes([self.ram[o], self.ram[o + 1]]);
                let (r, g, b) = (p >> 11, (p >> 5) & 63, p & 31);
                ppm.extend([(r << 3 | r >> 2) as u8, (g << 2 | g >> 4) as u8, (b << 3 | b >> 2) as u8]);
            }
        }
        let name = format!("shot-{:05}.ppm", self.frames);
        std::fs::write(&name, ppm).unwrap();
        eprintln!("saved {name} ({w}x{h})");
    }
}

impl Bus for Flat {
    fn read8(&mut self, addr: u32) -> u8 {
        let Some(o) = self.off(addr, 1) else { self.bad("read8", addr) };
        self.mem.data(addr, false);
        self.ram[o]
    }
    fn read16(&mut self, addr: u32) -> u16 {
        self.align(addr, 2);
        let Some(o) = self.off(addr, 2) else { self.bad("read16", addr) };
        self.mem.data(addr, false);
        u16::from_le_bytes([self.ram[o], self.ram[o + 1]])
    }
    fn read32(&mut self, addr: u32) -> u32 {
        self.align(addr, 4);
        if addr == CLOCK {
            self.mem.device();
            return self.clock as u32;
        }
        let Some(o) = self.off(addr, 4) else { self.bad("read32", addr) };
        self.mem.data(addr, false);
        u32::from_le_bytes(self.ram[o..o + 4].try_into().unwrap())
    }
    fn write8(&mut self, addr: u32, value: u8) {
        let Some(o) = self.off(addr, 1) else { return self.device_write(addr, value.into()) };
        self.mem.data(addr, true);
        self.ram[o] = value;
    }
    fn write16(&mut self, addr: u32, value: u16) {
        self.align(addr, 2);
        let Some(o) = self.off(addr, 2) else { return self.device_write(addr, value.into()) };
        self.mem.data(addr, true);
        self.ram[o..o + 2].copy_from_slice(&value.to_le_bytes());
    }
    fn write32(&mut self, addr: u32, value: u32) {
        self.align(addr, 4);
        let Some(o) = self.off(addr, 4) else { return self.device_write(addr, value) };
        self.mem.data(addr, true);
        self.ram[o..o + 4].copy_from_slice(&value.to_le_bytes());
    }
    fn fetch16(&mut self, addr: u32) -> u16 {
        let Some(o) = self.off(addr, 2) else { self.bad("fetch", addr) };
        u16::from_le_bytes([self.ram[o], self.ram[o + 1]])
    }
    fn instruction(&mut self, pc: u32, len: u32) {
        self.last_pc = pc;
        self.mem.instruction(pc, len);
    }
    fn instruction_same_line(&mut self) {
        self.mem.instruction_same_line();
    }
    fn take_stall(&mut self) -> u64 {
        self.mem.take_stall()
    }
}

fn number(s: &str) -> u64 {
    s.strip_prefix("0x").map_or_else(|| s.parse().unwrap(), |h| u64::from_str_radix(h, 16).unwrap())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut base = 0x3C10_0000u32;
    let mut max_frames = u64::MAX;
    let mut path = None;
    let mut profile: Option<Vec<(u32, String)>> = None;
    // SNESBENCH_MISSES=i|d|wb: the profile counts that cache's misses instead of cycles
    let miss_kind = match std::env::var("SNESBENCH_MISSES").as_deref() {
        Ok("i") => 0,
        Ok("d") => 1,
        Ok("wb") => 2,
        _ => 3,
    };
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--base" => (base, i) = (number(&args[i + 1]) as u32, i + 1),
            "--max-frames" => (max_frames, i) = (number(&args[i + 1]), i + 1),
            "--profile" => {
                let text = std::fs::read_to_string(&args[i + 1]).unwrap();
                let mut syms: Vec<(u32, String)> = text
                    .lines()
                    .filter_map(|l| {
                        let mut f = l.split_whitespace();
                        let (a, t, n) = (f.next()?, f.next()?, f.next()?);
                        matches!(t, "T" | "t").then(|| (u32::from_str_radix(a, 16).ok().unwrap(), n.to_string()))
                    })
                    .collect();
                syms.sort();
                profile = Some(syms);
                i += 1;
            }
            p => path = Some(p.to_string()),
        }
        i += 1;
    }
    let path = path.expect("usage: snesbench PROGRAM.bin [--base ADDR] [--max-frames N]");
    let program = std::fs::read(&path).unwrap();
    let mut bus = Flat { ram: vec![0; RAM_SIZE + VRAM_SIZE], mem: MemTiming::default(), frame: None, exit: None, out: vec![], shot: [0; 3], frames: 0, clock: 0, last_pc: 0, misaligned: (0, 0) };
    let off = (base - RAM_BASE) as usize;
    bus.ram[off..off + program.len()].copy_from_slice(&program);

    let mut cpu = Cpu::new(CpuConfig::leapster());
    cpu.reset();
    cpu.pc = base;
    let wall = std::time::Instant::now();
    let (mut last, mut last_instr, mut frames, mut total) = (0u64, 0u64, 0u64, Vec::new());
    let mut by_pc: std::collections::HashMap<u32, u64> = std::collections::HashMap::new();
    loop {
        let (pc, before, mb) = (cpu.pc, cpu.cycles, bus.mem.misses[miss_kind.min(2)]);
        bus.clock = cpu.cycles;
        if let Err(e) = cpu.step(&mut bus) {
            eprintln!("CPU stopped: {e:?}\n{cpu:?}");
            std::process::exit(2);
        }
        if profile.is_some() && frames > 0 {
            *by_pc.entry(pc).or_default() +=
                if miss_kind == 3 { cpu.cycles - before } else { bus.mem.misses[miss_kind.min(2)] - mb };
        }
        if !bus.out.is_empty() && bus.out.ends_with(b"\n") {
            print!("{}", String::from_utf8_lossy(&bus.out));
            bus.out.clear();
        }
        if let Some(v) = bus.frame.take() {
            let (c, n) = (cpu.cycles - last, cpu.instructions_retired - last_instr);
            println!(
                "frame {v:5}: {c:11} cycles ({:6.2} ms at 96 MHz, {:5.1}% of a 60 Hz frame), {n} instructions, {:.2} cycles/instr",
                c as f64 / HZ * 1e3,
                c as f64 / (HZ / 60.0) * 100.0,
                c as f64 / n.max(1) as f64
            );
            total.push(c);
            (last, last_instr) = (cpu.cycles, cpu.instructions_retired);
            frames += 1;
            bus.frames = frames;
            if frames >= max_frames {
                break;
            }
        }
        if let Some(code) = bus.exit {
            print!("{}", String::from_utf8_lossy(&bus.out));
            println!("exit {code}");
            break;
        }
    }
    if let Some(syms) = &profile {
        let mut by_fn: std::collections::HashMap<&str, u64> = std::collections::HashMap::new();
        for (&pc, &c) in &by_pc {
            let i = syms.partition_point(|(a, _)| *a <= pc);
            *by_fn.entry(if i == 0 { "?" } else { &syms[i - 1].1 }).or_default() += c;
        }
        let all: u64 = by_fn.values().sum();
        let mut list: Vec<_> = by_fn.into_iter().collect();
        list.sort_by(|a, b| b.1.cmp(&a.1));
        let top: usize = std::env::var("SNESBENCH_TOP").ok().and_then(|v| v.parse().ok()).unwrap_or(30);
        for (name, c) in list.iter().take(top) {
            println!("PROFILE {:5.1}% {name}", *c as f64 * 100.0 / all as f64);
        }
        // The hottest addresses, for reading against a disassembly.
        let mut pcs: Vec<_> = by_pc.iter().collect();
        pcs.sort_by(|a, b| b.1.cmp(a.1));
        for (pc, c) in pcs.iter().take(60) {
            println!("PROFILE-PC {:5.2}% {pc:08x}", **c as f64 * 100.0 / all as f64);
        }
    }
    let _ = std::io::stdout().flush();
    if total.len() > 1 {
        // The first frame includes start-up.
        let rest = &total[1..];
        let avg = rest.iter().sum::<u64>() as f64 / rest.len() as f64;
        let max = *rest.iter().max().unwrap();
        println!(
            "SUMMARY frames {} (after the first): average {:.0} cycles = {:.1}% of a 60 Hz frame at 96 MHz ({:.1}% at 48 MHz); worst {:.1}%; {} cycles total; misses i/d/wb {:?}; {:.1} s wall",
            rest.len(),
            avg,
            avg / (HZ / 60.0) * 100.0,
            avg / (HZ / 2.0 / 60.0) * 100.0,
            max as f64 / (HZ / 60.0) * 100.0,
            cpu.cycles,
            bus.mem.misses,
            wall.elapsed().as_secs_f64()
        );
        if bus.misaligned.0 != 0 {
            println!("MISALIGNED {} accesses, the first at pc {:#010x}", bus.misaligned.0, bus.misaligned.1);
        }
    }
}
