// SPDX-License-Identifier: GPL-3.0-or-later
//! The Leapster 2 over USB (docs/usb-research.md): with BIOS 0.6 the console
//! is a USB mass-storage device (VID 0x0F63, Bulk-Only, SCSI) with two
//! removable disks, one per LUN, whose INQUIRY data says "LeapFrog" /
//! "Leapster 2-RAM" (copies of the internal flash) and "LeapFrog" /
//! "Leapster 2-SD" (the SD card). LeapFrog's own commands (10-byte vendor
//! CDBs): C2 mount (the disk reads nothing before it), C1 lock, C6 eject.
//!
//! Mount/eject method ported from LFTools (https://github.com/lfhacks/LFTools),
//! Copyright 2026 Ian Mathews (awes145), GPL-3.0: find the disk whose SCSI
//! product contains "2-SD", send it `C2 00 00 00 00 00 00 00 00 00` (no data)
//! to mount and `C6 00 ...` to eject, and keep track of whether it is mounted
//! so it isn't mounted twice or ejected when it isn't.
//!
//! What LeapLoader does differently, and why:
//! * Native SCSI pass-through (Windows IOCTL_SCSI_PASS_THROUGH_DIRECT, Linux
//!   SG_IO) instead of running sg3_utils' sg_scan and sg_raw: nothing extra
//!   to install.
//! * The match also needs the vendor "LeapFrog" (LFTools: the product
//!   contains "2-SD"), so no other maker's disk can match by accident; and
//!   before any LeapFrog command the disk is asked again (INQUIRY) and must
//!   answer the same way.
//! * C2's result is checked: its SCSI status and sense data, then TEST UNIT
//!   READY until the card is ready (LFTools prints "Mounted!" whatever the
//!   console answers), then the drive the system mounts is waited for.
//! * Before C6 the drive is flushed and dismounted (Windows) or synced and
//!   unmounted (Linux), so nothing waiting to be written is lost.
//! * "Mounted" is what the system shows (the disk has a drive letter or
//!   mount point), not a marker file: it can't go stale if the console is
//!   unplugged or another tool mounts it.
//!
//! The steps, each asked for first in the window:
//! 1. find the console's disks by the identity the system read from them
//!    (reading only; every other disk is left alone);
//! 2. open the SD card: send C2 to it (only to a disk whose INQUIRY says
//!    LeapFrog / Leapster 2-SD), wait until it is ready and the system has
//!    mounted it as a drive;
//! 3. build the card into that drive (files through the filesystem, as into
//!    any folder; app.rs), then flush and close the drive and send C6.
//!
//! Commands need admin rights (Windows) or root (Linux): they run in a
//! helper, this same program started with `--usb-helper` and elevated for
//! that one action. Every step is written to the USB log (`note`), which
//! testers save and send back. UNTESTED on a real console: everything that
//! touches a device; tested here with a fake console (the tests below).

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

// ---------------------------------------------------------------- the log

static LOG: Mutex<Vec<String>> = Mutex::new(Vec::new());
static START: std::sync::OnceLock<Instant> = std::sync::OnceLock::new();

/// Adds a line to the USB log, with the seconds since the app started.
pub fn note(text: impl AsRef<str>) {
    let t = START.get_or_init(Instant::now).elapsed().as_secs_f64();
    let line = format!("[{t:8.3} s] {}", text.as_ref());
    if let Ok(mut log) = LOG.lock() {
        log.push(line);
    }
}

/// The USB log so far, with what it was made on at the top.
pub fn log_text() -> String {
    let head = format!(
        "LeapLoader {} USB log ({} {})\n",
        env!("CARGO_PKG_VERSION"),
        std::env::consts::OS,
        std::env::consts::ARCH
    );
    head + &LOG.lock().map(|l| l.join("\n")).unwrap_or_default() + "\n"
}

/// Writes the USB log to `usb-log.txt` in `dir`; its path.
pub fn save_log(dir: &Path) -> std::io::Result<PathBuf> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join("usb-log.txt");
    std::fs::write(&path, log_text())?;
    Ok(path)
}

// ---------------------------------------------------------------- disks

/// Which of the console's disks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// The SD card ("Leapster 2-SD").
    Sd,
    /// The internal storage ("Leapster 2-RAM": copies of the flash).
    Internal,
}

impl Kind {
    pub fn label(self) -> &'static str {
        match self {
            Kind::Sd => "SD card",
            Kind::Internal => "internal storage",
        }
    }
}

/// A disk as the system reports it (its INQUIRY identity).
#[derive(Debug, Clone, PartialEq)]
pub struct Disk {
    /// Where the system has it: "\\.\PhysicalDrive3", "/dev/sdb".
    pub device: String,
    pub vendor: String,
    pub product: String,
    pub revision: String,
    /// Where its files are, if the system has mounted it ("E:\", "/media/x").
    pub mounted: Option<PathBuf>,
}

impl Disk {
    /// Which Leapster 2 disk this is, or None for any other disk.
    pub fn leapster(&self) -> Option<Kind> {
        classify(&self.vendor, &self.product)
    }
}

/// The console's disks by their INQUIRY vendor and product (8 and 16
/// characters, space padded; BIOS 0.6: "LeapFrog" with "Leapster 2-SD" or
/// "Leapster 2-RAM"): LFTools' rule (the product contains "2-SD"), and the
/// vendor must be LeapFrog. Anything else is not ours.
pub fn classify(vendor: &str, product: &str) -> Option<Kind> {
    if vendor.trim() != "LeapFrog" {
        return None;
    }
    if product.contains("2-SD") {
        Some(Kind::Sd)
    } else if product.contains("2-RAM") {
        Some(Kind::Internal)
    } else {
        None
    }
}

/// Every disk the system knows, with its identity (no command is sent to
/// any of them; the system read these when the disk arrived).
pub fn disks() -> Vec<Disk> {
    platform::disks()
}

/// What a look for the console found: its disks, and the other disks
/// (left alone).
#[derive(Debug, Clone, Default)]
pub struct Scan {
    pub found: Vec<(Kind, Disk)>,
    pub others: usize,
}

