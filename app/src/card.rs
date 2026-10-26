// SPDX-License-Identifier: GPL-3.0-or-later
//! Building a card. For now the app runs LeapLoader's research pipeline,
//! `python -I research/mkcard.py [options] OUT_DIR DUMPS...`, as a child
//! process, and shows what it prints. mkcard writes only into OUT_DIR, the
//! folder the user chose; the app never touches a drive itself.

use crate::settings::{Menu, Settings};
use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// Zipped dumps are unpacked here, inside the output folder, for mkcard
/// (which reads .bin files), with the menu's music and welcome sound beside
/// them; the folder is
/// removed after the build.
const STAGING: &str = ".leaploader-unzipped";

/// The research folder: the setting, else the first `research` folder with
/// mkcard.py beside the program or above it (a release would ship it next
/// to the program), else the one in the source tree this app was built from.
pub fn research_dir(settings: &Settings) -> Option<PathBuf> {
    if let Some(r) = &settings.research {
        return Some(r.clone());
    }
    let has_mkcard = |d: &Path| d.join("mkcard.py").is_file();
    let exe = std::env::current_exe().ok();
    let from_exe = exe.iter().flat_map(|e| e.ancestors().skip(1)).map(|d| d.join("research"));
    let from_cwd = std::env::current_dir().ok().into_iter().flat_map(|d| {
        let v: Vec<PathBuf> = d.ancestors().map(|a| a.join("research")).collect();
        v
    });
    // (A build-tree fallback: the target folder is often elsewhere, e.g. on
    // another drive, so the program's folder alone may not lead there. Left
    // out of release packages, scripts/package-release.py: it would put the
    // build machine's folder in the program.)
    #[cfg(not(leaploader_release))]
    let from_source = Path::new(env!("CARGO_MANIFEST_DIR")).parent().map(|p| p.join("research"));
    #[cfg(leaploader_release)]
    let from_source: Option<PathBuf> = None;
    from_exe.chain(from_cwd).chain(from_source).find(|d| has_mkcard(d))
}

/// nativescan for the NATIVESCAN variable: the setting, else the one
/// beside the program, if it is there (None: mkcard looks in its own folder;
/// a development build gets a copy beside it, docs/HANDOFF.md).
pub fn default_nativescan(settings: &Settings) -> Option<PathBuf> {
    let beside_exe = || std::env::current_exe().ok().and_then(|e| Some(e.parent()?.join(NATIVESCAN_EXE)));
    settings.nativescan.clone().or_else(|| beside_exe().filter(|p| p.is_file()))
}

/// nativescan's file name (a release ships it beside the program).
const NATIVESCAN_EXE: &str = if cfg!(windows) { "nativescan.exe" } else { "nativescan" };

/// The ARC binutils the save stubs are assembled with (the ARC_GNU
/// variable): the `arc-gnu` folder a release ships beside the program
/// (None: the scripts' default, Ribbit's tools/arc-gnu).
pub fn bundled_arc_gnu() -> Option<PathBuf> {
    let dir = std::env::current_exe().ok()?.parent()?.join("arc-gnu");
    let assembler = if cfg!(windows) { "arc-elf32-as.exe" } else { "arc-elf32-as" };
    dir.join(assembler).is_file().then_some(dir)
}

/// The Python that runs mkcard: the one a release package brings (python/
/// beside the program, with numpy and scipy: players install nothing),
/// unless Settings names another; else the system's `python`/`python3`.
pub fn python(settings: &Settings) -> PathBuf {
    let chosen = settings.python.trim();
    let default = chosen.is_empty() || chosen == "python" || chosen == "python3";
    let bundled = std::env::current_exe().ok().and_then(|e| {
        let dir = e.parent()?.join("python");
        Some(if cfg!(windows) { dir.join("python.exe") } else { dir.join("bin").join("python3") })
    });
    match bundled.filter(|p| default && p.is_file()) {
        Some(p) => p,
        None if chosen.is_empty() => PathBuf::from(if cfg!(windows) { "python" } else { "python3" }),
        None => PathBuf::from(chosen),
    }
}

/// The Leapster 2 BIOS the menu music is rendered with: the setting, else
/// the one picked in Ribbit (None: mkcard's default, else no music).
pub fn find_bios(settings: &Settings) -> Option<PathBuf> {
    settings.bios.clone().or_else(crate::games::ribbit_leapster2_bios)
}

