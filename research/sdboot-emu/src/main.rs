//! Research harness for LeapLoader Phase 2a: boots a Leapster 2 BIOS in
//! Ribbit's emulator with the boot selector (0x0180_B008) set to the SD
//! developer load and an emulated SD card holding chosen files, then reports
//! the BIOS's own log calls, restarts and screenshots.
//!
//! Usage:
//!   sdboot-emu --bios BIOS.bin [options]
//!     --ms N              emulated milliseconds to run (default 8000)
//!     --b008 HEX          boot selector value (default 5: bits 1-2 = 10, SD load)
//!     --put CARD=LOCAL    copy a local file onto the card, e.g. Leapster/Game.bin=game.bin
//!     --text CARD=TEXT    write a text file onto the card
//!     --tree DIR          copy a local folder tree onto the card root
//!     --log PC[:REG]      a printf-style log function and its format register (repeatable;
//!                         default 0x40042F98:0, the BootSystem log of BIOS 0.6. 0x400F00C8:1 is
//!                         the system's levelled debug log (r0 = level), very chatty)
//!     --trace PC          also print r0-r3 and blink each time PC runs (repeatable)
//!     --shot-every MS     screenshot every MS into --out (default 1000)
//!     --out DIR           output directory for screenshots (default .)
//!     --dump ADDR:LEN:FILE  at the end, write memory to FILE
//!     --cart CART.bin     also insert a cartridge
//!     --card-format F     factory (default) | mbr-fat16 | mbr-fat32 | bare-fat16
//!     --profile-from MS   from MS on, sample the PC every 1000 cycles and print the hottest PCs
//!     --script FILE       run a script instead of --ms. Lines: run MS | tap X Y [MS] (LCD pixels) |
//!                         btn NAME [MS] | shot NAME | save STATE | load STATE | card (rewrite the
//!                         add the --put/--text files to the card, e.g. after load) | ls (card files) | power (power cycle) | trace PC | cat CARDPATH | hold NAME | release NAME | export RIBBIT_SDCARD.img | b008 HEX | say TEXT (shown
//!                         in the window title) | wait (keep the window open until closed) | play (interactive until closed: arrows,
//!                         Enter/Z = A, X = B, H = Hint, P = Pause, Esc = Home, mouse = stylus)
//!     --view              show the LCD live in a window, paced to real time
//!
//! Nothing here is LeapLoader's product code; it exists to answer the
//! questions in docs/research-report.md §8 before anything is built on them.

use fatfs::{FileSystem, FsOptions};
use ribbit_core::Machine;
use ribbit_debug::Breakpoints;
use ribbit_video::{HEIGHT, WIDTH};
use std::collections::BTreeMap;
use std::io::{Read, Seek, SeekFrom, Write};

const SECTOR: usize = 512;

/// A disk image held as sparse 512-byte sectors (absent sectors read as zeros),
/// in the shape Ribbit's SD card model stores.
struct SparseDisk {
    sectors: BTreeMap<u32, Vec<u8>>,
    /// Byte offset of this view (a partition) on the card, and its size.
    base: u64,
    size: u64,
    pos: u64,
}

impl Read for SparseDisk {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        let n = buf.len().min(self.size.saturating_sub(self.pos) as usize);
        for (i, b) in buf[..n].iter_mut().enumerate() {
            let p = self.base + self.pos + i as u64;
            *b = self.sectors.get(&((p / SECTOR as u64) as u32)).map_or(0, |s| s[(p % SECTOR as u64) as usize]);
        }
        self.pos += n as u64;
        Ok(n)
    }
}