/// Looks for the console, writing every disk seen to the log.
pub fn scan() -> Scan {
    let t = Instant::now();
    let all = disks();
    note(format!("scan: {} disks ({} ms)", all.len(), t.elapsed().as_millis()));
    let mut s = Scan::default();
    for d in all {
        let at = d.mounted.as_ref().map_or_else(|| "no volume".into(), |m| format!("volume {}", m.display()));
        match d.leapster() {
            Some(k) => {
                note(format!(
                    "  {}: {:?} {:?} {:?}, {at}: Leapster 2 {}",
                    d.device,
                    d.vendor,
                    d.product,
                    d.revision,
                    k.label()
                ));
                s.found.push((k, d));
            }
            None => {
                let why =
                    if d.vendor.trim() != "LeapFrog" { "vendor is not LeapFrog" } else { "not a Leapster 2 disk" };
                note(format!(
                    "  {}: {:?} {:?} {:?}, {at}: left alone ({why})",
                    d.device, d.vendor, d.product, d.revision
                ));
                s.others += 1;
            }
        }
    }
    s
}

// ---------------------------------------------------------------- SCSI

/// A command's outcome: the SCSI status (0 good, 2 check condition), the
/// sense data the device gave, and the bytes it sent back.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Reply {
    pub status: u8,
    pub sense: Vec<u8>,
    pub read: usize,
}

/// A SCSI device commands can be sent to: the console's disk, or a fake
/// one in the tests.
pub trait Scsi {
    /// Sends `cdb`; with `data`, reads up to its length back (data in).
    fn command(&mut self, cdb: &[u8], data: Option<&mut [u8]>) -> std::io::Result<Reply>;
}

/// Why something over USB didn't work, for the user (and the log).
#[derive(Debug, Clone, PartialEq)]
pub enum UsbError {
    /// The disk's INQUIRY doesn't say LeapFrog / Leapster 2 (what it says).
    NotLeapster(String),
    /// No admin rights (Windows) or root (Linux) for the command.
    NeedsAdmin(String),
    /// The console answered a command with an error.
    Refused {
        what: &'static str,
        status: u8,
        sense: Vec<u8>,
    },
    /// The SD card didn't become ready after "mount".
    NotReady(Vec<u8>),
    /// No drive appeared for the SD card within this many seconds.
    NoVolume(u64),
    /// Not on this system (macOS: not done yet).
    #[cfg_attr(any(windows, target_os = "linux"), allow(dead_code))]
    Unsupported,
    Io(String),
}

impl std::fmt::Display for UsbError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            UsbError::NotLeapster(what) => {
                write!(f, "That disk isn't a Leapster 2's ({what}); nothing was sent to it.")
            }
            UsbError::NeedsAdmin(why) => write!(f, "This step needs admin rights: {why}"),
            UsbError::Refused { what, status, sense } => {
                write!(f, "The Leapster 2 refused \"{what}\" (SCSI status {status}{}).", sense_text(sense))
            }
            UsbError::NotReady(sense) => write!(
                f,
                "The Leapster 2's SD card didn't become ready after \"mount\"{}. Is an SD card in the console?",
                sense_text(sense)
            ),
            UsbError::NoVolume(s) => write!(
                f,
                "The SD card was opened, but no drive appeared for it within {s} s. Look in your file manager; if it \
                 is there, look for the Leapster 2 again."
            ),
            UsbError::Unsupported => write!(f, "Sending files to a Leapster 2 over USB isn't done on this system yet."),
            UsbError::Io(e) => write!(f, "{e}"),
        }
    }
}

/// ", sense key 5 (illegal request), ASC 20h ASCQ 00h" for fixed-format
/// sense data; empty without any.
pub fn sense_text(sense: &[u8]) -> String {
    if sense.len() < 14 || sense[0] & 0x7E != 0x70 {
        return if sense.is_empty() { String::new() } else { format!(", sense {}", hex(sense)) };
    }
    let key = sense[2] & 0x0F;
    let name = [
        "no sense",
        "recovered error",
        "not ready",
        "medium error",
        "hardware error",
        "illegal request",
        "unit attention",
        "data protect",
        "blank check",
        "vendor specific",
        "copy aborted",
        "aborted command",
        "reserved",
        "volume overflow",
        "miscompare",
        "reserved",
    ][key as usize];
    format!(", sense key {key} ({name}), ASC {:02X}h ASCQ {:02X}h", sense[12], sense[13])
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02X}")).collect::<Vec<_>>().join(" ")
}

/// Sends `cdb`, writing it and its outcome to the log.
fn send(dev: &mut dyn Scsi, what: &str, cdb: &[u8], data: Option<&mut [u8]>) -> Result<Reply, UsbError> {
    let t = Instant::now();
    let r = dev.command(cdb, data).map_err(|e| {
        note(format!("  {what} [{}]: failed to send: {e}", hex(cdb)));
        UsbError::Io(format!("Couldn't send \"{what}\" to the Leapster 2: {e}"))
    })?;
    note(format!(
        "  {what} [{}]: status {}{}, {} bytes back ({} ms)",
        hex(cdb),
        r.status,
        sense_text(&r.sense),
        r.read,
        t.elapsed().as_millis()
    ));
    Ok(r)
}

/// INQUIRY: vendor (bytes 8-15), product (16-31), revision (32-35).
pub fn inquiry(dev: &mut dyn Scsi) -> Result<(String, String, String), UsbError> {
    let mut buf = [0u8; 36];
    let r = send(dev, "INQUIRY", &[0x12, 0, 0, 0, 36, 0], Some(&mut buf))?;
    if r.status != 0 || r.read < 36 {
        return Err(UsbError::Refused { what: "INQUIRY", status: r.status, sense: r.sense });
    }
    let text = |r: std::ops::Range<usize>| String::from_utf8_lossy(&buf[r]).into_owned();
    Ok((text(8..16), text(16..32), text(32..36)))
}

