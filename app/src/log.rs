// SPDX-License-Identifier: GPL-3.0-or-later
//! leaploader.log in the data folder, rewritten at each start, for players to
//! send when LeapLoader closes or misbehaves (as Ribbit's ribbit.log: nobody
//! sees the window-less program's stderr). Also records panics and, on
//! Windows, crashes outside Rust with the DLL they happened in (Ribbit's
//! crates/ribbit-desktop/src/app.rs `log_native_crashes`).

use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

static LOG: OnceLock<(PathBuf, Mutex<Option<std::fs::File>>, Instant)> = OnceLock::new();

/// Starts the log at `path` (the old one is replaced).
pub fn init(path: &Path) {
    let _ = std::fs::create_dir_all(path.parent().unwrap_or(Path::new(".")));
    let file = std::fs::File::create(path).ok();
    let _ = LOG.set((path.to_path_buf(), Mutex::new(file), Instant::now()));
    line(&format!("LeapLoader {} ({} {})", env!("CARGO_PKG_VERSION"), std::env::consts::OS, std::env::consts::ARCH));
}

/// Writes one line (time since start, then `msg`) to the log and stderr.
pub fn line(msg: &str) {
    eprintln!("{msg}");
    if let Some((_, file, start)) = LOG.get()
        && let Ok(mut f) = file.lock()
        && let Some(f) = f.as_mut()
    {
        let _ = writeln!(f, "{:9.3} s  {msg}", start.elapsed().as_secs_f64());
        let _ = f.flush();
    }
}

/// The log file's path (None before `init`).
pub fn path() -> Option<PathBuf> {
    LOG.get().map(|(p, _, _)| p.clone())
}

/// A crash outside Rust (an access violation in a graphics driver, say) ends
/// the process without a panic, so the log would just stop. This logs the
/// exception and the DLL it happened in, then lets Windows end the process.
#[cfg(windows)]
pub fn log_native_crashes() {
    use std::ffi::c_void;
    #[repr(C)]
    struct ExceptionRecord {
        code: u32,
        flags: u32,
        next: *mut ExceptionRecord,
        address: *mut c_void,
    }
    #[repr(C)]
    struct ExceptionPointers {
        record: *mut ExceptionRecord,
        context: *mut c_void,
    }
    type Filter = unsafe extern "system" fn(*const ExceptionPointers) -> i32;
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn SetUnhandledExceptionFilter(filter: Option<Filter>) -> Option<Filter>;
        fn GetModuleHandleExW(flags: u32, address: *const c_void, module: *mut *mut c_void) -> i32;
        fn GetModuleFileNameW(module: *mut c_void, name: *mut u16, size: u32) -> u32;
    }
    const FROM_ADDRESS: u32 = 0x4;
    const UNCHANGED_REFCOUNT: u32 = 0x2;
    const CONTINUE_SEARCH: i32 = 0;

    unsafe extern "system" fn filter(info: *const ExceptionPointers) -> i32 {
        // SAFETY: Windows passes valid exception pointers to the filter.
        let Some(record) = (unsafe { info.as_ref() }).and_then(|i| unsafe { i.record.as_ref() }) else {
            return CONTINUE_SEARCH;
        };
        let mut module = std::ptr::null_mut();
        let mut name = [0u16; 260];
        // SAFETY: `module` and `name` are valid for the calls' writes.
        let len = unsafe {
            if GetModuleHandleExW(FROM_ADDRESS | UNCHANGED_REFCOUNT, record.address, &mut module) == 0 {
                0
            } else {
                GetModuleFileNameW(module, name.as_mut_ptr(), name.len() as u32)
            }
        };
        let place = match len {
            0 => "an unknown module".to_string(),
            n => format!(
                "{} + {:#x}",
                String::from_utf16_lossy(&name[..n as usize]),
                record.address as usize - module as usize
            ),
        };
        line(&format!(
            "LeapLoader crashed: exception {:#010x} at {:#x} in {place} (thread {:?})",
            record.code,
            record.address as usize,
            std::thread::current().name().unwrap_or("unnamed"),
        ));
        CONTINUE_SEARCH
    }

    // SAFETY: `filter` has the signature Windows expects and lives forever.
    unsafe { SetUnhandledExceptionFilter(Some(filter)) };
}