impl Write for SparseDisk {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        let n = buf.len().min(self.size.saturating_sub(self.pos) as usize);
        for (i, &b) in buf[..n].iter().enumerate() {
            let p = self.base + self.pos + i as u64;
            let s = self.sectors.entry((p / SECTOR as u64) as u32).or_insert_with(|| vec![0; SECTOR]);
            s[(p % SECTOR as u64) as usize] = b;
        }
        self.pos += n as u64;
        Ok(n)
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

impl Seek for SparseDisk {
    fn seek(&mut self, to: SeekFrom) -> std::io::Result<u64> {
        self.pos = match to {
            SeekFrom::Start(p) => p,
            SeekFrom::End(d) => (self.size as i64 + d) as u64,
            SeekFrom::Current(d) => (self.pos as i64 + d) as u64,
        };
        Ok(self.pos)
    }
}

fn hex(s: &str) -> u32 {
    u32::from_str_radix(s.trim_start_matches("0x").trim_start_matches("0X"), 16).expect("hex number")
}

/// How the emulated card is formatted before files are added (--card-format).
static CARD_FORMAT: std::sync::OnceLock<String> = std::sync::OnceLock::new();

/// Builds a card and adds `files` (card path with '/' separators, contents).
/// Formats: `factory` (Ribbit's copy of what BIOS B5 formats: FAT32, no
/// partition table), `mbr-fat16` / `mbr-fat32` (a partition table with one
/// partition at sector 2048, as Windows writes), `bare-fat16` (FAT16, no table).
fn build_card(files: &[(String, Vec<u8>)]) -> BTreeMap<u32, Vec<u8>> {
    let total = ribbit_core::io::sd::CARD_SECTORS;
    let format = CARD_FORMAT.get().map_or("factory", |s| s.as_str());
    let sectors = match format {
        "factory" => ribbit_core::io::fat::format_fat32(total).into_iter().collect(),
        "mbr-fat16" | "mbr-fat32" | "bare-fat16" => {
            let mut disk = SparseDisk { sectors: BTreeMap::new(), base: 0, size: total as u64 * SECTOR as u64, pos: 0 };
            let (start, ty, fat) = match format {
                "mbr-fat16" => (2048u32, 0x06u8, fatfs::FatType::Fat16),
                "mbr-fat32" => (2048, 0x0C, fatfs::FatType::Fat32),
                _ => (0, 0, fatfs::FatType::Fat16),
            };
            if start > 0 {
                let mut mbr = vec![0u8; SECTOR];
                let e = 0x1BE;
                mbr[e + 4] = ty;
                mbr[e + 8..e + 12].copy_from_slice(&start.to_le_bytes());
                mbr[e + 12..e + 16].copy_from_slice(&(total - start).to_le_bytes());
                mbr[510] = 0x55;
                mbr[511] = 0xAA;
                disk.sectors.insert(0, mbr);
            }
            let mut part = SparseDisk { sectors: disk.sectors, base: start as u64 * 512, size: (total - start) as u64 * 512, pos: 0 };
            fatfs::format_volume(&mut part, fatfs::FormatVolumeOptions::new().fat_type(fat).volume_label(*b"LEAPSTER   ")).expect("format");
            part.sectors
        }
        other => panic!("unknown --card-format {other}"),
    };
    add_files(sectors, files)
}

/// The first sector of the FAT volume: after a partition table if sector 0 has one.
fn volume_start(sectors: &BTreeMap<u32, Vec<u8>>) -> u32 {
    match sectors.get(&0) {
        Some(s) if s[510] == 0x55 && s[511] == 0xAA && s[0] != 0xEB && s[0] != 0xE9 && s[0x1BE + 4] != 0 => {
            u32::from_le_bytes([s[0x1C6], s[0x1C7], s[0x1C8], s[0x1C9]])
        }
        _ => 0,
    }
}

/// Adds (or replaces) files on an existing card image, as a PC would.
fn add_files(sectors: BTreeMap<u32, Vec<u8>>, files: &[(String, Vec<u8>)]) -> BTreeMap<u32, Vec<u8>> {
    let total = ribbit_core::io::sd::CARD_SECTORS;
    let start = volume_start(&sectors);
    let mut part = SparseDisk { sectors, base: start as u64 * 512, size: (total - start) as u64 * SECTOR as u64, pos: 0 };
    {
        let fs = FileSystem::new(&mut part, FsOptions::new()).expect("mount the emulated card");
        let root = fs.root_dir();
        for (path, data) in files {
            let parts: Vec<&str> = path.split('/').filter(|p| !p.is_empty()).collect();
            let mut dir = root.clone();
            for d in &parts[..parts.len() - 1] {
                dir = match dir.open_dir(d) {
                    Ok(x) => x,
                    Err(_) => dir.create_dir(d).expect("create directory"),
                };
            }
            let mut f = dir.create_file(parts[parts.len() - 1]).expect("create file");
            f.truncate().unwrap();
            f.write_all(data).expect("write file");
        }
        drop(root);
        fs.unmount().unwrap();
    }
    part.sectors
}

fn cstr(m: &Machine, a: u32) -> String {
    let mut v = vec![];
    for i in 0..300 {
        match m.bus.peek8(a.wrapping_add(i)) {
            Some(0) | None => break,
            Some(c) => v.push(c),
        }
    }
    String::from_utf8_lossy(&v).into_owned()
}

/// Formats a printf-style call: format in register `fr`, arguments after it.
fn format_log(m: &Machine, fr: usize) -> String {
    let fmt = cstr(m, m.cpu.regs[fr]);
    let (mut out, mut arg, mut it) = (String::new(), fr + 1, fmt.chars().peekable());
    while let Some(c) = it.next() {
        if c != '%' {
            out.push(c);
            continue;
        }
        let mut spec = String::new();
        while let Some(&d) = it.peek() {
            it.next();
            if d.is_ascii_alphabetic() || d == '%' {
                spec.push(d);
                break;
            }
        }
        let v = if arg < 8 { m.cpu.regs[arg] } else { 0 };
        arg += 1;
        match spec.as_str() {
            "s" => out.push_str(&cstr(m, v)),
            "x" | "X" | "p" => out.push_str(&format!("{v:x}")),
            "%" => {
                out.push('%');
                arg -= 1;
            }
            // Doubles take a register pair; the value is not decoded.
            "f" => {
                out.push_str("<float>");
                arg += 1;
            }
            _ => out.push_str(&format!("{}", v as i32)),
        }
    }
    out.trim_end().to_string()
}

const VOICE_HZ: u32 = 8000;

fn write_wav(path: &str, s: &[i16], hz: u32) {
    let mut w = Vec::with_capacity(44 + 2 * s.len());
    let data = 2 * s.len() as u32;
    w.extend_from_slice(b"RIFF");
    w.extend_from_slice(&(36 + data).to_le_bytes());
    w.extend_from_slice(b"WAVEfmt ");
    for v in [16u32, 1 | 1 << 16, hz, 2 * hz, 2 | 16 << 16] {
        w.extend_from_slice(&v.to_le_bytes());
    }
    w.extend_from_slice(b"data");
    w.extend_from_slice(&data.to_le_bytes());
    s.iter().for_each(|v| w.extend_from_slice(&v.to_le_bytes()));
    std::fs::write(path, w).expect("write wav");
}

/// Prints the non-silent stretches (gaps under 50 ms join), in ms from the recording's start.
fn report_sounds(s: &[i16]) {
    let ms = |i: usize| i as f64 * 1000.0 / VOICE_HZ as f64;
    let gap = VOICE_HZ as usize / 20;
    let mut run: Option<(usize, usize)> = None;
    let mut spans = vec![];
    for (i, v) in s.iter().enumerate() {
        if v.unsigned_abs() > 64 {
            run = match run {
                Some((a, b)) if i - b <= gap => Some((a, i)),
                Some(r) => {
                    spans.push(r);
                    Some((i, i))
                }
                None => Some((i, i)),
            };
        }
    }
    spans.extend(run);
    println!("  audio: {:.0} ms recorded, {} sound(s)", ms(s.len()), spans.len());
    for (a, b) in spans {
        println!("    {:8.1} - {:8.1} ms ({:.0} ms)", ms(a), ms(b), ms(b - a));
    }
}

fn shot(m: &Machine, path: &std::path::Path) {
    let mut px = Box::new([0u32; WIDTH * HEIGHT]);
    m.render_frame(&mut px);
    let s = 2;
    let mut rgb = Vec::with_capacity(WIDTH * HEIGHT * 3 * s * s);
    for y in 0..HEIGHT * s {
        for x in 0..WIDTH * s {
            let p = px[(y / s) * WIDTH + x / s];
            rgb.extend([(p >> 16) as u8, (p >> 8) as u8, p as u8]);
        }
    }
    let mut e = png::Encoder::new(std::fs::File::create(path).unwrap(), (WIDTH * s) as u32, (HEIGHT * s) as u32);
    e.set_color(png::ColorType::Rgb);
    e.write_header().unwrap().write_image_data(&rgb).unwrap();
}

struct Session {
    bp: Breakpoints,
    /// USB research: keep the USB stub out, also after console restarts (which rebuild it).
    usb_off: bool,
    logs: Vec<(u32, usize)>,
    traces: Vec<u32>,
    per_ms: u64,
    next_shot: u64,
    shot_every: u64,
    out: std::path::PathBuf,
    restarts: u64,
    last_b008: u32,
    profile_from: Option<u64>,
    samples: BTreeMap<u32, u64>,
    view: Option<View>,
    /// The 8 kHz voice output since the last `audio` command (script).
    audio: Vec<i16>,
    /// The 32 kHz DAC stream (PCM channel 1: Flash sounds, and the voices mixed in) over the same time.
    dac: Vec<i16>,
    /// Recording: drain the voice output often enough that its ring never overflows.
    recording: bool,
}

/// A live window showing the LCD, paced to real time (for watching a run).
struct View {
    window: minifb::Window,
    buf: Vec<u32>,
    wall: std::time::Instant,
    emu_start: u64,
}

impl View {
    fn new() -> Self {
        let opts = minifb::WindowOptions { scale: minifb::Scale::X4, ..Default::default() };
        let window = minifb::Window::new("LeapLoader research: Leapster 2 (Ribbit)", WIDTH, HEIGHT, opts).expect("open window");
        Self { window, buf: vec![0; WIDTH * HEIGHT], wall: std::time::Instant::now(), emu_start: 0 }
    }