/// Checks the device is the console's `want` disk by asking it (INQUIRY):
/// no other command goes to a device that doesn't answer this way.
fn check_identity(dev: &mut dyn Scsi, want: &[Kind]) -> Result<Kind, UsbError> {
    let (v, p, r) = inquiry(dev)?;
    match classify(&v, &p) {
        Some(k) if want.contains(&k) => Ok(k),
        _ => Err(UsbError::NotLeapster(format!("{:?} {:?} {:?}", v.trim(), p.trim(), r.trim()))),
    }
}

/// LeapFrog's "mount" (C2): the disk is readable after it.
pub const MOUNT: [u8; 10] = [0xC2, 0, 0, 0, 0, 0, 0, 0, 0, 0];
/// LeapFrog's "eject" (C6): the console's "safe detach".
pub const EJECT: [u8; 10] = [0xC6, 0, 0, 0, 0, 0, 0, 0, 0, 0];
const TEST_UNIT_READY: [u8; 6] = [0; 6];

/// Step 2 on the device: checks it is the console's SD card, sends "mount"
/// (C2) and waits (TEST UNIT READY every `poll`, up to `tries` times) until
/// the card is ready.
pub fn mount_sd(dev: &mut dyn Scsi, poll: Duration, tries: u32) -> Result<(), UsbError> {
    check_identity(dev, &[Kind::Sd])?;
    let r = send(dev, "mount (C2)", &MOUNT, None)?;
    if r.status != 0 {
        return Err(UsbError::Refused { what: "mount (C2)", status: r.status, sense: r.sense });
    }
    let mut last = Vec::new();
    for i in 0..tries {
        let r = send(dev, "TEST UNIT READY", &TEST_UNIT_READY, None)?;
        if r.status == 0 {
            note(format!("  ready after {} checks", i + 1));
            return Ok(());
        }
        last = r.sense;
        std::thread::sleep(poll);
    }
    Err(UsbError::NotReady(last))
}

/// Step 3's end on the device: checks it is one of the console's disks and
/// sends "eject" (C6).
pub fn eject(dev: &mut dyn Scsi) -> Result<(), UsbError> {
    check_identity(dev, &[Kind::Sd, Kind::Internal])?;
    let r = send(dev, "eject (C6)", &EJECT, None)?;
    if r.status != 0 {
        return Err(UsbError::Refused { what: "eject (C6)", status: r.status, sense: r.sense });
    }
    Ok(())
}

// ---------------------------------------------------------------- the helper

/// The command-line switch that runs the helper.
pub const HELPER_ARG: &str = "--usb-helper";

/// Exit codes of the helper, for the error it hit.
fn exit_code(e: &UsbError) -> i32 {
    match e {
        UsbError::NotLeapster(_) => 2,
        UsbError::NeedsAdmin(_) => 3,
        UsbError::Refused { .. } => 4,
        UsbError::NotReady(_) => 5,
        UsbError::NoVolume(_) => 6,
        UsbError::Unsupported => 7,
        UsbError::Io(_) => 8,
    }
}

/// The helper: `--usb-helper mount|eject DEVICE LOGFILE [VOLUME]`, run with
/// admin rights. Writes its log lines to LOGFILE, the error's message last
/// ("ERROR ..."), and exits with 0 or `exit_code`.
pub fn helper_main(args: &[std::ffi::OsString]) -> i32 {
    let arg = |i: usize| args.get(i).map(|a| a.to_string_lossy().into_owned());
    let (Some(op), Some(device), Some(log)) = (arg(0), arg(1), arg(2)) else {
        return 9;
    };
    let volume = arg(3).map(PathBuf::from);
    note(format!(
        "helper: {op} {device}{}",
        volume.as_ref().map_or_else(String::new, |v| format!(" ({})", v.display()))
    ));
    let result = run_op(&op, &device, volume.as_deref());
    if let Err(e) = &result {
        note(format!("ERROR {e}"));
    }
    let lines = LOG.lock().map(|l| l.join("\n")).unwrap_or_default();
    let _ = std::fs::write(&log, lines + "\n");
    result.map_or_else(|e| exit_code(&e), |()| 0)
}

/// What the helper does, with the rights it has.
fn run_op(op: &str, device: &str, volume: Option<&Path>) -> Result<(), UsbError> {
    let mut dev = platform::open(device)?;
    match op {
        "mount" => mount_sd(dev.as_mut(), Duration::from_millis(500), 20),
        "eject" => {
            // Everything written reaches the card, the drive closes, then C6.
            let _closed = match volume {
                Some(v) => Some(platform::close_volume(v)?),
                None => None,
            };
            eject(dev.as_mut())
        }
        _ => Err(UsbError::Io(format!("unknown helper step {op}"))),
    }
}

/// Runs a step (`mount` or `eject`) on `device` with admin rights: in this
/// process when it has them, else in the helper, which asks for them
/// (Windows' admin prompt, Linux's pkexec). `logdir` holds the helper's log.
pub fn run_elevated(op: &str, device: &str, volume: Option<&Path>, logdir: &Path) -> Result<(), UsbError> {
    if platform::is_admin() {
        note(format!("{op}: running here (already admin)"));
        return run_op(op, device, volume);
    }
    let _ = std::fs::create_dir_all(logdir);
    let log = logdir.join(format!("usb-helper-{}.txt", std::process::id()));
    let _ = std::fs::remove_file(&log);
    let exe = std::env::current_exe().map_err(|e| UsbError::Io(format!("can't find this program: {e}")))?;
    let mut args: Vec<String> = vec![HELPER_ARG.into(), op.into(), device.into(), log.display().to_string()];
    if let Some(v) = volume {
        args.push(v.display().to_string());
    }
    note(format!("{op}: starting the helper with admin rights"));
    let t = Instant::now();
    let code = platform::run_as_admin(&exe, &args)?;
    // The helper's own log lines, then its outcome.
    let text = std::fs::read_to_string(&log).unwrap_or_default();
    let _ = std::fs::remove_file(&log);
    let mut error = None;
    for line in text.lines() {
        note(format!("  helper {line}"));
        if let Some((_, e)) = line.split_once("ERROR ") {
            error = Some(e.to_string());
        }
    }
    note(format!("{op}: helper exited with {code} after {} ms", t.elapsed().as_millis()));
    match (code, error) {
        (0, _) => Ok(()),
        (3, e) => Err(UsbError::NeedsAdmin(e.unwrap_or_else(|| "the helper wasn't allowed to open the disk".into()))),
        (_, Some(e)) => Err(UsbError::Io(e)),
        (c, None) => Err(UsbError::Io(format!("the helper stopped with code {c} and said nothing"))),
    }
}

