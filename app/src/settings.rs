// SPDX-License-Identifier: GPL-3.0-or-later
//! User settings, kept in `settings.toml` in the app's data folder
//! (Windows: %APPDATA%\LeapLoader; elsewhere ~/.config/leaploader), the way
//! Ribbit keeps its own (crates/ribbit-frontend/src/settings.rs).

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// The menu the console's SD icon boots.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub enum Menu {
    /// LeapLoader's own menu (research/menugen.py), the recommended one.
    #[default]
    LeapLoader,
    /// LeapFrog's SD menu, from the user's .lfp package (or a bare SDMenu.bin).
    LeapFrog(PathBuf),
    /// LeapFrog's SD menu already in the output folder (a card that has it).
    LeapFrogOnCard,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    /// The dumps on the list, kept for next time.
    pub dumps: Vec<PathBuf>,
    /// Dumps on the list but not chosen for the card.
    pub unselected: Vec<PathBuf>,
    /// Incompatible dumps the user switched on anyway (they start off).
    pub try_anyway: Vec<PathBuf>,
    /// Where the last dumps were picked from (the file dialog starts there).
    pub dumps_folder: Option<PathBuf>,
    /// The folder the card is built into.
    pub output: Option<PathBuf>,
    pub menu: Menu,
    /// LeapLoader's `research` folder (mkcard.py); None: found next to the
    /// program (`card::research_dir`).
    pub research: Option<PathBuf>,
    /// The Python that runs mkcard.py: empty (or "python"/"python3") = the
    /// one the release brings, else the system's (`card::python`).
    pub python: String,
    /// nativescan, the converter's helper (the NATIVESCAN variable); None:
    /// `card::default_nativescan`.
    pub nativescan: Option<PathBuf>,
    /// The Leapster 2 BIOS 0.6 dump the menu music is rendered with; None:
    /// the one Ribbit uses (`card::find_bios`).
    pub bios: Option<PathBuf>,
    /// The build log panel is open.
    pub show_log: bool,
    /// The first-start note (made with AI, use at your own risk) was read.
    pub ai_notice_seen: bool,
    /// Look for a newer release at start-up (updates.rs).
    pub check_for_updates: bool,
    /// A release the user chose to skip: not announced at start-up again
    /// (Help → Check for updates still shows it).
    pub skipped_update: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            dumps: Vec::new(),
            unselected: Vec::new(),
            try_anyway: Vec::new(),
            dumps_folder: None,
            output: None,
            menu: Menu::default(),
            research: None,
            python: String::new(),
            nativescan: None,
            bios: None,
            show_log: true,
            ai_notice_seen: false,
            check_for_updates: true,
            skipped_update: String::new(),
        }
    }
}

impl Settings {
    pub fn load(path: &Path) -> Self {
        match std::fs::read_to_string(path) {
            Ok(text) => toml::from_str(&text).unwrap_or_else(|e| {
                // Kept aside, not written over (e.g. settings from a newer
                // LeapLoader read by an older one).
                eprintln!("ignoring unreadable {}: {e}", path.display());
                let _ = std::fs::rename(path, path.with_extension("toml.unreadable"));
                Self::default()
            }),
            Err(_) => Self::default(),
        }
    }

    pub fn save(&self, path: &Path) -> anyhow::Result<()> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let tmp = path.with_extension("tmp");
        std::fs::write(&tmp, toml::to_string_pretty(self)?)?;
        std::fs::rename(&tmp, path)?;
        Ok(())
    }
}

/// The app's data folder (settings), as Ribbit's `default_data_dir`.
pub fn default_data_dir() -> PathBuf {
    if let Some(appdata) = std::env::var_os("APPDATA") {
        return PathBuf::from(appdata).join("LeapLoader");
    }
    if let Some(xdg) = std::env::var_os("XDG_CONFIG_HOME") {
        return PathBuf::from(xdg).join("leaploader");
    }
    if let Some(home) = std::env::var_os("HOME") {
        return PathBuf::from(home).join(".config").join("leaploader");
    }
    PathBuf::from("leaploader-data")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settings_round_trip() {
        let s = Settings {
            dumps: vec!["a/b.bin".into()],
            output: Some("card".into()),
            menu: Menu::LeapFrog("x.lfp".into()),
            ..Default::default()
        };
        let text = toml::to_string_pretty(&s).unwrap();
        assert_eq!(toml::from_str::<Settings>(&text).unwrap(), s);
        // Missing fields take their defaults; old ones are ignored (the
        // card options of the first test builds).
        assert_eq!(toml::from_str::<Settings>("music_loop = 1.0").unwrap(), Settings::default());
    }
}
