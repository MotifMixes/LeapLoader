//! The emulators LeapLoader comes with, as homebrew packages (docs/homebrew.md):
//! NES (QuickNES, LGPL-2.1) and Game Boy / Color (gnuboy, GPL-2), built from
//! github.com/MotifMixes/LeapLoader-Emulators (its `package/` folders, copied to
//! assets/emulators). They are written to the app's data folder at every start
//! (so an update brings their new build) and put on the list once: taken off,
//! they stay off.

use std::path::{Path, PathBuf};

/// Each package: its id (the card folder `Leapster/Apps/<id>`) and its files.
const PACKAGES: &[(&str, &[(&str, &[u8])])] = &[
    (
        "NES",
        &[
            ("app.txt", include_bytes!("../assets/emulators/NES/app.txt")),
            ("code.bin", include_bytes!("../assets/emulators/NES/code.bin")),
            ("LICENSE.txt", include_bytes!("../assets/emulators/NES/LICENSE.txt")),
            ("card/NES/Put NES games here.txt", include_bytes!("../assets/emulators/NES/card/NES/Put NES games here.txt")),
        ],
    ),
    (
        "GB",
        &[
            ("app.txt", include_bytes!("../assets/emulators/GB/app.txt")),
            ("code.bin", include_bytes!("../assets/emulators/GB/code.bin")),
            ("LICENSE.txt", include_bytes!("../assets/emulators/GB/LICENSE.txt")),
            ("card/GB/Put GB games here.txt", include_bytes!("../assets/emulators/GB/card/GB/Put GB games here.txt")),
            ("card/GBC/Put GBC games here.txt", include_bytes!("../assets/emulators/GB/card/GBC/Put GBC games here.txt")),
        ],
    ),
];

/// Writes the packages under `data_dir/emulators` (only files that differ) and
/// returns each one's id and folder; a package that could not be written is left out.
pub fn install(data_dir: &Path) -> Vec<(&'static str, PathBuf)> {
    let mut out = Vec::new();
    for (id, files) in PACKAGES {
        let dir = data_dir.join("emulators").join(id);
        let written = files.iter().all(|(rel, data)| {
            let path = dir.join(rel);
            if std::fs::read(&path).ok().as_deref() == Some(*data) {
                return true;
            }
            let made = path.parent().map_or(Ok(()), std::fs::create_dir_all).and_then(|_| std::fs::write(&path, data));
            if let Err(e) = &made {
                eprintln!("could not write {}: {e}", path.display());
            }
            made.is_ok()
        });
        if written {
            out.push((*id, dir));
        }
    }
    out
}