/// Step 2's end: waits until the system has mounted `device` as a drive
/// (it notices the card is ready on its own), up to `secs` seconds.
pub fn wait_for_volume(device: &str, secs: u64) -> Result<PathBuf, UsbError> {
    let t = Instant::now();
    while t.elapsed() < Duration::from_secs(secs) {
        if let Some(at) = disks().into_iter().find(|d| d.device == device).and_then(|d| d.mounted) {
            note(format!("volume {} appeared after {} ms", at.display(), t.elapsed().as_millis()));
            return Ok(at);
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    note(format!("no volume for {device} after {secs} s"));
    Err(UsbError::NoVolume(secs))
}

/// Free space on the drive at `path`, if the system says.
pub fn free_space(path: &Path) -> Option<u64> {
    platform::free_space(path)
}

// ---------------------------------------------------------------- Windows

#[cfg(windows)]
mod platform {
    use super::{Disk, Reply, Scsi, UsbError, note};
    use std::path::{Path, PathBuf};
    use windows_sys::Win32::Foundation::{
        CloseHandle, ERROR_ACCESS_DENIED, ERROR_CANCELLED, GENERIC_READ, GENERIC_WRITE, GetLastError, HANDLE,
        INVALID_HANDLE_VALUE,
    };
    use windows_sys::Win32::Storage::FileSystem::{
        CreateFileW, FILE_SHARE_READ, FILE_SHARE_WRITE, FlushFileBuffers, GetDiskFreeSpaceExW, OPEN_EXISTING,
    };
    use windows_sys::Win32::Storage::IscsiDisc::{
        IOCTL_SCSI_PASS_THROUGH_DIRECT, SCSI_IOCTL_DATA_IN, SCSI_IOCTL_DATA_UNSPECIFIED, SCSI_PASS_THROUGH_DIRECT,
    };
    use windows_sys::Win32::System::IO::DeviceIoControl;
    use windows_sys::Win32::System::Ioctl::{
        FSCTL_DISMOUNT_VOLUME, FSCTL_LOCK_VOLUME, IOCTL_STORAGE_GET_DEVICE_NUMBER, IOCTL_STORAGE_QUERY_PROPERTY,
        PropertyStandardQuery, STORAGE_DEVICE_DESCRIPTOR, STORAGE_DEVICE_NUMBER, STORAGE_PROPERTY_QUERY,
        StorageDeviceProperty,
    };

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain([0]).collect()
    }

    /// A handle, closed when dropped.
    pub struct Handle(HANDLE);
    impl Drop for Handle {
        fn drop(&mut self) {
            // SAFETY: the handle came from CreateFileW and is closed once.
            unsafe { CloseHandle(self.0) };
        }
    }

    /// Opens `path` with `access` (0: queries only, no admin rights needed
    /// and nothing can be changed through the handle).
    fn open_with(path: &str, access: u32) -> Result<Handle, u32> {
        let name = wide(path);
        // SAFETY: a plain Win32 call with a NUL-terminated name.
        let h = unsafe {
            CreateFileW(
                name.as_ptr(),
                access,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                std::ptr::null(),
                OPEN_EXISTING,
                0,
                std::ptr::null_mut(),
            )
        };
        if h == INVALID_HANDLE_VALUE || h.is_null() {
            // SAFETY: no arguments.
            Err(unsafe { GetLastError() })
        } else {
            Ok(Handle(h))
        }
    }

    fn ioctl(h: &Handle, code: u32, input: &[u8], output: &mut [u8]) -> Result<u32, u32> {
        let mut got = 0u32;
        // SAFETY: the buffers are valid for the sizes given.
        let ok = unsafe {
            DeviceIoControl(
                h.0,
                code,
                if input.is_empty() { std::ptr::null() } else { input.as_ptr().cast() },
                input.len() as u32,
                if output.is_empty() { std::ptr::null_mut() } else { output.as_mut_ptr().cast() },
                output.len() as u32,
                &mut got,
                std::ptr::null_mut(),
            )
        };
        // SAFETY: no arguments.
        if ok != 0 { Ok(got) } else { Err(unsafe { GetLastError() }) }
    }

    /// The disk's number (N of \\.\PhysicalDriveN) behind a handle.
    fn device_number(h: &Handle) -> Option<u32> {
        let mut out = [0u8; std::mem::size_of::<STORAGE_DEVICE_NUMBER>()];
        ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, &[], &mut out).ok()?;
        // SAFETY: the buffer holds a whole STORAGE_DEVICE_NUMBER.
        let n: STORAGE_DEVICE_NUMBER = unsafe { std::ptr::read_unaligned(out.as_ptr().cast()) };
        Some(n.DeviceNumber)
    }

    /// Vendor, product and revision as the system read them from the disk
    /// (for USB disks: from its INQUIRY data).
    fn identity(h: &Handle) -> Option<(String, String, String)> {
        let query = STORAGE_PROPERTY_QUERY {
            PropertyId: StorageDeviceProperty,
            QueryType: PropertyStandardQuery,
            AdditionalParameters: [0],
        };
        // SAFETY: plain old data viewed as bytes for the call.
        let input = unsafe {
            std::slice::from_raw_parts(
                (&query as *const STORAGE_PROPERTY_QUERY).cast::<u8>(),
                std::mem::size_of_val(&query),
            )
        };
        let mut buf = vec![0u8; 1024];
        let got = ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, input, &mut buf).ok()? as usize;
        if got < std::mem::size_of::<STORAGE_DEVICE_DESCRIPTOR>() {
            return None;
        }
        buf.truncate(got);
        // SAFETY: the buffer holds at least a whole descriptor (checked above).
        let d: STORAGE_DEVICE_DESCRIPTOR = unsafe { std::ptr::read_unaligned(buf.as_ptr().cast()) };
        let text = |off: u32| -> String {
            let off = off as usize;
            if off == 0 || off >= buf.len() {
                return String::new();
            }
            let end = buf[off..].iter().position(|&b| b == 0).map_or(buf.len(), |p| off + p);
            String::from_utf8_lossy(&buf[off..end]).into_owned()
        };
        Some((text(d.VendorIdOffset), text(d.ProductIdOffset), text(d.ProductRevisionOffset)))
    }

    pub fn disks() -> Vec<Disk> {
        // Drive letters by disk number (a volume on a removable disk).
        let mut letters: Vec<(u32, PathBuf)> = Vec::new();
        for c in b'A'..=b'Z' {
            let c = c as char;
            if let Ok(h) = open_with(&format!("\\\\.\\{c}:"), 0)
                && let Some(n) = device_number(&h)
            {
                letters.push((n, PathBuf::from(format!("{c}:\\"))));
            }
        }
        let mut out = Vec::new();
        // (Disk numbers are small; gaps are allowed, so look past them.)
        for n in 0..64u32 {
            let device = format!("\\\\.\\PhysicalDrive{n}");
            let Ok(h) = open_with(&device, 0) else { continue };
            let Some((vendor, product, revision)) = identity(&h) else { continue };
            let mounted = letters.iter().find(|(m, _)| *m == n).map(|(_, p)| p.clone());
            out.push(Disk { device, vendor, product, revision, mounted });
        }
        out
    }

    /// The disk, opened for SCSI commands (needs admin rights).
    struct Device(Handle);

    /// SCSI_PASS_THROUGH_DIRECT with room for sense data after it.
    #[repr(C)]
    struct WithSense {
        sptd: SCSI_PASS_THROUGH_DIRECT,
        sense: [u8; 32],
    }

    impl Scsi for Device {
        fn command(&mut self, cdb: &[u8], data: Option<&mut [u8]>) -> std::io::Result<Reply> {
            // SAFETY: zero is a valid value for every field.
            let mut p: WithSense = unsafe { std::mem::zeroed() };
            p.sptd.Length = std::mem::size_of::<SCSI_PASS_THROUGH_DIRECT>() as u16;
            p.sptd.CdbLength = cdb.len() as u8;
            p.sptd.Cdb[..cdb.len()].copy_from_slice(cdb);
            p.sptd.SenseInfoLength = p.sense.len() as u8;
            p.sptd.SenseInfoOffset = std::mem::offset_of!(WithSense, sense) as u32;
            p.sptd.TimeOutValue = 10;
            match data {
                Some(buf) => {
                    p.sptd.DataIn = SCSI_IOCTL_DATA_IN as u8;
                    p.sptd.DataTransferLength = buf.len() as u32;
                    p.sptd.DataBuffer = buf.as_mut_ptr().cast();
                }
                None => p.sptd.DataIn = SCSI_IOCTL_DATA_UNSPECIFIED as u8,
            }
            // SAFETY: the struct is used as its own input and output buffer,
            // as the IOCTL documents; the data buffer outlives the call.
            let bytes = unsafe {
                std::slice::from_raw_parts_mut(
                    (&mut p as *mut WithSense).cast::<u8>(),
                    std::mem::size_of::<WithSense>(),
                )
            };
            let copy = bytes.to_vec();
            ioctl(&self.0, IOCTL_SCSI_PASS_THROUGH_DIRECT, &copy, bytes)
                .map_err(|e| std::io::Error::from_raw_os_error(e as i32))?;
            let sense_len = if p.sptd.ScsiStatus != 0 { p.sense.len() } else { 0 };
            Ok(Reply {
                status: p.sptd.ScsiStatus,
                sense: p.sense[..sense_len].to_vec(),
                read: p.sptd.DataTransferLength as usize,
            })
        }
    }

    pub fn open(device: &str) -> Result<Box<dyn Scsi>, UsbError> {
        match open_with(device, GENERIC_READ | GENERIC_WRITE) {
            Ok(h) => Ok(Box::new(Device(h))),
            Err(ERROR_ACCESS_DENIED) => Err(UsbError::NeedsAdmin(format!("{device} can only be opened as admin"))),
            Err(e) => Err(UsbError::Io(format!("couldn't open {device} (Windows error {e})"))),
        }
    }

    /// Writes everything waiting to the drive and takes it off line, before
    /// "eject" (the handle keeps it closed until dropped).
    pub fn close_volume(volume: &Path) -> Result<Handle, UsbError> {
        let letter = volume.to_string_lossy().trim_end_matches(['\\', '/']).to_string();
        let path = format!("\\\\.\\{letter}");
        let h = open_with(&path, GENERIC_READ | GENERIC_WRITE)
            .map_err(|e| UsbError::Io(format!("couldn't open the drive {letter} to close it (Windows error {e})")))?;
        // SAFETY: a valid handle.
        let flushed = unsafe { FlushFileBuffers(h.0) } != 0;
        note(format!("  {letter}: flushed: {flushed}"));
        // A lock fails while files are open; dismounting works anyway.
        let locked = ioctl(&h, FSCTL_LOCK_VOLUME, &[], &mut []).is_ok();
        let dismounted = ioctl(&h, FSCTL_DISMOUNT_VOLUME, &[], &mut []);
        note(format!("  {letter}: locked: {locked}, dismounted: {:?}", dismounted.map(|_| ())));
        dismounted.map_err(|e| UsbError::Io(format!("couldn't close the drive {letter} (Windows error {e})")))?;
        Ok(h)
    }

    pub fn is_admin() -> bool {
        // SAFETY: no arguments.
        unsafe { windows_sys::Win32::UI::Shell::IsUserAnAdmin() != 0 }
    }

    /// Starts `exe args` with the admin prompt, waits; its exit code.
    pub fn run_as_admin(exe: &Path, args: &[String]) -> Result<i32, UsbError> {
        use windows_sys::Win32::System::Threading::{GetExitCodeProcess, WaitForSingleObject};
        use windows_sys::Win32::UI::Shell::{
            SEE_MASK_NO_CONSOLE, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW, ShellExecuteExW,
        };
        let quote = |a: &str| format!("\"{}\"", a.replace('"', "\\\""));
        let params = args.iter().map(|a| quote(a)).collect::<Vec<_>>().join(" ");
        let (verb, file, params) = (wide("runas"), wide(&exe.to_string_lossy()), wide(&params));
        // SAFETY: zero is a valid value for every field.
        let mut info: SHELLEXECUTEINFOW = unsafe { std::mem::zeroed() };
        info.cbSize = std::mem::size_of::<SHELLEXECUTEINFOW>() as u32;
        info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NO_CONSOLE;
        info.lpVerb = verb.as_ptr();
        info.lpFile = file.as_ptr();
        info.lpParameters = params.as_ptr();
        info.nShow = windows_sys::Win32::UI::WindowsAndMessaging::SW_HIDE;
        // SAFETY: the strings outlive the call.
        if unsafe { ShellExecuteExW(&mut info) } == 0 {
            // SAFETY: no arguments.
            let e = unsafe { GetLastError() };
            return Err(if e == ERROR_CANCELLED {
                UsbError::NeedsAdmin("the admin prompt was answered No".into())
            } else {
                UsbError::Io(format!("couldn't start the helper (Windows error {e})"))
            });
        }
        let process = Handle(info.hProcess);
        // SAFETY: a valid process handle.
        unsafe { WaitForSingleObject(process.0, 120_000) };
        let mut code = 0u32;
        // SAFETY: as above.
        unsafe { GetExitCodeProcess(process.0, &mut code) };
        Ok(code as i32)
    }

    pub fn free_space(path: &Path) -> Option<u64> {
        let name = wide(&path.to_string_lossy());
        let mut free = 0u64;
        // SAFETY: valid pointers for the call.
        let ok = unsafe { GetDiskFreeSpaceExW(name.as_ptr(), &mut free, std::ptr::null_mut(), std::ptr::null_mut()) };
        (ok != 0).then_some(free)
    }
}

