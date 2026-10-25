// SPDX-License-Identifier: GPL-3.0-or-later
//! The tags shown with a game in the list, as Ribbit's library shows them
//! (crates/ribbit-frontend/src/library.rs: `name_tags`, `is_prototype`,
//! `pretty_date`, `header_version`, `build_date`, copied and adapted): the
//! region, editions, "Prototype", the version and a prototype's build date,
//! from the dump's file name and the cartridge's header. Unlike Ribbit, every
//! bracket group in the name is read (so "Bratz World (500-11201-A, USA)"
//! gives "USA", and "Ni Hao Kai-lan - Beach Day (2009) (USA) (Leapster)"
//! gives "USA" and "2009"), years and the language of "_Leapster_EN" names
//! are tags too, and a prototype is a prototype even when gamenames.rs knows
//! the dump (its box name is kept; the tag says what the file is).

const REGIONS: &[&str] = &[
    "USA",
    "UK",
    "Europe",
    "France",
    "Germany",
    "Spain",
    "Canada",
    "Australia",
    "Netherlands",
    "Italy",
    "Mexico",
    "World",
    "Japan",
    "Korea",
    "Brazil",
];
const EDITIONS: &[&str] = &["L-MAX", "Leapster2", "Leapster 2", "POP LP7"];
const MONTH_NAMES: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/// The tags for a dump: `names` are its file names (a zip's own, then the
/// .bin in it), `image` the dump. In Ribbit's order: region, editions,
/// "Prototype", version, build date (then year and language, LeapLoader's).
pub fn tags_for(names: &[&str], image: &[u8]) -> Vec<String> {
    let mut region = None;
    let mut extras: Vec<String> = Vec::new();
    let mut prototype = false;
    let mut version = None;
    let mut date = None;
    let mut year = None;
    let mut language = None;
    for name in names {
        let stem = stem(name);
        prototype |= is_prototype(stem);
        language = language.or_else(|| leapster_language(stem));
        for group in bracket_groups(stem) {
            for piece in group.split(',').map(str::trim).filter(|p| !p.is_empty()) {
                let lower = piece.to_ascii_lowercase();
                let is_version = ["v", "alpha ", "beta ", "pre-alpha "].iter().any(|p| lower.starts_with(p))
                    && piece.chars().any(|c| c.is_ascii_digit());
                if piece.contains('-') && pretty_date(piece).is_some() {
                    date = date.or_else(|| pretty_date(piece));
                } else if is_version {
                    version = version.or_else(|| Some(piece.to_string()));
                } else if lower == "proto" || lower == "prototype" {
                    prototype = true;
                } else if let Some(e) = EDITIONS.iter().find(|e| e.eq_ignore_ascii_case(piece)) {
                    if !extras.iter().any(|x| x == e) {
                        extras.push(e.to_string());
                    }
                } else if let Some(r) = REGIONS.iter().find(|r| r.eq_ignore_ascii_case(piece)) {
                    region = region.or_else(|| Some(r.to_string()));
                } else if piece == "US" {
                    // ("1st Grade (2003)(LeapFrog)(US)": No-Intro's short form.)
                    region = region.or_else(|| Some("USA".to_string()));
                } else if piece.len() == 4
                    && piece.bytes().all(|b| b.is_ascii_digit())
                    && (1990..2040).contains(&piece.parse::<u32>().unwrap_or(0))
                {
                    year = year.or_else(|| Some(piece.to_string()));
                }
            }
        }
    }
    // The header's version when the name has none (Ribbit: field 0x07).
    let version = version.or_else(|| header_text(image, 0x07).as_deref().and_then(header_version));
    let mut tags: Vec<String> = region.into_iter().chain(extras).collect();
    if prototype {
        tags.push("Prototype".into());
    }
    tags.extend(version);
    // A prototype's build date tells one build from another: the header's,
    // else the file name's, else a compile stamp found in the program.
    if prototype
        && let Some(d) =
            header_text(image, 0x0F).as_deref().and_then(pretty_date).or(date.clone()).or_else(|| build_date(image))
    {
        tags.push(d);
    } else if let Some(y) = year {
        tags.push(y);
    }
    tags.extend(language);
    tags
}

/// The name without its extension ("x.bin" -> "x").
fn stem(name: &str) -> &str {
    let base = name.rsplit(['/', '\\']).next().unwrap_or(name);
    match base.rsplit_once('.') {
        Some((s, ext)) if !s.is_empty() && ext.len() <= 4 && ext.bytes().all(|b| b.is_ascii_alphanumeric()) => s,
        _ => base,
    }
}

