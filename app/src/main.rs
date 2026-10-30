// SPDX-License-Identifier: GPL-3.0-or-later
//! LeapLoader's desktop app: puts the user's own Leapster cartridge dumps
//! on an SD card for the Leapster 2. A window in Ribbit's look (egui on
//! wgpu); for now the card itself is built by LeapLoader's research scripts
//! (card.rs).
//!
//! `leaploader --names FILES...` prints each dump's CRC-32 and the name the
//! card gives it (no window), to compare with research/gamenames.py.
//! `leaploader --usb-list` prints every disk the system knows with its
//! identity, and which are a Leapster 2's (reading only);
//! `leaploader --usb-helper ...` is the elevated USB helper (usb.rs).
//! LEAPLOADER_DATA: another folder for settings.toml (tests).
#![cfg_attr(windows, windows_subsystem = "windows")]

mod app;
mod card;
mod emulators;
mod files;
mod fonts;
mod gamenames;
mod games;
mod gpu;
mod icon;
mod install;
mod log;
mod notify;
mod settings;
mod tags;
mod ui;
mod updates;
mod usb;

fn main() {
    let args: Vec<std::ffi::OsString> = std::env::args_os().collect();
    // The USB helper: one step on the Leapster 2 with admin rights (usb.rs).
    if args.get(1).is_some_and(|a| a == usb::HELPER_ARG) {
        std::process::exit(usb::helper_main(&args[2..]));
    }
    if args.get(1).is_some_and(|a| a == "--names") {
        std::process::exit(print_names(&args[2..]));
    }
    if args.get(1).is_some_and(|a| a == "--usb-list") {
        #[cfg(windows)]
        attach_console();
        for d in usb::disks() {
            let what = d.leapster().map_or("not a Leapster 2", usb::Kind::label);
            let at = d.mounted.as_ref().map_or_else(String::new, |m| format!(" at {}", m.display()));
            println!("{}\t{:?} {:?} {:?}\t{what}{at}", d.device, d.vendor, d.product, d.revision);
        }
        return;
    }
    let data_dir: std::path::PathBuf =
        std::env::var_os("LEAPLOADER_DATA").map_or_else(settings::default_data_dir, Into::into);
    // Nobody sees the window-less program's stderr: a log in the data
    // folder for players to send (as Ribbit's ribbit.log).
    log::init(&data_dir.join("leaploader.log"));
    std::panic::set_hook(Box::new(|info| {
        let backtrace = std::backtrace::Backtrace::force_capture();
        log::line(&format!(
            "panic: {info}
{backtrace}"
        ));
        // A panic on the window's thread ends LeapLoader: say so instead of
        // closing without a word.
        if std::thread::current().name() == Some("main") {
            failed(&format!(
                "LeapLoader stopped because of a bug:

{info}"
            ));
        }
    }));
    #[cfg(windows)]
    log::log_native_crashes();
    if let Err(e) = app::run(data_dir) {
        failed(&format!("LeapLoader could not start:\n\n{e:#}"));
    }
}

fn print_names(files: &[std::ffi::OsString]) -> i32 {
    // The window-less program has no console on Windows: write to the one
    // it was started from, if any.
    #[cfg(windows)]
    attach_console();
    let mut code = 0;
    for f in files {
        let path = std::path::Path::new(f);
        match games::Dump::open(path) {
            Ok(d) => println!("{:08X}\t{}\t{}\t{}", d.crc, d.name, d.tags.join(", "), path.display()),
            Err(e) => {
                eprintln!("{}: {e:#}", path.display());
                code = 1;
            }
        }
    }
    code
}

#[cfg(windows)]
fn attach_console() {
    unsafe extern "system" {
        fn AttachConsole(process: u32) -> i32;
    }
    const ATTACH_PARENT_PROCESS: u32 = u32::MAX;
    // SAFETY: a plain Win32 call with no pointers.
    unsafe { AttachConsole(ATTACH_PARENT_PROCESS) };
}

/// Says why LeapLoader stopped: stderr, and on Windows and macOS a message
/// box (the window may never have drawn anything).
fn failed(msg: &str) {
    log::line(msg);
    let msg = match log::path() {
        Some(p) => format!(
            "{msg}

Please send {} with your report.",
            p.display()
        ),
        None => msg.to_string(),
    };
    let msg = msg.as_str();
    rfd::MessageDialog::new().set_title("LeapLoader").set_description(msg).set_level(rfd::MessageLevel::Error).show();
    std::process::exit(1);
}