    /// Keyboard and mouse to the console: arrows = D-pad, Enter/Z = A, X = B, H = Hint,
    /// Escape = Home, P = Pause; the left mouse button on the screen = the stylus.
    fn input(&self, m: &mut Machine) {
        use minifb::Key;
        use ribbit_input::Button;
        let keys = [(Key::Up, Button::Up), (Key::Down, Button::Down), (Key::Left, Button::Left),
                    (Key::Right, Button::Right), (Key::Enter, Button::A), (Key::Z, Button::A), (Key::X, Button::B),
                    (Key::H, Button::Hint), (Key::Escape, Button::Home), (Key::P, Button::Pause)];
        for b in [Button::Up, Button::Down, Button::Left, Button::Right, Button::A, Button::B, Button::Hint, Button::Home, Button::Pause] {
            let down = keys.iter().any(|(k, kb)| *kb == b && self.window.is_key_down(*k));
            m.buttons.set(b, down);
        }
        if let Some(t) = m.io.touch.as_mut() {
            let pen = self.window.get_mouse_down(minifb::MouseButton::Left);
            t.live = match (pen, self.window.get_mouse_pos(minifb::MouseMode::Discard)) {
                (true, Some((x, y))) => {
                    let raw = |p: f32| (((p.max(0.0) as u32).min(159) * 0x7F0 + 79) / 159).min(0x7F0);
                    Some((raw(x), raw(y)))
                }
                _ => None,
            };
        }
    }