/// Every "(...)" and "[...]" group's insides, left to right.
fn bracket_groups(name: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut rest = name;
    while let Some(open) = rest.find(['(', '[']) {
        let close = if rest.as_bytes()[open] == b'(' { ')' } else { ']' };
        let Some(len) = rest[open + 1..].find(close) else { break };
        out.push(&rest[open + 1..open + 1 + len]);
        rest = &rest[open + 1 + len + 1..];
    }
    out
}

/// "Sonic-X_Leapster_EN" -> "EN" (the downloads' naming).
fn leapster_language(stem: &str) -> Option<String> {
    let (head, code) = stem.rsplit_once('_')?;
    (head.ends_with("_Leapster") && code.len() == 2 && code.bytes().all(|b| b.is_ascii_uppercase()))
        .then(|| code.to_string())
}

/// A prototype or pre-release build, going by its name (Ribbit's: "Wall-E
/// December 20th 2007 prototype", "ROX Alpha 1.15", "1.8 Beta").
fn is_prototype(name: &str) -> bool {
    let name = name.to_ascii_lowercase();
    name.split(|c: char| !c.is_ascii_alphanumeric())
        .any(|w| matches!(w, "prototype" | "proto" | "beta" | "alpha" | "sample" | "submission" | "unreleased" | "j2s"))
}

/// A text field of the cartridge's header (resource 0x1003/`id`, as
/// mkcard.title_of reads 0x0B), or None.
pub fn header_text(image: &[u8], id: u16) -> Option<String> {
    let u16_at = |o: usize| image.get(o..o + 2).map(|b| u16::from_le_bytes([b[0], b[1]]));
    let u32_at = |o: usize| image.get(o..o + 4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]));
    let base = u32_at(0x11C)?;
    let leap = u32_at(0x140)?.checked_sub(base)? as usize;
    for i in 0..u16_at(leap + 6)? as usize {
        let e = leap + 0x20 + 8 * i;
        let (tag, cnt, ptr) = (u16_at(e)?, u16_at(e + 2)?, u32_at(e + 4)?);
        if tag != 0x1003 {
            continue;
        }
        for j in 0..cnt as usize {
            let r = ptr.checked_sub(base)? as usize + 8 * j;
            let (rid, v) = (u16_at(r)?, u32_at(r + 4)?);
            if rid == id && v >= base && ((v - base) as usize) < image.len() {
                let o = (v - base) as usize;
                let end = o + image[o..].iter().position(|&b| b == 0)?;
                // Latin-1: each byte is the character of that number.
                return Some(image[o..end].iter().map(|&b| b as char).collect());
            }
        }
    }
    None
}

/// "2008-04-23" (a file name's) or "Apr 23 2008 10:00:00" (a header's) as
/// "Apr 23, 2008" (Ribbit's).
fn pretty_date(s: &str) -> Option<String> {
    let s = s.trim();
    let num = |t: &str| t.parse::<u32>().ok();
    if let [y, m, d] = s.split('-').collect::<Vec<_>>()[..] {
        let (y, m, d) = (num(y)?, num(m)?, num(d)?);
        return (s.len() == 10 && y >= 1990 && (1..=12).contains(&m) && (1..=31).contains(&d))
            .then(|| format!("{} {d}, {y}", MONTH_NAMES[m as usize - 1]));
    }
    let mut w = s.split_whitespace();
    let (m, d, y) = (w.next()?, num(w.next()?)?, num(w.next()?)?);
    (MONTH_NAMES.contains(&m) && (1..=31).contains(&d) && y >= 1990).then(|| format!("{m} {d}, {y}"))
}

/// A header's version field ("v1.0", "A04, v1.0", "v 1.1", "1") as "v1.0";
/// None for anything else (Ribbit's).
fn header_version(s: &str) -> Option<String> {
    let s = s.trim().to_ascii_lowercase();
    let number = |t: &str| {
        let n: String = t.chars().take_while(|c| c.is_ascii_digit() || *c == '.').collect();
        let n = n.trim_end_matches('.').to_string();
        n.starts_with(|c: char| c.is_ascii_digit()).then_some(n)
    };
    let tidy = |n: String| if n.contains('.') { format!("v{n}") } else { format!("v{n}.0") };
    if !s.is_empty() && s.chars().all(|c| c.is_ascii_digit()) {
        return Some(tidy(s));
    }
    s.match_indices('v').find_map(|(i, _)| {
        let word_start = i == 0 || !s.as_bytes()[i - 1].is_ascii_alphabetic();
        word_start.then(|| number(s[i + 1..].trim_start())).flatten().map(tidy)
    })
}