/// Where the card keeps the menu the SD icon boots.
const MENU_ON_CARD: &str = "Leapster/System/SDMenu/SDMenu.bin";

/// LeapFrog's SD menu in `out` (an SD card, or a card built before), if
/// it holds one: LeapLoader's own menu names itself ("LeapLoader" in its
/// text), LeapFrog's doesn't.
pub fn leapfrog_menu_in(out: &Path) -> Option<PathBuf> {
    let path = out.join(MENU_ON_CARD);
    let data = std::fs::read(&path).ok()?;
    let ours = data.windows(10).any(|w| w == b"LeapLoader");
    (!ours && !data.is_empty()).then_some(path)
}

/// LeapLoader's menu music, baked into the app: the user's song (a MIDI
/// file whose track names are BIOS program numbers, rendered by mkcard with
/// the BIOS's instruments), and where it starts again after its end.
const MENU_MUSIC: &[u8] = include_bytes!("../assets/menumusic.mid");
const MENU_MUSIC_LOOP: &str = "20.21";
/// The song's parts the console's own sequencer plays (user's choice): the
/// drums, flute (73) and bass (38); the rest is the rendered clip (the guitar
/// on it took voices from the bass, which then dropped to the clip).
const MENU_MUSIC_CONSOLE: &str = "drums,73,38";
/// Parts whose notes play their sample once, without its loop (the guitar,
/// 31: its short loop sounded like a stuck repeat when notes were held).
const MENU_MUSIC_SHORT: &str = "31";
/// The bass (38) plays its soft notes at velocity 96, its level elsewhere
/// (it was too quiet from ~0:40 to 0:50).
const MENU_MUSIC_FLOOR: &str = "38:96";
/// The sound LeapLoader's menu plays when it starts ("Welcome to LeapLoader.
/// Select a game."), baked in too: LeapLoader's assets/welcome.alaw (welcome.mp3
/// already as the menu plays it, so the build needs no ffmpeg).
const WELCOME: &[u8] = include_bytes!("../../assets/welcome.alaw");

/// mkcard.py's arguments after the script: options, OUT_DIR, the dumps.
/// `sounds`: the menu music's and the welcome sound's files (LeapLoader's
/// menu only).
pub fn mkcard_args(
    menu: &Menu,
    sounds: Option<(&Path, &Path)>,
    bios: Option<&Path>,
    out: &Path,
    dumps: &[PathBuf],
) -> Vec<OsString> {
    let mut args: Vec<OsString> = Vec::new();
    match menu {
        Menu::LeapFrog(lfp) => args.extend(["--menu".into(), lfp.into()]),
        // (mkcard reads the menu before it writes it back.)
        Menu::LeapFrogOnCard => args.extend(["--menu".into(), out.join(MENU_ON_CARD).into()]),
        Menu::LeapLoader => {
            if let Some((music, welcome)) = sounds {
                args.extend(["--music".into(), music.into(), "--music-loop".into(), MENU_MUSIC_LOOP.into()]);
                args.extend(["--console".into(), MENU_MUSIC_CONSOLE.into(), "--short".into(), MENU_MUSIC_SHORT.into()]);
                args.extend(["--floor".into(), MENU_MUSIC_FLOOR.into()]);
                args.extend(["--welcome".into(), welcome.into()]);
                if let Some(bios) = bios {
                    args.extend(["--bios".into(), bios.into()]);
                }
            }
        }
    }
    args.push(out.into());
    args.extend(dumps.iter().map(OsString::from));
    args
}

/// What a running build sends the window.
#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    /// A line mkcard printed (stdout or stderr).
    Line(String),
    /// Finished: whether mkcard succeeded, and a word on how it ended.
    Done(bool, String),
}

/// A card being built.
pub struct Build {
    pub events: Receiver<Event>,
    child: Arc<Mutex<Child>>,
}

