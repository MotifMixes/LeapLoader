// SPDX-License-Identifier: GPL-3.0-or-later
//! In-app update (Ribbit's crates/ribbit-frontend/src/install.rs, for
//! LeapLoader's package): downloads this system's package from a GitHub
//! release, puts it in place of the running one, and restarts into it.
//!
//! LeapLoader's package is a folder, not one program: the app, nativescan,
//! the ARC binutils, the research scripts and a Python of its own. On
//! Windows and Linux the package is unpacked beside them (`.leaploader-
//! update/new`), then each of its top-level files and folders takes the
//! place of the old one, which moves aside (`.leaploader-update/old`,
//! removed at the next start; a running program can be renamed but not
//! overwritten). A step that fails puts everything back. macOS replaces
//! LeapLoader.app the same way Ribbit replaces Ribbit.app. Only a release
//! package installs itself (a build from source, a copy run from inside its
//! zip, or a folder LeapLoader can't write to keep the release page, and the
//! updates window says why).

use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use crate::updates::{Asset, Release};

#[derive(Debug, Clone, Default, PartialEq)]
pub enum State {
    #[default]
    Idle,
    /// Bytes so far, of `total`.
    Downloading {
        done: u64,
        total: u64,
    },
    Installing,
    /// The new version is in place: restart to run it.
    Ready,
    Failed(String),
}

/// Where the running app is, and so what an update replaces.
#[derive(Debug, Clone)]
enum Target {
    /// Windows, Linux: the package folder, and the program in it.
    Folder { dir: PathBuf, program: PathBuf },
    /// macOS: LeapLoader.app.
    Bundle(PathBuf),
}

/// Unpacked and moved-aside files of an update, in the package folder.
const WORK: &str = ".leaploader-update";
/// The program's name in the Windows and Linux packages.
const PROGRAM: &str = if cfg!(windows) { "LeapLoader.exe" } else { "leaploader" };

/// The package for this system in a release ("…-windows-x64.zip").
fn package_suffix() -> Option<&'static str> {
    if cfg!(all(windows, target_arch = "x86_64")) {
        Some("-windows-x64.zip")
    } else if cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        Some("-linux-x64.tar.gz")
    } else if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        Some("-macos-arm64.zip")
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        Some("-macos-x64.zip")
    } else {
        None
    }
}

/// The running app, when it is a release package that can update itself;
/// otherwise why not, said to the user.
fn target() -> Result<Target, String> {
    package_suffix().ok_or("there is no package for this system")?;
    let exe = std::env::current_exe().map_err(|e| format!("LeapLoader can't tell where it is ({e})"))?;
    if cfg!(target_os = "macos") {
        // LeapLoader.app/Contents/MacOS/leaploader
        return exe
            .ancestors()
            .nth(3)
            .filter(|b| b.file_name().is_some_and(|n| n.eq_ignore_ascii_case("LeapLoader.app")))
            .map(|b| Target::Bundle(b.into()))
            .ok_or_else(|| "this copy of LeapLoader isn't in LeapLoader.app".to_string());
    }
    let dir = exe.parent().ok_or("LeapLoader can't tell where it is")?.to_path_buf();
    // A release package: the program with its research scripts and Python
    // beside it (a build from source has neither in its target folder).
    let python = if cfg!(windows) { "python/python.exe" } else { "python/bin/python3" };
    if !dir.join("research/mkcard.py").is_file() || !dir.join(python).is_file() {
        return Err("this copy of LeapLoader isn't a release package (built from source?)".into());
    }
    // Opened from inside the zip, Windows unpacks the program alone into a
    // temporary folder and deletes it later; an update would go there.
    let temp = std::env::temp_dir().canonicalize().unwrap_or_else(|_| std::env::temp_dir());
    if exe.canonicalize().unwrap_or_else(|_| exe.clone()).starts_with(&temp) {
        return Err("LeapLoader is running from inside its zip or a temporary folder. Unzip all of it to a folder \
                    (right-click the zip, Extract All…) and start LeapLoader from there"
            .into());
    }
    Ok(Target::Folder { dir, program: exe })
}