/// The build date compiled into the program ("Dec 20 2007 16:28:29", C's
/// `__DATE__ __TIME__`) as "Dec 20, 2007"; the latest one when there are
/// several (Ribbit's).
fn build_date(rom: &[u8]) -> Option<String> {
    const MONTHS: [&[u8]; 12] =
        [b"Jan", b"Feb", b"Mar", b"Apr", b"May", b"Jun", b"Jul", b"Aug", b"Sep", b"Oct", b"Nov", b"Dec"];
    let digits = |b: &[u8]| b.iter().all(u8::is_ascii_digit);
    let mut best: Option<(u32, usize, u32)> = None;
    for w in rom.windows(20) {
        let Some(month) = MONTHS.iter().position(|m| w[..3] == **m) else { continue };
        let day = &w[4..6];
        let ok = w[3] == b' '
            && (day[0] == b' ' || day[0].is_ascii_digit())
            && day[1].is_ascii_digit()
            && w[6] == b' '
            && digits(&w[7..11])
            && w[11] == b' '
            && digits(&w[12..14])
            && w[14] == b':'
            && digits(&w[15..17])
            && w[17] == b':'
            && digits(&w[18..20]);
        if !ok {
            continue;
        }
        let year: u32 = std::str::from_utf8(&w[7..11]).ok()?.parse().ok()?;
        let day: u32 = std::str::from_utf8(day).ok()?.trim().parse().ok()?;
        if !(1990..2100).contains(&year) || !(1..=31).contains(&day) {
            continue;
        }
        let key = (year, month, day);
        if best.is_none_or(|b| key > b) {
            best = Some(key);
        }
    }
    best.map(|(y, m, d)| format!("{} {d}, {y}", std::str::from_utf8(MONTHS[m]).unwrap()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tags(name: &str) -> Vec<String> {
        tags_for(&[name], &[])
    }

    #[test]
    fn tags_from_file_names() {
        assert_eq!(tags("Wall-E (USA).bin"), ["USA"]);
        assert_eq!(tags("Bratz World (500-11201-A, USA).bin"), ["USA"]);
        assert_eq!(tags("Ni Hao Kai-lan - Beach Day (2009) (USA) (Leapster).bin"), ["USA", "2009"]);
        assert_eq!(tags("Wall-E December 20th 2007 prototype.bin"), ["Prototype"]);
        assert_eq!(tags("Sonic-X_Leapster_EN.bin"), ["EN"]);
        assert_eq!(tags("Rock the World - A Reading Adventure (500-11703-A, USA, L-MAX).bin"), ["USA", "L-MAX"]);
        assert_eq!(
            tags("Cars - Supercharged (USA) (Leapster2) (Proto) (Alpha 002) (2008-04-23).bin"),
            ["USA", "Leapster2", "Prototype", "Alpha 002", "Apr 23, 2008"]
        );
        assert_eq!(tags("NASCAR (USA) (L-MAX) (v1.0) (2006-02-24).bin"), ["USA", "L-MAX", "v1.0"]);
        assert_eq!(tags("Counting on Zero (prototype, repaired).bin"), ["Prototype"]);
        assert_eq!(tags("2ndgrade.bin"), Vec::<String>::new());
        assert_eq!(tags("1st Grade (2003)(LeapFrog)(US).bin"), ["USA", "2003"]);
        // A zip's own name, then the .bin in it.
        assert_eq!(tags_for(&["toystory3.zip", "Toy Story 3 (USA).bin"], &[]), ["USA"]);
    }

    #[test]
    fn versions_and_dates_normalised() {
        assert_eq!(header_version("A03, v1.0").as_deref(), Some("v1.0"));
        assert_eq!(header_version("v 1.1").as_deref(), Some("v1.1"));
        assert_eq!(pretty_date("2008-04-23").as_deref(), Some("Apr 23, 2008"));
        let mut rom = vec![0u8; 256];
        rom[10..30].copy_from_slice(b"Feb  9 2005 10:00:00");
        rom[100..120].copy_from_slice(b"Apr 29 2005 13:50:19");
        assert_eq!(build_date(&rom).as_deref(), Some("Apr 29, 2005"));
    }
}