    fn frame(&mut self, m: &Machine, per_ms: u64) {
        let mut px = Box::new([0u32; WIDTH * HEIGHT]);
        m.render_frame(&mut px);
        self.buf.copy_from_slice(&px[..]);
        let _ = self.window.update_with_buffer(&self.buf, WIDTH, HEIGHT);
        // Real-time pacing: wait until the wall clock catches up with emulated time.
        let emu_ms = (m.cpu.cycles - self.emu_start) / per_ms;
        let wall_ms = self.wall.elapsed().as_millis() as u64;
        if emu_ms > wall_ms {
            std::thread::sleep(std::time::Duration::from_millis(emu_ms - wall_ms));
        }
    }
}

impl Session {
    fn advance_ms(&mut self, m: &mut Machine, ms: u64) {
        let end = m.cpu.cycles + ms * self.per_ms;
        self.advance(m, end);
    }

    /// Runs the machine to cycle `end`, printing log calls, traces, restarts
    /// and B008 changes, and taking the periodic screenshots.
    fn advance(&mut self, m: &mut Machine, end: u64) {
        let per_ms = self.per_ms;
        while m.cpu.cycles < end {
            if self.usb_off && m.io.usb.is_some() {
                m.io.usb = None;
            }
            if self.bp.hit(m.cpu.pc) {
                m.run(1, &Breakpoints::default());
            }
            let mut stop = (self.next_shot * per_ms).min(end);
            if self.view.is_some() || self.recording {
                stop = stop.min(m.cpu.cycles + 16 * per_ms);
            }
            if self.usb_off {
                stop = stop.min(m.cpu.cycles + 2 * per_ms);
            }
            let profiling = self.profile_from.is_some_and(|p| m.cpu.cycles >= p * per_ms);
            if profiling {
                stop = stop.min(m.cpu.cycles + 1000);
            } else if let Some(p) = self.profile_from {
                stop = stop.min(p * per_ms);
            }
            if m.cpu.cycles < stop {
                m.run_cycles(stop - m.cpu.cycles, &self.bp);
            }
            if profiling {
                *self.samples.entry(m.cpu.pc).or_default() += 1;
            }
            let out = &mut m.io.voices.output;
            let at = self.audio.len();
            self.audio.resize(at + out.len(), 0);
            out.pop_into(&mut self.audio[at..]);
            let dac = &mut m.io.voices.dac_output;
            let at = self.dac.len();
            self.dac.resize(at + dac.len(), 0);
            dac.pop_into(&mut self.dac[at..]);
            if let Some(v) = self.view.as_mut() {
                v.frame(m, per_ms);
            }
            let now = m.cpu.cycles as f64 / per_ms as f64;
            if m.restarts != self.restarts {
                self.restarts = m.restarts;
                println!("{now:10.1} ms  ** console restarted (restart #{})", self.restarts);
            }
            let b = m.io.leapster2_power.unwrap()[1];
            if b != self.last_b008 {
                println!("{now:10.1} ms  ** B008 {:#x} -> {b:#x}", self.last_b008);
                self.last_b008 = b;
            }
            if let Some(&(_, fr)) = self.logs.iter().find(|l| l.0 == m.cpu.pc) {
                let level = if fr > 0 { format!("[r0={}] ", m.cpu.regs[0]) } else { String::new() };
                println!("{now:10.1} ms  {level}{}", format_log(m, fr));
            } else if self.traces.contains(&m.cpu.pc) {
                let r = &m.cpu.regs;
                let regs: Vec<String> = (0..27).filter(|&i| i <= 8 || i >= 13).map(|i| format!("r{i}={:08x}", r[i])).collect();
                println!("{now:10.1} ms  @{:08x} {} blink={:08x}", m.cpu.pc, regs.join(" "), r[31]);
            }
            if m.cpu.cycles >= self.next_shot * per_ms {
                shot(m, &self.out.join(format!("t{:06}.png", self.next_shot)));
                self.next_shot += self.shot_every;
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut bios, mut cart, mut ms, mut b008, mut logs) = (None, None, 8000u64, 5u32, vec![]);
    let (mut files, mut traces, mut dumps) = (vec![], vec![], vec![]);
    let (mut shot_every, mut out) = (1000u64, std::path::PathBuf::from("."));
    let mut profile_from: Option<u64> = None;
    let mut script: Option<String> = None;
    let mut view = false;
    // --usb-attached: no USB stub, so the BIOS sees a PC attached and drives the controller;
    // every access to it (0x0180_F000-0x0180_F3FF) is listed at the end (USB research).
    let mut usb_attached = false;
    let mut i = 0;
    while i < args.len() {
        let v = args.get(i + 1).cloned().unwrap_or_default();
        match args[i].as_str() {
            "--bios" => bios = Some(v),
            "--cart" => cart = Some(v),
            "--ms" => ms = v.parse().unwrap(),
            "--b008" => b008 = hex(&v),
            "--log" => {
                let (pc, r) = v.split_once(':').unwrap_or((&v, "0"));
                logs.push((hex(pc), r.trim_start_matches('r').parse::<usize>().unwrap()));
            }
            "--trace" => traces.push(hex(&v)),
            "--shot-every" => shot_every = v.parse().unwrap(),
            "--out" => out = v.into(),
            "--profile-from" => profile_from = Some(v.parse().unwrap()),
            "--script" => script = Some(v),
            "--view" => {
                view = true;
                i -= 1;
            }
            "--usb-attached" => {
                usb_attached = true;
                i -= 1;
            }
            "--put" => {
                let (c, l) = v.split_once('=').expect("CARD=LOCAL");
                files.push((c.to_string(), std::fs::read(l).expect("read --put file")));
            }
            "--tree" => {
                // Copy a local folder tree onto the card root (as a PC copy would).
                fn walk(dir: &std::path::Path, rel: &str, out: &mut Vec<(String, Vec<u8>)>) {
                    for e in std::fs::read_dir(dir).expect("read --tree").flatten() {
                        let name = e.file_name().to_string_lossy().into_owned();
                        let r = if rel.is_empty() { name.clone() } else { format!("{rel}/{name}") };
                        if e.path().is_dir() { walk(&e.path(), &r, out) } else { out.push((r, std::fs::read(e.path()).unwrap())) }
                    }
                }
                walk(std::path::Path::new(&v), "", &mut files);
            }
            "--text" => {
                let (c, t) = v.split_once('=').expect("CARD=TEXT");
                files.push((c.to_string(), t.as_bytes().to_vec()));
            }
            "--card-format" => CARD_FORMAT.set(v).unwrap(),
            "--dump" => {
                let p: Vec<&str> = v.splitn(3, ':').collect();
                dumps.push((hex(p[0]), hex(p[1]), p[2].to_string()));
            }
            other => panic!("unknown option {other}"),
        }
        i += 2;
    }
    if logs.is_empty() {
        logs = vec![(0x4004_2F98, 0)];
    }
    std::fs::create_dir_all(&out).unwrap();
    let image = ribbit_core::read_image(bios.expect("--bios")).unwrap();
    let fw = ribbit_memory::Firmware::from_bytes_any_model(image).unwrap();
    let cart = cart.map(|c| ribbit_memory::Cartridge::from_bytes(ribbit_core::read_image(c).unwrap()).unwrap());
    // As Ribbit's scenes tool: MAME's measured straps with bit 14 set (skip
    // calibration; a Leapster 2 cannot calibrate at boot) and the factory
    // touch calibration in the SPI flash.
    let mut m = Machine::with_straps(fw, cart, 0x63FF_FFFF);
    m.ensure_touch_calibration();
    m.enable_experimental_mame_touch(Default::default());
    m.record_trace_tail = false;
    if usb_attached {
        m.io.usb = None;
    }
    m.io.leapster2_power.as_mut().expect("not a Leapster 2 BIOS")[1] = b008;
    let card = m.io.sd.as_mut().and_then(|s| s.card.as_mut()).expect("this BIOS has no SD card (CIP3 uses NAND)");
    card.sectors = build_card(&files);
    for (p, d) in &files {
        println!("card: {p} ({} bytes)", d.len());
    }

    let mut bp = Breakpoints::default();
    for &(pc, _) in &logs {
        bp.add(pc);
    }
    for &t in &traces {
        bp.add(t);
    }
    let per_ms = m.clock.cpu_hz / 1000;
    let mut ses = Session { bp, usb_off: usb_attached, logs, traces, per_ms, next_shot: shot_every, shot_every, out: out.clone(), restarts: m.restarts, last_b008: b008, profile_from, samples: BTreeMap::new(), view: None, audio: Vec::new(), dac: Vec::new(), recording: false };
    if view {
        let mut v = View::new();
        v.emu_start = m.cpu.cycles;
        ses.view = Some(v);
    }
    match script {
        None => ses.advance(&mut m, ms * per_ms),
        Some(path) => {
            for (n, line) in std::fs::read_to_string(&path).expect("read --script").lines().enumerate() {
                let line = line.split('#').next().unwrap().trim();
                let w: Vec<&str> = line.split_whitespace().collect();
                let num = |i: usize, d: u64| w.get(i).map_or(d, |x| x.parse().expect("number"));
                match w.first().copied() {
                    None => {}
                    Some("run") => ses.advance_ms(&mut m, num(1, 0)),
                    Some("tap") => {
                        // LCD pixel (0-159) to the touch panel's raw 11-bit scale, as Ribbit's scenes tool.
                        let raw = |p: u64| ((p as u32 * 0x7F0 + 79) / 159).min(0x7F0);
                        m.io.touch.as_mut().unwrap().live = Some((raw(num(1, 0)), raw(num(2, 0))));
                        ses.advance_ms(&mut m, num(3, 200));
                        m.io.touch.as_mut().unwrap().live = None;
                        ses.advance_ms(&mut m, 300);
                    }
                    Some("btn") => {
                        let b = ribbit_input::Button::from_name(w[1]).expect("button name");
                        m.buttons.set(b, true);
                        ses.advance_ms(&mut m, num(2, 200));
                        m.buttons.set(b, false);
                        ses.advance_ms(&mut m, 300);
                    }
                    // Hold / release a button (for chords); `run` lets time pass meanwhile.
                    Some("hold") | Some("release") => {
                        let b = ribbit_input::Button::from_name(w[1]).expect("button name");
                        m.buttons.set(b, w[0] == "hold");
                    }
                    Some("shot") => shot(&m, &out.join(format!("{}.png", w[1]))),
                    // `usb-attach`: remove the USB stub now (e.g. after `load`), as --usb-attached.
                    Some("usb-attach") => {
                        m.io.usb = None;
                        ses.usb_off = true;
                    }
                    Some("say") => {
                        let text = line[3..].trim();
                        println!("--- {text}");
                        if let Some(v) = ses.view.as_mut() {
                            v.window.set_title(&format!("Leapster 2 (Ribbit) - {text}"));
                        }
                    }
                    // Interactive: run in real time with keyboard/mouse input until the window closes.
                    Some("play") => {
                        while ses.view.as_ref().is_some_and(|v| v.window.is_open()) {
                            ses.view.as_ref().unwrap().input(&mut m);
                            ses.advance_ms(&mut m, 16);
                        }
                    }
                    Some("wait") => {
                        // Hold the window open (real time) at the end of a script.
                        if let Some(v) = ses.view.as_mut() {
                            while v.window.is_open() {
                                let _ = v.window.update_with_buffer(&v.buf, WIDTH, HEIGHT);
                                std::thread::sleep(std::time::Duration::from_millis(50));
                            }
                        }
                    }
                    // `audio`: start recording; `audio FILE.wav`: write what played since, and list the sounds in it.
                    // The 32 kHz DAC stream, when PCM channel 1 ran, goes to FILE-32k.wav.
                    Some("audio") => {
                        if let Some(path) = w.get(1) {
                            write_wav(path, &ses.audio, VOICE_HZ);
                            report_sounds(&ses.audio);
                            if !ses.dac.is_empty() {
                                let p32 = format!("{}-32k.wav", path.trim_end_matches(".wav"));
                                write_wav(&p32, &ses.dac, 32_000);
                                println!("  audio: {:.0} ms of 32 kHz DAC output -> {p32}", ses.dac.len() as f64 / 32.0);
                            }
                        }
                        ses.audio.clear();
                        ses.dac.clear();
                        ses.recording = w.get(1).is_none();
                    }
                    // `voices`: the voice engine's start/end addresses, volumes and which voices play.
                    Some("voices") => {
                        let v = &m.io.voices;
                        for k in 0..8 {
                            println!("  voice {k}: start {:#010x} end {:#010x} volume {:#06x} triggered {} paused {}",
                                     v.start[k], v.end[k], v.volume[k], v.triggered[k], v.paused[k]);
                        }
                    }
                    // `mem ADDR [WORDS]`: dump memory words; ADDR may be `gp`, or `[gp+4]` style
                    // chains written as `gp+4@+0x88@` (each `@` loads the word at the address so far).
                    Some("mem") => {
                        let peek32 = |a: u32| (0..4).fold(0u32, |v, k| v | (m.bus.peek8(a + k).unwrap_or(0) as u32) << (8 * k));
                        let mut a = 0u32;
                        for part in w[1].split_inclusive(['+', '@']) {
                            let (tok, op) = part.split_at(part.len() - part.ends_with(['+', '@']) as usize);
                            let tok = tok.trim_start_matches('+');
                            if !tok.is_empty() {
                                a = a.wrapping_add(if tok == "gp" { m.cpu.regs[26] } else { hex(tok) });
                            }
                            if op == "@" {
                                a = peek32(a);
                            }
                        }
                        let n = num(2, 8) as u32;
                        println!("  mem {} = {a:08x} (gp {:08x}, cache misses i/d/wb {:?}, cycles {}):", w[1], m.cpu.regs[26],
                                 m.io.mem.misses, m.cpu.cycles);
                        for r in (0..n).step_by(8) {
                            let words: Vec<String> = (r..(r + 8).min(n)).map(|k| format!("{:08x}", peek32(a + 4 * k))).collect();
                            println!("    {:08x}: {}", a + 4 * r, words.join(" "));
                        }
                    }
                    Some("save") => std::fs::write(w[1], m.save_state()).expect("write state"),
                    Some("load") => {
                        m.load_state(&std::fs::read(w[1]).expect("read state")).expect("load state");
                        ses.restarts = m.restarts;
                        ses.next_shot = (m.cpu.cycles / per_ms / ses.shot_every + 1) * ses.shot_every;
                        if let Some(v) = ses.view.as_mut() {
                            v.emu_start = m.cpu.cycles;
                            v.wall = std::time::Instant::now();
                        }
                    }
                    // Replace the card's contents with the --put/--text files (after a load).
                    Some("card") => {
                        let card = m.io.sd.as_mut().unwrap().card.as_mut().unwrap();
                        card.sectors = add_files(std::mem::take(&mut card.sectors), &files);
                    }
                    // Save the card in Ribbit's own format (sdcard-<bios crc>.img, io/sparse.rs).
                    Some("export") => {
                        let card = m.io.sd.as_ref().unwrap().card.as_ref().unwrap();
                        std::fs::write(w[1], ribbit_core::io::sparse::encode(&card.sectors, SECTOR)).expect("write export");
                        println!("  exported {} sectors to {}", card.sectors.len(), w[1]);
                    }
                    // Print a file from the card (as a PC would read it).
                    Some("cat") => {
                        let card = m.io.sd.as_ref().unwrap().card.as_ref().unwrap();
                        let start = volume_start(&card.sectors);
                        let total = ribbit_core::io::sd::CARD_SECTORS as u64 * SECTOR as u64;
                        let mut part = SparseDisk { sectors: card.sectors.clone(), base: start as u64 * 512, size: total - start as u64 * 512, pos: 0 };
                        let fs = FileSystem::new(&mut part, FsOptions::new()).expect("mount");
                        let mut data = Vec::new();
                        match fs.root_dir().open_file(w[1]) {
                            Ok(mut f) => {
                                f.read_to_end(&mut data).unwrap();
                                println!("  cat {} ({} bytes): {:?}", w[1], data.len(), String::from_utf8_lossy(&data));
                            }
                            Err(e) => println!("  cat {}: {e}", w[1]),
                        }
                    }
                    // List the card's files (as a PC would see them).
                    Some("ls") => {
                        let card = m.io.sd.as_ref().unwrap().card.as_ref().unwrap();
                        let start = volume_start(&card.sectors);
                        let total = ribbit_core::io::sd::CARD_SECTORS as u64 * SECTOR as u64;
                        let mut part = SparseDisk { sectors: card.sectors.clone(), base: start as u64 * 512, size: total - start as u64 * 512, pos: 0 };
                        let fs = FileSystem::new(&mut part, FsOptions::new()).expect("mount");
                        fn walk<T: fatfs::ReadWriteSeek>(d: fatfs::Dir<T>, path: String) {
                            for e in d.iter().flatten() {
                                let n = e.file_name();
                                if n == "." || n == ".." { continue; }
                                println!("  card: {path}/{n}{}", if e.is_dir() { "/".into() } else { format!(" ({} bytes)", e.len()) });
                                if e.is_dir() { walk(e.to_dir(), format!("{path}/{n}")); }
                            }
                        }
                        walk(fs.root_dir(), String::new());
                    }
                    Some("b008") => m.io.leapster2_power.as_mut().unwrap()[1] = hex(w[1]),
                    // Add a trace point from here on.
                    Some("trace") => {
                        let pc = hex(w[1]);
                        ses.bp.add(pc);
                        ses.traces.push(pc);
                    }
                    // Power cycle: Ribbit keeps the SPI flash, NAND and SD card (Machine::reset).
                    Some("power") => {
                        m.reset();
                        m.enable_experimental_mame_touch(Default::default());
                        ses.restarts = m.restarts;
                        ses.last_b008 = m.io.leapster2_power.unwrap()[1];
                        ses.next_shot = (m.cpu.cycles / per_ms / ses.shot_every + 1) * ses.shot_every;
                        if let Some(v) = ses.view.as_mut() {
                            v.emu_start = m.cpu.cycles;
                            v.wall = std::time::Instant::now();
                        }
                    }
                    Some(other) => panic!("script line {}: unknown command {other}", n + 1),
                }
            }
        }
    }
    let samples = std::mem::take(&mut ses.samples);
    if !samples.is_empty() {
        let total: u64 = samples.values().sum();
        let mut v: Vec<_> = samples.into_iter().collect();
        v.sort_by(|a, b| b.1.cmp(&a.1));
        println!("hottest PCs ({total} samples):");
        let top = std::env::var("SDBOOT_PROFILE_TOP").ok().and_then(|s| s.parse().ok()).unwrap_or(25);
        for (pc, n) in v.into_iter().take(top) {
            println!("  {pc:08x}  {:5.1}%", 100.0 * n as f64 / total as f64);
        }
    }
    // Unmapped accesses (Ribbit reads them as 0 and records them): grouped by
    // 1 MiB region, with the earliest occurrence.
    let mut regions: BTreeMap<u32, (u64, u64, u32, u32, String)> = BTreeMap::new();
    for ((addr, width, kind), st) in m.bus.unmapped_summary() {
        let e = regions.entry(addr & 0xFFF0_0000).or_insert((0, u64::MAX, 0, 0, String::new()));
        e.0 += st.count;
        if st.first_cycle < e.1 {
            *e = (e.0, st.first_cycle, st.first_pc, *addr, format!("{kind:?}/{width}"));
        }
    }
    if ses.usb_off {
        println!("USB controller accesses (address, width, kind: count, first ms, first pc):");
        for ((addr, width, kind), st) in m.bus.unmapped_summary() {
            if (0x0180_F000..0x0180_F400).contains(addr) {
                println!("  {addr:08x} {width} {kind:?}: {:6}  {:9.1} ms  pc {:08x}", st.count,
                         st.first_cycle as f64 / per_ms as f64, st.first_pc);
            }
        }
        println!("USB controller accesses in order (first {} unmapped accesses kept):", m.bus.unmapped_accesses().len());
        for a in m.bus.unmapped_accesses() {
            if (0x0180_F000..0x0180_F400).contains(&a.addr) {
                println!("  {:08x} {} {:?} {:#x}", a.addr, a.width, a.kind, a.value);
            }
        }
    }
    if !regions.is_empty() {
        println!("unmapped accesses by 1 MiB region (count, first at):");
        for (r, (n, cyc, pc, addr, k)) in regions {
            println!("  {r:08x}  {n:8}  first {:9.1} ms  addr {addr:08x} {k} pc {pc:08x}", cyc as f64 / per_ms as f64);
        }
    }
    for (a, len, f) in dumps {
        let bytes: Vec<u8> = (0..len).map(|i| m.bus.peek8(a + i).unwrap_or(0)).collect();
        std::fs::write(&f, bytes).unwrap();
        println!("dumped {len:#x} bytes at {a:08x} to {f}");
    }
    let ee = &m.io.eeprom;
    println!(
        "eeprom: system reads {} writes {}; commands to other devices {} (last {:?}); cartridge chip {}",
        ee.reads, ee.writes, ee.other_device_commands, ee.last_other_command.map(|(c, v)| format!("{c:#010x}/{v}")),
        if ee.cart.is_some() { "present" } else { "absent" }
    );
    println!("final pc {:08x}, B008 {:#x}, restarts {}", m.cpu.pc, m.io.leapster2_power.unwrap()[1], m.restarts);
    if let Some(sd) = m.io.sd.as_ref() {
        let hc = sd.card.as_ref().is_some_and(|c| c.hc);
        let rw: Vec<_> = sd.log.iter().filter(|l| l.0 == 17 || l.0 == 24).collect();
        let odd = rw.iter().filter(|l| l.1 % 512 != 0).count();
        println!("sd: hc {hc}, {} reads/writes, {odd} with an argument not a multiple of 512", rw.len());
    }
}