// ---------------------------------------------------------------- Linux

#[cfg(target_os = "linux")]
mod platform {
    use super::{Disk, Reply, Scsi, UsbError, note};
    use std::os::unix::io::AsRawFd;
    use std::path::{Path, PathBuf};

    /// SCSI disks from sysfs (/sys/block/sdX/device/vendor, model, rev:
    /// the INQUIRY strings), and where /proc/mounts has them or a partition.
    pub fn disks() -> Vec<Disk> {
        let mounts = std::fs::read_to_string("/proc/mounts").unwrap_or_default();
        let read =
            |p: PathBuf| std::fs::read_to_string(p).map(|s| s.trim_end_matches('\n').to_string()).unwrap_or_default();
        let mut out = Vec::new();
        let Ok(dir) = std::fs::read_dir("/sys/block") else { return out };
        let mut names: Vec<String> = dir.flatten().map(|e| e.file_name().to_string_lossy().into_owned()).collect();
        names.sort();
        for name in names.into_iter().filter(|n| n.starts_with("sd")) {
            let dev = PathBuf::from("/sys/block").join(&name).join("device");
            let device = format!("/dev/{name}");
            let mounted = mounts.lines().find_map(|l| {
                let mut f = l.split_whitespace();
                let (src, at) = (f.next()?, f.next()?);
                src.starts_with(&device).then(|| PathBuf::from(at.replace("\\040", " ")))
            });
            out.push(Disk {
                device,
                vendor: read(dev.join("vendor")),
                product: read(dev.join("model")),
                revision: read(dev.join("rev")),
                mounted,
            });
        }
        out
    }