/// The package to download from `release`, or why this app can't install
/// it.
pub fn installable(release: &Release) -> Result<Asset, String> {
    target()?;
    let suffix = package_suffix().ok_or("there is no package for this system")?;
    release
        .assets
        .iter()
        .find(|a| a.name.ends_with(suffix))
        .cloned()
        .ok_or_else(|| "this release has no package for this system".into())
}

/// The download and install, run in the background.
#[derive(Default)]
pub struct Installer {
    state: Arc<Mutex<State>>,
}

impl Installer {
    pub fn state(&self) -> State {
        self.state.lock().unwrap().clone()
    }

    /// Downloads and installs `asset` (unless already under way); `ctx`
    /// repaints as it goes.
    pub fn start(&self, asset: Asset, ctx: &egui::Context) {
        {
            let mut s = self.state.lock().unwrap();
            if matches!(*s, State::Downloading { .. } | State::Installing | State::Ready) {
                return;
            }
            *s = State::Downloading { done: 0, total: asset.size };
        }
        let state = Arc::clone(&self.state);
        let ctx = ctx.clone();
        let spawned = std::thread::Builder::new().name("leaploader-install".into()).spawn(move || {
            let set = |s: State| {
                *state.lock().unwrap() = s;
                ctx.request_repaint();
            };
            let result = target().and_then(|t| {
                let data = download(&asset, |done| set(State::Downloading { done, total: asset.size }))?;
                set(State::Installing);
                install(&t, &data)
            });
            match result {
                Ok(()) => {
                    crate::log::line(&format!("installed {}", asset.name));
                    set(State::Ready);
                }
                Err(e) => {
                    crate::log::line(&format!("update failed: {e}"));
                    set(State::Failed(e));
                }
            }
        });
        if let Err(e) = spawned {
            *self.state.lock().unwrap() = State::Failed(e.to_string());
        }
    }
}

fn download(asset: &Asset, mut progress: impl FnMut(u64)) -> Result<Vec<u8>, String> {
    let agent: ureq::Agent =
        ureq::Agent::config_builder().timeout_connect(Some(std::time::Duration::from_secs(15))).build().into();
    let response = agent
        .get(&asset.url)
        .header("User-Agent", concat!("LeapLoader/", env!("CARGO_PKG_VERSION")))
        .call()
        .map_err(|e| format!("couldn't download the update: {e}"))?;
    // (At most 512 MB: a package with its Python is about 60.)
    let mut reader = response.into_body().into_with_config().limit(512 << 20).reader();
    let mut data = Vec::with_capacity(asset.size as usize);
    let mut chunk = vec![0u8; 64 << 10];
    loop {
        let n = reader.read(&mut chunk).map_err(|e| format!("the download stopped: {e}"))?;
        if n == 0 {
            break;
        }
        data.extend_from_slice(&chunk[..n]);
        progress(data.len() as u64);
    }
    if data.len() as u64 != asset.size {
        return Err(format!("the download is incomplete ({} of {} bytes)", data.len(), asset.size));
    }
    Ok(data)
}

fn install(target: &Target, package: &[u8]) -> Result<(), String> {
    match target {
        Target::Folder { dir, .. } => replace_folder(dir, package),
        #[cfg(target_os = "macos")]
        Target::Bundle(app) => replace_bundle(app, package),
        #[cfg(not(target_os = "macos"))]
        Target::Bundle(_) => Err("this copy of LeapLoader can't update itself".into()),
    }
}

/// Unpacks `package` into `into` (its top folder, LeapLoader/, included).
#[cfg(windows)]
fn unpack(package: &[u8], into: &Path) -> Result<(), String> {
    let mut zip =
        zip::ZipArchive::new(std::io::Cursor::new(package)).map_err(|e| format!("the update is damaged: {e}"))?;
    zip.extract(into).map_err(|e| format!("couldn't unpack the update: {e}"))
}

/// Unpacks `package` into `into` (its top folder, LeapLoader/, included),
/// with the programs' permissions.
#[cfg(target_os = "linux")]
fn unpack(package: &[u8], into: &Path) -> Result<(), String> {
    let mut tar = tar::Archive::new(flate2::read::GzDecoder::new(package));
    tar.set_preserve_permissions(true);
    tar.unpack(into).map_err(|e| format!("couldn't unpack the update: {e}"))
}

