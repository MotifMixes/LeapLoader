// SPDX-License-Identifier: GPL-3.0-or-later
//! Choosing files and folders with the system's dialogs (rfd), after
//! Ribbit's crates/ribbit-frontend/src/files.rs (its macOS sheet, used here
//! on every system).

use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Pick {
    /// Cartridge dumps for the list (several at once).
    Dumps,
    /// A folder of dumps (every .bin and .zip in it).
    DumpFolder,
    /// The folder the card is built into.
    Output,
    /// LeapFrog's SD menu package (.lfp) or SDMenu.bin.
    LeapFrogMenu,
    /// LeapLoader's research folder (with mkcard.py).
    Research,
    Nativescan,
    /// The Leapster 2 BIOS 0.6 dump (the menu music's instruments).
    Bios,
}

impl Pick {
    pub fn title(self) -> &'static str {
        match self {
            Pick::Dumps => "Add Leapster cartridge dumps",
            Pick::DumpFolder => "Add every dump in a folder",
            Pick::Output => "Choose the folder to build the card in",
            Pick::LeapFrogMenu => "Choose LeapFrog's SD menu (.lfp package or SDMenu.bin)",
            Pick::Research => "Choose LeapLoader's research folder (with mkcard.py)",
            Pick::Nativescan => "Choose nativescan",
            Pick::Bios => "Choose your Leapster 2 BIOS 0.6 dump (152-12206)",
        }
    }

    pub fn is_folder(self) -> bool {
        matches!(self, Pick::DumpFolder | Pick::Output | Pick::Research)
    }

    fn filters(self) -> &'static [(&'static str, &'static [&'static str])] {
        match self {
            Pick::Dumps => &[("Leapster dumps", &["bin", "zip"])],
            Pick::Bios => &[("BIOS dumps", &["bin"])],
            Pick::LeapFrogMenu => &[("LeapFrog SD menu", &["lfp", "bin"])],
            // (A program has no extension outside Windows: "All files".)
            Pick::Nativescan if cfg!(windows) => &[("Programs", &["exe"])],
            Pick::Nativescan | Pick::DumpFolder | Pick::Output | Pick::Research => &[],
        }
    }
}

fn start_dir(start: Option<&Path>) -> Option<&Path> {
    start.and_then(|p| if p.is_dir() { Some(p) } else { p.parent() })
}

/// The system's dialog, shown at once and answered later while the event
/// loop and drawing carry on (`poll` it each frame): a sheet on the window
/// on macOS (Ribbit's `SheetPick`: a modal panel run from inside winit's
/// event handler holds up every event until it closes), and on Windows and
/// Linux a dialog on its own thread, so the window keeps drawing too.
pub struct SheetPick {
    pub what: Pick,
    answer: std::pin::Pin<Box<dyn std::future::Future<Output = Vec<PathBuf>> + Send>>,
}

impl SheetPick {
    pub fn start(what: Pick, start: Option<&Path>, window: &winit::window::Window) -> Self {
        let mut d = rfd::AsyncFileDialog::new().set_title(what.title()).set_parent(window);
        if let Some(dir) = start_dir(start) {
            d = d.set_directory(dir);
        }
        let paths = |files: Vec<rfd::FileHandle>| files.into_iter().map(|f| f.path().to_path_buf()).collect();
        let answer: std::pin::Pin<Box<dyn std::future::Future<Output = Vec<PathBuf>> + Send>> = if what.is_folder() {
            let f = d.pick_folder();
            Box::pin(async move { paths(f.await.into_iter().collect()) })
        } else {
            for (name, ext) in what.filters() {
                d = d.add_filter(*name, ext);
            }
            d = d.add_filter("All files", &["*"]);
            if what == Pick::Dumps {
                let f = d.pick_files();
                Box::pin(async move { paths(f.await.unwrap_or_default()) })
            } else {
                let f = d.pick_file();
                Box::pin(async move { paths(f.await.into_iter().collect()) })
            }
        };
        Self { what, answer }
    }

    /// `Some` once the panel has closed: the chosen paths (empty: cancelled).
    pub fn poll(&mut self) -> Option<Vec<PathBuf>> {
        let mut cx = std::task::Context::from_waker(std::task::Waker::noop());
        match self.answer.as_mut().poll(&mut cx) {
            std::task::Poll::Ready(files) => Some(files),
            std::task::Poll::Pending => None,
        }
    }
}