    /// The kernel's sg_io_hdr (scsi/sg.h), for SG_IO.
    #[repr(C)]
    struct SgIoHdr {
        interface_id: i32,
        dxfer_direction: i32,
        cmd_len: u8,
        mx_sb_len: u8,
        iovec_count: u16,
        dxfer_len: u32,
        dxferp: *mut libc::c_void,
        cmdp: *const u8,
        sbp: *mut u8,
        timeout: u32,
        flags: u32,
        pack_id: i32,
        usr_ptr: *mut libc::c_void,
        status: u8,
        masked_status: u8,
        msg_status: u8,
        sb_len_wr: u8,
        host_status: u16,
        driver_status: u16,
        resid: i32,
        duration: u32,
        info: u32,
    }
    const SG_IO: libc::c_ulong = 0x2285;
    const SG_DXFER_NONE: i32 = -1;
    const SG_DXFER_FROM_DEV: i32 = -3;

    struct Device(std::fs::File);

    impl Scsi for Device {
        fn command(&mut self, cdb: &[u8], data: Option<&mut [u8]>) -> std::io::Result<Reply> {
            let mut sense = [0u8; 32];
            let (dir, len, ptr) = match data {
                Some(buf) => (SG_DXFER_FROM_DEV, buf.len() as u32, buf.as_mut_ptr().cast()),
                None => (SG_DXFER_NONE, 0, std::ptr::null_mut()),
            };
            let mut h = SgIoHdr {
                interface_id: b'S' as i32,
                dxfer_direction: dir,
                cmd_len: cdb.len() as u8,
                mx_sb_len: sense.len() as u8,
                iovec_count: 0,
                dxfer_len: len,
                dxferp: ptr,
                cmdp: cdb.as_ptr(),
                sbp: sense.as_mut_ptr(),
                timeout: 10_000,
                flags: 0,
                pack_id: 0,
                usr_ptr: std::ptr::null_mut(),
                status: 0,
                masked_status: 0,
                msg_status: 0,
                sb_len_wr: 0,
                host_status: 0,
                driver_status: 0,
                resid: 0,
                duration: 0,
                info: 0,
            };
            // SAFETY: the header and the buffers it points to outlive the call.
            if unsafe { libc::ioctl(self.0.as_raw_fd(), SG_IO as _, &mut h) } < 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(Reply {
                status: h.status,
                sense: sense[..h.sb_len_wr as usize].to_vec(),
                read: (len as i32 - h.resid).max(0) as usize,
            })
        }
    }