#[cfg(not(any(windows, target_os = "linux")))]
fn unpack(_package: &[u8], _into: &Path) -> Result<(), String> {
    Err("no package to unpack on this system".into())
}

/// Puts the package's files in place of those in `dir`, which move aside.
fn replace_folder(dir: &Path, package: &[u8]) -> Result<(), String> {
    let cant = |e: std::io::Error| format!("LeapLoader can't write to its folder ({}): {e}", dir.display());
    let work = dir.join(WORK);
    // What an earlier update left (the cleanup at start-up may still be going).
    let _ = std::fs::remove_dir_all(&work);
    let unpacked = work.join("new");
    std::fs::create_dir_all(&unpacked).map_err(cant)?;
    unpack(package, &unpacked)?;
    let new = unpacked.join("LeapLoader");
    if !new.join(PROGRAM).is_file() || !new.join("research/mkcard.py").is_file() {
        return Err("the update holds no LeapLoader for this system".into());
    }
    let old = work.join("old");
    std::fs::create_dir_all(&old).map_err(cant)?;
    let names: Vec<_> = std::fs::read_dir(&new).map_err(cant)?.flatten().map(|e| e.file_name()).collect();
    // (name, whether an old one moved aside): undone in reverse on a failure.
    let mut done: Vec<(std::ffi::OsString, bool)> = Vec::new();
    let mut result = Ok(());
    for name in &names {
        let (current, aside) = (dir.join(name), old.join(name));
        let had = current.exists();
        if had && let Err(e) = std::fs::rename(&current, &aside) {
            result = Err(cant(e));
            break;
        }
        if let Err(e) = std::fs::rename(new.join(name), &current) {
            if had {
                let _ = std::fs::rename(&aside, &current);
            }
            result = Err(cant(e));
            break;
        }
        done.push((name.clone(), had));
    }
    if result.is_err() {
        // Back as it was.
        for (name, had) in done.into_iter().rev() {
            let current = dir.join(&name);
            let _ = if current.is_dir() { std::fs::remove_dir_all(&current) } else { std::fs::remove_file(&current) };
            if had {
                let _ = std::fs::rename(old.join(&name), &current);
            }
        }
    }
    result
}

/// Puts the LeapLoader.app from the macOS zip in place of `app`, which moves
/// aside. `ditto` unpacks it with its permissions and signature intact.
#[cfg(target_os = "macos")]
fn replace_bundle(app: &Path, package: &[u8]) -> Result<(), String> {
    let parent = app.parent().ok_or("LeapLoader.app has no folder")?;
    // Opened straight from a download, macOS runs a read-only copy of the app
    // from a temporary place (App Translocation).
    if parent.components().any(|c| c.as_os_str() == "AppTranslocation") {
        return Err("macOS is running LeapLoader from a temporary read-only copy. Move LeapLoader.app to your \
                    Applications folder, open it from there, and update again"
            .into());
    }
    let cant = |e: std::io::Error| format!("LeapLoader can't write to {}: {e}", parent.display());
    // Unpacked next to the app, so the new one moves into place within one disk.
    let work = parent.join(WORK);
    let _ = std::fs::remove_dir_all(&work);
    std::fs::create_dir_all(&work).map_err(cant)?;
    let result = (|| {
        let zip = work.join("update.zip");
        std::fs::write(&zip, package).map_err(cant)?;
        let unpacked = work.join("unpacked");
        let status = std::process::Command::new("/usr/bin/ditto")
            .args(["-x", "-k"])
            .arg(&zip)
            .arg(&unpacked)
            .status()
            .map_err(|e| format!("couldn't unpack the update: {e}"))?;
        if !status.success() {
            return Err("couldn't unpack the update (ditto failed)".to_string());
        }
        // LeapLoader-<version>-macos-<arch>/LeapLoader.app
        let new = std::fs::read_dir(&unpacked)
            .map_err(cant)?
            .flatten()
            .map(|e| e.path().join("LeapLoader.app"))
            .find(|p| p.join("Contents/MacOS/leaploader").is_file())
            .ok_or("the update holds no LeapLoader.app")?;
        let old = parent.join("LeapLoader.app.old");
        let _ = std::fs::remove_dir_all(&old);
        std::fs::rename(app, &old).map_err(cant)?;
        if let Err(e) = std::fs::rename(&new, app) {
            let _ = std::fs::rename(&old, app);
            return Err(cant(e));
        }
        Ok(())
    })();
    let _ = std::fs::remove_dir_all(&work);
    result
}

