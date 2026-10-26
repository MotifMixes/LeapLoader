// SPDX-License-Identifier: GPL-3.0-or-later
//! The games list: the user's cartridge dumps (.bin, or a .zip with a .bin
//! inside), each with the name the card will give it (gamenames.rs).

use std::io::Read;
use std::path::{Path, PathBuf};

/// The biggest dump read. Leapster cartridges are at most 16 MiB, but other
/// dumps (e.g. 66 MiB flash images) are listed too, as mkcard reads them
/// and says why it skips them.
const MAX_DUMP: u64 = 128 << 20;

/// What the last card build said about a game (mkcard's ok/skip lines).
#[derive(Debug, Clone, PartialEq)]
pub enum Outcome {
    /// Converted: mkcard's line after the file name ("-> Leapster/Apps/...").
    Ok(String),
    /// Left off the card, and why.
    Skip(String),
}

#[derive(Debug, Clone)]
pub struct Dump {
    pub path: PathBuf,
    /// The .bin inside a zip (None: the file is the dump).
    pub zip_entry: Option<String>,
    /// The name it gets on the card.
    pub name: String,
    /// Region, version, "Prototype"... from its file name and header, as
    /// Ribbit's library shows them (tags.rs).
    pub tags: Vec<String>,
    /// Size of the dump itself (inside the zip, for a zip).
    pub size: u64,
    pub crc: u32,
    pub outcome: Option<Outcome>,
    /// On the card (a click turns it on or off).
    pub enabled: bool,
    /// Selected in the list (Ctrl+click, Shift+click) for doing something
    /// to several games at once.
    pub picked: bool,
}

impl Dump {
    /// Reads the dump at `path` and names it.
    pub fn open(path: &Path) -> anyhow::Result<Self> {
        let (data, zip_entry) = read_dump(path)?;
        let crc = crc32fast::hash(&data);
        // mkcard names a dump from the file it is given: for a zip, the .bin
        // unpacked from it (`card::stage_zips` keeps the entry's name).
        let file_name = match &zip_entry {
            Some(e) => base_name(e).to_string(),
            None => path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
        };
        let own = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let names: Vec<&str> = if zip_entry.is_some() { vec![&own, &file_name] } else { vec![&file_name] };
        let tags = crate::tags::tags_for(&names, &data);
        Ok(Self {
            path: path.to_path_buf(),
            name: crate::gamenames::display_name(crc, &file_name, &data),
            tags,
            zip_entry,
            size: data.len() as u64,
            crc,
            outcome: None,
            enabled: false,
            picked: false,
        })
        .map(|mut d| {
            // A dump LeapLoader doesn't know starts off the card.
            d.enabled = d.tested();
            d
        })
    }

    /// Whether this is one of the dumps LeapLoader was tested with: every
    /// dump in gamenames.rs's table converts and runs from the SD card
    /// (VERIFIED-EMU in docs/HANDOFF.md: 77 of 77, in the Ribbit emulator).
    pub fn tested(&self) -> bool {
        crate::gamenames::known_name(self.crc).is_some()
    }

    /// The file name mkcard prints for this dump (its ok/skip lines).
    pub fn label(&self) -> String {
        match &self.zip_entry {
            Some(e) => base_name(e).to_string(),
            None => self.path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
        }
    }
}

/// The last part of a zip entry's name ("games/x.bin" -> "x.bin").
pub fn base_name(entry: &str) -> &str {
    entry.rsplit(['/', '\\']).next().unwrap_or(entry)
}

fn is_zip(path: &Path) -> bool {
    path.extension().is_some_and(|e| e.eq_ignore_ascii_case("zip"))
}

/// Whether `path` looks like a dump the list takes (by its extension).
pub fn is_dump_file(path: &Path) -> bool {
    path.extension().is_some_and(|e| e.eq_ignore_ascii_case("bin") || e.eq_ignore_ascii_case("zip"))
}

/// The dump's bytes, and for a zip the name of the .bin read from it (the
/// first one in the archive).
pub fn read_dump(path: &Path) -> anyhow::Result<(Vec<u8>, Option<String>)> {
    let file = std::fs::File::open(path)?;
    if !is_zip(path) {
        anyhow::ensure!(file.metadata()?.len() <= MAX_DUMP, "too big for a Leapster cartridge dump");
        let mut data = Vec::new();
        file.take(MAX_DUMP).read_to_end(&mut data)?;
        return Ok((data, None));
    }
    let mut zip = zip::ZipArchive::new(std::io::BufReader::new(file))?;
    let name = zip
        .file_names()
        .find(|n| n.to_ascii_lowercase().ends_with(".bin"))
        .map(str::to_string)
        .ok_or_else(|| anyhow::anyhow!("no .bin file in the zip"))?;
    let entry = zip.by_name(&name)?;
    anyhow::ensure!(entry.size() <= MAX_DUMP, "too big for a Leapster cartridge dump");
    let mut data = Vec::with_capacity(entry.size() as usize);
    entry.take(MAX_DUMP).read_to_end(&mut data)?;
    Ok((data, Some(name)))
}

/// The dumps in a folder (not its subfolders, as mkcard.py), by name.
pub fn dumps_in(folder: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(folder)
        .map(|d| d.flatten().map(|e| e.path()).filter(|p| p.is_file() && is_dump_file(p)).collect())
        .unwrap_or_default();
    found.sort();
    found
}