    pub fn open(device: &str) -> Result<Box<dyn Scsi>, UsbError> {
        use std::os::unix::fs::OpenOptionsExt;
        match std::fs::OpenOptions::new().read(true).write(true).custom_flags(libc::O_NONBLOCK).open(device) {
            Ok(f) => Ok(Box::new(Device(f))),
            Err(e) if e.kind() == std::io::ErrorKind::PermissionDenied => {
                Err(UsbError::NeedsAdmin(format!("{device} can only be opened as root")))
            }
            Err(e) => Err(UsbError::Io(format!("couldn't open {device}: {e}"))),
        }
    }

    /// Writes everything waiting to the card and unmounts it, before "eject".
    pub fn close_volume(volume: &Path) -> Result<(), UsbError> {
        // SAFETY: no arguments.
        unsafe { libc::sync() };
        let out = std::process::Command::new("umount").arg(volume).output();
        note(format!("  sync, umount {}: {:?}", volume.display(), out.as_ref().map(|o| o.status)));
        match out {
            Ok(o) if o.status.success() => Ok(()),
            Ok(o) => Err(UsbError::Io(format!(
                "couldn't unmount {}: {}",
                volume.display(),
                String::from_utf8_lossy(&o.stderr).trim()
            ))),
            Err(e) => Err(UsbError::Io(format!("couldn't run umount: {e}"))),
        }
    }

    pub fn is_admin() -> bool {
        // SAFETY: no arguments.
        unsafe { libc::geteuid() == 0 }
    }

    /// Runs `exe args` through pkexec (the desktop's admin prompt); its exit code.
    pub fn run_as_admin(exe: &Path, args: &[String]) -> Result<i32, UsbError> {
        match std::process::Command::new("pkexec").arg(exe).args(args).status() {
            // pkexec: 126 = not authorised (dialog dismissed), 127 = failed.
            Ok(s) if s.code() == Some(126) => Err(UsbError::NeedsAdmin("the admin prompt was cancelled".into())),
            Ok(s) => Ok(s.code().unwrap_or(-1)),
            Err(e) => Err(UsbError::NeedsAdmin(format!(
                "pkexec isn't available ({e}); run LeapLoader with sudo for this step"
            ))),
        }
    }

    pub fn free_space(path: &Path) -> Option<u64> {
        use std::os::unix::ffi::OsStrExt;
        let c = std::ffi::CString::new(path.as_os_str().as_bytes()).ok()?;
        // SAFETY: zeroed is a valid statvfs; the path is NUL-terminated.
        let mut s: libc::statvfs = unsafe { std::mem::zeroed() };
        (unsafe { libc::statvfs(c.as_ptr(), &mut s) } == 0).then(|| s.f_bavail as u64 * s.f_frsize as u64)
    }
}

// ---------------------------------------------------------------- others

#[cfg(not(any(windows, target_os = "linux")))]
mod platform {
    use super::{Disk, Scsi, UsbError};
    use std::path::Path;

    /// macOS (IOKit) is not done yet: nothing is found there.
    pub fn disks() -> Vec<Disk> {
        Vec::new()
    }
    pub fn open(_device: &str) -> Result<Box<dyn Scsi>, UsbError> {
        Err(UsbError::Unsupported)
    }
    pub fn close_volume(_volume: &Path) -> Result<(), UsbError> {
        Err(UsbError::Unsupported)
    }
    pub fn is_admin() -> bool {
        false
    }
    pub fn run_as_admin(_exe: &Path, _args: &[String]) -> Result<i32, UsbError> {
        Err(UsbError::Unsupported)
    }
    pub fn free_space(_path: &Path) -> Option<u64> {
        None
    }
}