/// Starts the installed version (the caller then quits).
pub fn restart() -> std::io::Result<()> {
    match target() {
        // `-n`: a new instance, as this one is still running.
        Ok(Target::Bundle(app)) => std::process::Command::new("/usr/bin/open").arg("-n").arg(app).spawn().map(drop),
        Ok(Target::Folder { program, .. }) => std::process::Command::new(program).spawn().map(drop),
        Err(why) => Err(std::io::Error::other(format!("this copy of LeapLoader can't restart itself: {why}"))),
    }
}

/// Removes what the last update moved aside. The old version may still be
/// closing for a moment, so this keeps trying for a few seconds in the
/// background.
pub fn remove_leftovers() {
    let old = match target() {
        Ok(Target::Folder { dir, .. }) => dir.join(WORK),
        Ok(Target::Bundle(app)) => app.with_file_name("LeapLoader.app.old"),
        Err(why) => {
            crate::log::line(&format!("updates open the release page: {why}"));
            return;
        }
    };
    if !old.exists() {
        return;
    }
    let _ = std::thread::Builder::new().name("leaploader-cleanup".into()).spawn(move || {
        for _ in 0..40 {
            if std::fs::remove_dir_all(&old).is_ok() || !old.exists() {
                crate::log::line(&format!("removed the previous version ({})", old.display()));
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(250));
        }
    });
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use std::io::Write as _;

    /// A package zip: LeapLoader/<name> = contents.
    fn package(files: &[(&str, &[u8])]) -> Vec<u8> {
        let mut out = std::io::Cursor::new(Vec::new());
        let mut zip = zip::ZipWriter::new(&mut out);
        for (name, data) in files {
            zip.start_file(format!("LeapLoader/{name}"), zip::write::SimpleFileOptions::default()).unwrap();
            zip.write_all(data).unwrap();
        }
        zip.finish().unwrap();
        out.into_inner()
    }

    #[test]
    fn an_update_replaces_the_package_folder() {
        let dir = std::env::temp_dir().join(format!("leaploader-install-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("research")).unwrap();
        std::fs::write(dir.join("LeapLoader.exe"), b"old program").unwrap();
        std::fs::write(dir.join("research/mkcard.py"), b"old").unwrap();
        std::fs::write(dir.join("research/gone.py"), b"old only").unwrap();
        std::fs::write(dir.join("settings-the-user-made.txt"), b"keep").unwrap();
        let new = package(&[
            ("LeapLoader.exe", b"new program"),
            ("research/mkcard.py", b"new"),
            ("python/python.exe", b"py"),
        ]);
        replace_folder(&dir, &new).unwrap();
        assert_eq!(std::fs::read(dir.join("LeapLoader.exe")).unwrap(), b"new program");
        assert_eq!(std::fs::read(dir.join("research/mkcard.py")).unwrap(), b"new");
        assert!(!dir.join("research/gone.py").exists(), "the old research folder moved aside whole");
        assert_eq!(std::fs::read(dir.join("python/python.exe")).unwrap(), b"py");
        assert_eq!(std::fs::read(dir.join("settings-the-user-made.txt")).unwrap(), b"keep");
        assert_eq!(std::fs::read(dir.join(WORK).join("old/LeapLoader.exe")).unwrap(), b"old program");
        // A package without the program is refused, and nothing changes.
        assert!(replace_folder(&dir, &package(&[("readme.txt", b"x")])).is_err());
        assert_eq!(std::fs::read(dir.join("LeapLoader.exe")).unwrap(), b"new program");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