impl Build {
    /// Starts mkcard on `dumps` (each with its zip entry, if zipped) into `out`.
    /// `wake` is called whenever an event is sent (the window redraws).
    pub fn start(
        settings: &Settings,
        out: &Path,
        dumps: &[(PathBuf, Option<String>)],
        wake: impl Fn() + Send + Sync + 'static,
    ) -> anyhow::Result<Self> {
        let research = research_dir(settings).ok_or_else(|| {
            anyhow::anyhow!("LeapLoader's research folder (with mkcard.py) was not found: choose it in Settings")
        })?;
        anyhow::ensure!(research.join("mkcard.py").is_file(), "no mkcard.py in {}", research.display());
        anyhow::ensure!(out.is_dir(), "the output folder {} is not there", out.display());
        if settings.menu == Menu::LeapFrogOnCard {
            anyhow::ensure!(
                leapfrog_menu_in(out).is_some(),
                "LeapFrog's SD menu isn't in {} any more: import your .lfp package, or choose LeapLoader's menu",
                out.display()
            );
        }
        let staging = out.join(STAGING);
        let paths = stage_zips(dumps, &staging)?;
        let music = staging.join("menumusic.mid");
        std::fs::create_dir_all(&staging)?;
        std::fs::write(&music, MENU_MUSIC)?;
        let welcome = staging.join("welcome.alaw");
        std::fs::write(&welcome, WELCOME)?;
        let python = python(settings);
        let mut cmd = Command::new(&python);
        // -I: none of the user's Python settings or packages folder; -u: lines
        // as they come; -X utf8: text in UTF-8 whatever the console's code page.
        cmd.args(["-I", "-u", "-X", "utf8"]).arg(research.join("mkcard.py"));
        let bios = find_bios(settings);
        cmd.args(mkcard_args(&settings.menu, Some((&music, &welcome)), bios.as_deref(), out, &paths));
        cmd.current_dir(research.parent().unwrap_or(&research));
        if let Some(ns) = default_nativescan(settings) {
            cmd.env("NATIVESCAN", ns);
        }
        if let Some(arc) = bundled_arc_gnu() {
            cmd.env("ARC_GNU", arc);
        }
        cmd.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
        // No console window for the child (the app itself has none).
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt as _;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                let _ = std::fs::remove_dir_all(&staging);
                anyhow::bail!("could not start {}: {e}", python.display());
            }
        };
        let (tx, events) = channel();
        let wake = Arc::new(wake);
        let _ = tx.send(Event::Line(format!("$ {}", describe(&cmd))));
        let readers = [
            child.stdout.take().map(|s| reader(s, tx.clone(), wake.clone())),
            child.stderr.take().map(|s| reader(s, tx.clone(), wake.clone())),
        ];
        let child = Arc::new(Mutex::new(child));
        {
            let child = child.clone();
            std::thread::spawn(move || {
                let status = loop {
                    match child.lock().unwrap().try_wait() {
                        Ok(Some(s)) => break Ok(s),
                        Ok(None) => {}
                        Err(e) => break Err(e),
                    }
                    std::thread::sleep(Duration::from_millis(100));
                };
                // Every line before the end.
                for r in readers.into_iter().flatten() {
                    let _ = r.join();
                }
                let _ = std::fs::remove_dir_all(&staging);
                let done = match status {
                    Ok(s) if s.success() => Event::Done(true, "finished".into()),
                    Ok(s) => Event::Done(false, format!("stopped ({s})")),
                    Err(e) => Event::Done(false, format!("lost track of mkcard: {e}")),
                };
                let _ = tx.send(done);
                wake();
            });
        }
        Ok(Self { events, child })
    }

    /// Stops mkcard (its files so far stay in the output folder).
    pub fn stop(&self) {
        let _ = self.child.lock().unwrap().kill();
    }
}

fn reader(
    stream: impl std::io::Read + Send + 'static,
    tx: Sender<Event>,
    wake: Arc<impl Fn() + Send + Sync + 'static>,
) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let mut r = BufReader::new(stream);
        let mut line = Vec::new();
        while r.read_until(b'\n', &mut line).is_ok_and(|n| n > 0) {
            let text = String::from_utf8_lossy(&line).trim_end().to_string();
            line.clear();
            if tx.send(Event::Line(text)).is_err() {
                break;
            }
            wake();
        }
    })
}

/// The command line, for the log.
fn describe(cmd: &Command) -> String {
    let quote = |s: &std::ffi::OsStr| {
        let s = s.to_string_lossy();
        if s.contains(' ') { format!("\"{s}\"") } else { s.into_owned() }
    };
    std::iter::once(quote(cmd.get_program())).chain(cmd.get_args().map(quote)).collect::<Vec<_>>().join(" ")
}