// ---------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_leapster_2s_disks_are_ours() {
        // The INQUIRY strings, space padded as the BIOS has them.
        assert_eq!(classify("LeapFrog", "Leapster 2-SD   "), Some(Kind::Sd));
        assert_eq!(classify("LeapFrog", "Leapster 2-RAM  "), Some(Kind::Internal));
        assert_eq!(classify("LeapFrog ", "Leapster 2-SD"), Some(Kind::Sd));
        // LFTools' looser rule: another BIOS may pad or name it differently.
        assert_eq!(classify("LeapFrog", "Leapster2-SD"), Some(Kind::Sd));
        assert_eq!(classify("LeapFrog", "L2-SD"), Some(Kind::Sd));
        // ...but only from LeapFrog.
        assert_eq!(classify("Generic", "Card 2-SD"), None);
        for (v, p) in [
            ("SanDisk", "Ultra"),
            ("Generic-", "SD/MMC"),
            ("LeapFrog", "Leapster Explorer"),
            ("LeapFrog", "LeapPad"),
            ("leapfrog", "Leapster 2-SD"),
            ("", ""),
        ] {
            assert_eq!(classify(v, p), None, "{v} {p}");
        }
    }

    const SD: &[u8; 36] = b"\x00\x80\x00\x01\x1F\x00\x00\x00LeapFrogLeapster 2-SD   1.00";
    const RAM: &[u8; 36] = b"\x00\x80\x00\x01\x1F\x00\x00\x00LeapFrogLeapster 2-RAM  1.00";
    const OTHER: &[u8; 36] = b"\x00\x80\x00\x01\x1F\x00\x00\x00SanDisk Cruzer Blade    1.00";
    /// Sense data for "not ready, medium not present" (02/3A/00).
    const NO_MEDIUM: [u8; 18] = [0x70, 0, 2, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0x3A, 0, 0, 0, 0, 0];
    /// "Illegal request, invalid command" (05/20/00).
    const BAD_COMMAND: [u8; 18] = [0x70, 0, 5, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0x20, 0, 0, 0, 0, 0];

    /// A pretend console, BIOS 0.6's behaviour from docs/usb-research.md:
    /// INQUIRY answers its identity; TEST UNIT READY fails until "mount".
    struct Fake {
        inquiry: &'static [u8; 36],
        mounted: bool,
        /// How "mount" and "eject" answer (status, sense).
        mount_reply: (u8, Vec<u8>),
        eject_reply: (u8, Vec<u8>),
        /// TEST UNIT READY keeps failing (no card in the console).
        no_card: bool,
        sent: Vec<u8>,
    }

    impl Fake {
        fn new(inquiry: &'static [u8; 36]) -> Self {
            Fake {
                inquiry,
                mounted: false,
                mount_reply: (0, vec![]),
                eject_reply: (0, vec![]),
                no_card: false,
                sent: vec![],
            }
        }
    }

    impl Scsi for Fake {
        fn command(&mut self, cdb: &[u8], data: Option<&mut [u8]>) -> std::io::Result<Reply> {
            self.sent.push(cdb[0]);
            let reply = |(status, sense): (u8, Vec<u8>)| Reply { status, sense, read: 0 };
            Ok(match cdb[0] {
                0x12 => {
                    let buf = data.unwrap();
                    let n = buf.len().min(36);
                    buf[..n].copy_from_slice(&self.inquiry[..n]);
                    Reply { status: 0, sense: vec![], read: n }
                }
                0xC2 => {
                    if self.mount_reply.0 == 0 {
                        self.mounted = true;
                    }
                    reply(self.mount_reply.clone())
                }
                0x00 if self.mounted && !self.no_card => reply((0, vec![])),
                0x00 => reply((2, NO_MEDIUM.to_vec())),
                0xC6 => reply(self.eject_reply.clone()),
                _ => reply((2, BAD_COMMAND.to_vec())),
            })
        }
    }

    #[test]
    fn mount_sends_c2_then_waits_until_ready() {
        let mut dev = Fake::new(SD);
        mount_sd(&mut dev, Duration::ZERO, 5).unwrap();
        assert_eq!(dev.sent, [0x12, 0xC2, 0x00]);
    }

    #[test]
    fn nothing_but_inquiry_goes_to_another_disk() {
        for id in [OTHER, RAM] {
            let mut dev = Fake::new(id);
            assert!(matches!(mount_sd(&mut dev, Duration::ZERO, 5), Err(UsbError::NotLeapster(_))));
            assert_eq!(dev.sent, [0x12], "only INQUIRY was sent");
        }
        let mut dev = Fake::new(OTHER);
        assert!(matches!(eject(&mut dev), Err(UsbError::NotLeapster(_))));
        assert_eq!(dev.sent, [0x12]);
    }

    #[test]
    fn a_refused_mount_says_why() {
        let mut dev = Fake::new(SD);
        dev.mount_reply = (2, BAD_COMMAND.to_vec());
        let e = mount_sd(&mut dev, Duration::ZERO, 5).unwrap_err();
        assert_eq!(e, UsbError::Refused { what: "mount (C2)", status: 2, sense: BAD_COMMAND.to_vec() });
        assert!(e.to_string().contains("sense key 5 (illegal request), ASC 20h ASCQ 00h"), "{e}");
    }

    #[test]
    fn no_card_is_not_ready() {
        let mut dev = Fake::new(SD);
        dev.no_card = true;
        let e = mount_sd(&mut dev, Duration::ZERO, 3).unwrap_err();
        assert_eq!(e, UsbError::NotReady(NO_MEDIUM.to_vec()));
        assert!(e.to_string().contains("not ready"), "{e}");
        assert_eq!(dev.sent, [0x12, 0xC2, 0x00, 0x00, 0x00]);
    }

    #[test]
    fn eject_sends_c6_to_either_disk() {
        for id in [SD, RAM] {
            let mut dev = Fake::new(id);
            eject(&mut dev).unwrap();
            assert_eq!(dev.sent, [0x12, 0xC6]);
        }
        let mut dev = Fake::new(SD);
        dev.eject_reply = (2, BAD_COMMAND.to_vec());
        assert!(matches!(eject(&mut dev), Err(UsbError::Refused { what: "eject (C6)", .. })));
    }

    #[test]
    fn the_log_has_every_command() {
        let mut dev = Fake::new(SD);
        dev.mount_reply = (2, BAD_COMMAND.to_vec());
        let _ = mount_sd(&mut dev, Duration::ZERO, 1);
        let log = log_text();
        assert!(log.contains("INQUIRY [12 00 00 00 24 00]: status 0"), "{log}");
        assert!(log.contains("mount (C2) [C2 00 00 00 00 00 00 00 00 00]: status 2, sense key 5"), "{log}");
    }

    #[test]
    fn sense_data_in_words() {
        assert_eq!(sense_text(&[]), "");
        assert_eq!(sense_text(&NO_MEDIUM), ", sense key 2 (not ready), ASC 3Ah ASCQ 00h");
        assert_eq!(sense_text(&[1, 2]), ", sense 01 02");
    }

    #[test]
    fn helper_exit_codes_are_distinct() {
        let all = [
            UsbError::NotLeapster(String::new()),
            UsbError::NeedsAdmin(String::new()),
            UsbError::Refused { what: "", status: 0, sense: vec![] },
            UsbError::NotReady(vec![]),
            UsbError::NoVolume(0),
            UsbError::Unsupported,
            UsbError::Io(String::new()),
        ];
        let mut codes: Vec<i32> = all.iter().map(exit_code).collect();
        codes.dedup();
        assert_eq!(codes.len(), all.len());
        assert!(!codes.contains(&0), "0 is success");
        // run_elevated reads 3 as "no admin rights".
        assert_eq!(exit_code(&all[1]), 3);
    }
}