/// The Ribbit emulator's games folders, if Ribbit is installed: the
/// `rom_folders` in its settings.toml (Ribbit's settings.rs keeps it in
/// %APPDATA%\Ribbit, else ~/.config/ribbit). Only folders that are there.
pub fn ribbit_rom_folders() -> Vec<PathBuf> {
    let Some(table) = ribbit_settings() else {
        return Vec::new();
    };
    let folders = table.get("rom_folders").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    folders.iter().filter_map(|v| v.as_str()).map(PathBuf::from).filter(|p| p.is_dir()).collect()
}

/// The Leapster 2 BIOS picked in the Ribbit emulator, if it is there.
pub fn ribbit_leapster2_bios() -> Option<PathBuf> {
    let table = ribbit_settings()?;
    let picked = table.get("bios_picked")?.get("Leapster 2")?.as_str()?;
    Some(PathBuf::from(picked)).filter(|p| p.is_file())
}

/// The Ribbit emulator's settings.toml, if it has one.
fn ribbit_settings() -> Option<toml::Table> {
    let dir = if let Some(appdata) = std::env::var_os("APPDATA") {
        PathBuf::from(appdata).join("Ribbit")
    } else if let Some(xdg) = std::env::var_os("XDG_CONFIG_HOME") {
        PathBuf::from(xdg).join("ribbit")
    } else {
        PathBuf::from(std::env::var_os("HOME")?).join(".config").join("ribbit")
    };
    std::fs::read_to_string(dir.join("settings.toml")).ok()?.parse().ok()
}

/// About how much room the card takes with these games: each converted
/// game is about the size of its dump (a 77-game card: 649 MB of games for
/// 648 MB of dumps; a 3-game one 43.6 MiB for 40 MiB), so the dumps plus a
/// twentieth, plus each game's icon and meta.inf, plus the menu with its
/// music and welcome sound (about 0.7 MB). Rather over than under.
pub fn card_size_estimate<'a>(dumps: impl Iterator<Item = &'a Dump>) -> u64 {
    let (mut total, mut n) = (0u64, 0u64);
    for d in dumps {
        total += d.size;
        n += 1;
    }
    if n == 0 { 0 } else { total + total / 20 + n * (16 << 10) + (1 << 20) }
}

/// A click on dump `i` in the list. Alone it turns that game on or off
/// for the card (and clears the selection); with Ctrl (Cmd on macOS) it
/// selects or unselects it; with Shift it selects everything from `anchor`
/// (the last click without Shift) to it. Returns the new anchor.
pub fn click(dumps: &mut [Dump], anchor: Option<usize>, i: usize, ctrl: bool, shift: bool) -> Option<usize> {
    if i >= dumps.len() {
        return anchor;
    }
    if shift {
        let a = anchor.filter(|&a| a < dumps.len()).unwrap_or(i);
        for d in &mut dumps[a.min(i)..=a.max(i)] {
            d.picked = true;
        }
        return Some(a);
    }
    if ctrl {
        dumps[i].picked = !dumps[i].picked;
    } else {
        dumps[i].enabled = !dumps[i].enabled;
        for d in dumps.iter_mut() {
            d.picked = false;
        }
    }
    Some(i)
}

/// "8.0 MiB", "1.20 GiB"
pub fn size_text(bytes: u64) -> String {
    if bytes >= 1 << 30 {
        format!("{:.2} GiB", bytes as f64 / (1u64 << 30) as f64)
    } else if bytes >= 1 << 20 {
        format!("{:.1} MiB", bytes as f64 / (1 << 20) as f64)
    } else {
        format!("{} KiB", bytes.div_ceil(1024))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn list(n: usize) -> Vec<Dump> {
        (0..n)
            .map(|i| Dump {
                path: format!("{i}.bin").into(),
                zip_entry: None,
                name: i.to_string(),
                tags: Vec::new(),
                size: 1 << 20,
                crc: 0,
                outcome: None,
                enabled: true,
                picked: false,
            })
            .collect()
    }

    #[test]
    fn clicks_turn_games_on_and_off_and_select() {
        let mut d = list(6);
        let on =
            |d: &[Dump]| -> Vec<usize> { d.iter().enumerate().filter(|(_, d)| d.enabled).map(|(i, _)| i).collect() };
        let picked =
            |d: &[Dump]| -> Vec<usize> { d.iter().enumerate().filter(|(_, d)| d.picked).map(|(i, _)| i).collect() };
        let a = click(&mut d, None, 1, false, false);
        assert_eq!(on(&d), [0, 2, 3, 4, 5]);
        let a = click(&mut d, a, 3, true, false);
        let a = click(&mut d, a, 5, false, true);
        assert_eq!(picked(&d), [3, 4, 5]);
        let a = click(&mut d, a, 4, true, false);
        assert_eq!(picked(&d), [3, 5]);
        // A plain click clears the selection.
        click(&mut d, a, 0, false, false);
        assert!(picked(&d).is_empty());
        assert_eq!(on(&d), [2, 3, 4, 5]);
    }

    #[test]
    fn size_estimate() {
        let d = list(3);
        let dumps = 3 * (1 << 20);
        assert_eq!(card_size_estimate(d.iter()), dumps + dumps / 20 + 3 * (16 << 10) + (1 << 20));
        assert_eq!(card_size_estimate(d.iter().filter(|_| false)), 0);
        assert_eq!(size_text(3 << 30), "3.00 GiB");
    }
}