/// The paths to give mkcard: plain dumps as they are, zipped ones unpacked
/// into `staging` under their entry's own name (mkcard names folders from
/// it), each in a numbered folder of its own so equal names don't collide.
fn stage_zips(dumps: &[(PathBuf, Option<String>)], staging: &Path) -> anyhow::Result<Vec<PathBuf>> {
    let mut paths = Vec::new();
    for (i, (path, entry)) in dumps.iter().enumerate() {
        let Some(entry) = entry else {
            paths.push(path.clone());
            continue;
        };
        let (data, _) = crate::games::read_dump(path)?;
        let dir = staging.join(i.to_string());
        std::fs::create_dir_all(&dir)?;
        let file = dir.join(crate::games::base_name(entry));
        std::fs::write(&file, data)?;
        paths.push(file);
    }
    Ok(paths)
}

/// An ok/skip line: the file name it is about, and the outcome.
pub fn parse_outcome(line: &str) -> Option<(&str, crate::games::Outcome)> {
    use crate::games::Outcome;
    if let Some(rest) = line.strip_prefix("ok    ") {
        let (label, what) = rest.split_once(" -> ")?;
        return Some((label, Outcome::Ok(what.to_string())));
    }
    if let Some(rest) = line.strip_prefix("skip  ") {
        // "skip  NAME: reason"; a file name may hold ": " too, so the
        // caller matches the labels it knows (`outcome_for`).
        return Some((rest, Outcome::Skip(String::new())));
    }
    None
}

/// Matches an ok/skip line to one of `labels` (the dumps' file names, as
/// mkcard prints them): the index and outcome.
pub fn outcome_for(line: &str, labels: &[String], taken: &[bool]) -> Option<(usize, crate::games::Outcome)> {
    use crate::games::Outcome;
    let (rest, outcome) = parse_outcome(line)?;
    let free = |i: &usize| !taken[*i];
    match outcome {
        Outcome::Ok(what) => {
            let i = (0..labels.len()).filter(free).find(|&i| labels[i] == rest)?;
            Some((i, Outcome::Ok(what)))
        }
        Outcome::Skip(_) => {
            let i = (0..labels.len())
                .filter(free)
                .find(|&i| rest.strip_prefix(labels[i].as_str()).is_some_and(|r| r.starts_with(": ")))?;
            Some((i, Outcome::Skip(rest[labels[i].len() + 2..].to_string())))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::games::Outcome;

    #[test]
    fn options_then_out_dir_then_dumps() {
        let sounds = Some((Path::new("m.mid"), Path::new("w.mp3")));
        let args =
            mkcard_args(&Menu::LeapLoader, sounds, Some(Path::new("b.bin")), Path::new("out"), &["a.bin".into()]);
        let args: Vec<_> = args.iter().map(|a| a.to_string_lossy().into_owned()).collect();
        assert_eq!(
            args,
            [
                "--music",
                "m.mid",
                "--music-loop",
                "20.21",
                "--console",
                "drums,73,38",
                "--short",
                "31",
                "--floor",
                "38:96",
                "--welcome",
                "w.mp3",
                "--bios",
                "b.bin",
                "out",
                "a.bin"
            ]
        );
        // LeapFrog's menu has no music or welcome sound.
        let args =
            mkcard_args(&Menu::LeapFrog("x.lfp".into()), sounds, Some(Path::new("b.bin")), Path::new("out"), &[]);
        assert_eq!(args, [OsString::from("--menu"), "x.lfp".into(), "out".into()]);
    }

    #[test]
    fn ok_and_skip_lines() {
        let labels = vec!["a: b.bin".to_string(), "c.bin".to_string(), "c.bin".to_string()];
        let mut taken = vec![false; 3];
        let (i, o) = outcome_for("ok    c.bin -> Leapster/Apps/C (Cee)", &labels, &taken).unwrap();
        assert_eq!((i, o), (1, Outcome::Ok("Leapster/Apps/C (Cee)".into())));
        taken[1] = true;
        assert_eq!(outcome_for("ok    c.bin -> Leapster/Apps/C2 (Cee)", &labels, &taken).unwrap().0, 2);
        let (i, o) = outcome_for("skip  a: b.bin: native code", &labels, &taken).unwrap();
        assert_eq!((i, o), (0, Outcome::Skip("native code".into())));
        assert!(outcome_for("menu  LeapLoader menu", &labels, &taken).is_none());
    }
}
