// SPDX-License-Identifier: GPL-3.0-or-later
//! Display names for Leapster cartridge dumps: a port of LeapLoader's
//! research/gamenames.py (the CRC-32 of the whole dump file -> the name on
//! the box, else a name made from the file name) and of mkcard.py's
//! `title_of` (the cartridge's own title field), so the app shows the name
//! the card will use. Keep the table in step with gamenames.py: the test
//! below checks the names of the dumps it was made from.

/// CRC-32 of the dump -> the name printed on the box. ASCII only: the
/// menu's pixel font has no accents. (Generated from gamenames.NAMES.)
const NAMES: &[(u32, &str)] = &[
    (0xDB36283F, "1st Grade"),
    (0x597418D4, "2nd Grade"),
    (0xB0BA6D76, "Adibou: A la recherche de Robitoc"),
    (0xAF063BA4, "Animal Genius"),
    (0xDE5FB26E, "The Backyardigans"),
    (0x7C934681, "The Batman: Strength in Numbers"),
    (0xA0A362AA, "The Batman: Multiply, Divide and Conquer (German)"),
    (0x5D4F7CD0, "Bratz World"),
    (0xD4A7E5D4, "Cars"),
    (0x29AF42BA, "Cars 2"),
    (0x175D575F, "Cars: Supercharged"),
    (0x0134AF49, "Clifford the Big Red Dog: Reading"),
    (0x979346D5, "Cosmic Math"),
    (0xE4DB446F, "Crayola Art Adventure"),
    (0x9F08D02A, "Creature Create"),
    (0x822CA3DA, "Digging for Dinosaurs"),
    (0x8A605512, "Disney Fairies"),
    (0xD2F560C7, "Disney Fairies (Spanish)"),
    (0x5CCB2AD3, "Disney Princess: Enchanted Learning"),
    (0x2465F01D, "Disney Princess: Worlds of Enchantment"),
    (0x71778536, "Dora the Explorer: Camping Adventure"),
    (0xEA544030, "Dora the Explorer: Pinata Party"),
    (0x74AF5D57, "Dora the Explorer: Wildlife Rescue"),
    (0x1895F946, "Finding Nemo"),
    (0xE62D1684, "Foster's Home for Imaginary Friends"),
    (0x05B608F0, "Get Puzzled!"),
    (0xEBBF83A0, "Go, Diego, Go! Animal Rescuer"),
    (0xF1D6DB36, "The Incredibles"),
    (0xDA56181C, "I Spy Challenger"),
    (0x7C716016, "I Spy Treasure Hunt"),
    (0x78FCE75A, "Junie B. Jones: Top-Secret Personal Beeswax"),
    (0xDB262164, "Kindergarten"),
    (0x2C1FCF40, "Learning with Leap"),
    (0x9D1C2F35, "The Letter Factory"),
    (0x9B86A0FB, "Letterpillar"),
    (0xB186A3BF, "Letters on the Loose"),
    (0xA9C75D90, "Madagascar"),
    (0xFE8BD3FD, "Math Baseball"),
    (0xDBB767CC, "Mr. Pencil's Learn to Draw & Write"),
    (0x2FC77C9D, "My Amusement Park"),
    (0x95C78F34, "NASCAR"),
    (0x63C7DD95, "Ni Hao, Kai-lan: Beach Day"),
    (0x0F6D55CF, "Number Raiders"),
    (0x01F12CE7, "Numbers on the Run: Counting on Zero"),
    (0x24C28BCD, "Oui-Oui: Aventures au Pays des Jouets"),
    (0x9E69C26A, "Outwit!"),
    (0x076AD299, "The Penguins of Madagascar"),
    (0x3C428A13, "Pet Pals"),
    (0x0B83B8FA, "Phonics: Lesson One"),
    (0xD8AC1A09, "Pixar Pals"),
    (0xD0C4DE47, "Ratatouille"),
    (0x2C6E623E, "Reading with Phonics: Mole's Huge Nose"),
    (0x49AAB0FE, "Rock the World"),
    (0x7D7FC192, "Scholastic Math Missions"),
    (0xF3C31FAF, "Schoolhouse Rock! America Rock"),
    (0x53C9D9B2, "Schoolhouse Rock! Grammar Rock"),
    (0xC12B39A7, "Scooby-Doo! Arcade"),
    (0x19DA3DD8, "Scooby-Doo! Spooky Snacks"),
    (0x648E3EE5, "Scooby-Doo! Et les nombres fous !"),
    (0xA9D2CDBD, "Sonic X"),
    (0x0EF61CBB, "Spider-Man: The Case of the Sinister Speller"),
    (0x0F2AD725, "SpongeBob SquarePants: Saves the Day"),
    (0x6B24A3EF, "SpongeBob SquarePants: Through the Wormhole"),
    (0x27000674, "Star Wars: Jedi Math"),
    (0x6239A178, "Star Wars: Jedi Reading"),
    (0x9A3BED14, "Story Explorers"),
    (0x58D08F36, "The Talking Words Factory"),
    (0xCE9CE136, "Tangled"),
    (0x5303D366, "Thomas & Friends: Calling All Engines"),
    (0xA72C61FD, "Toy Story 3"),
    (0x1E2A5031, "Up"),
    (0xC71CFF35, "WALL-E"),
    (0x2C247582, "WALL-E (Prototype)"),
    (0x67BD4A6A, "Wolverine and the X-Men"),
    (0xF5A3052A, "Word Chasers"),
];

/// The box name of a known dump (`crc`: CRC-32 of the whole dump file, as
/// Python's zlib.crc32).
pub fn known_name(crc: u32) -> Option<&'static str> {
    NAMES.iter().find(|(c, _)| *c == crc).map(|(_, n)| *n)
}

/// The name mkcard.py gives a dump: the box name, else one from the file
/// name, else the cartridge's title, else "Game".
pub fn display_name(crc: u32, filename: &str, image: &[u8]) -> String {
    known_name(crc)
        .map(str::to_string)
        .or_else(|| from_filename(filename))
        .or_else(|| title_of(image))
        .unwrap_or_else(|| "Game".into())
}

/// Python's str.isspace (and `\s` in its regular expressions): Unicode
/// White_Space plus the four ASCII separators 0x1C..0x1F.
fn py_space(c: char) -> bool {
    c.is_whitespace() || ('\x1C'..='\x1F').contains(&c)
}

/// A readable title from a dump's file name, or None for short codes
/// ("2ndgrade.bin"), step for step as gamenames.from_filename:
/// "1st Grade (2003)(LeapFrog)(US).bin" -> "1st Grade";
/// "Sonic-X_Leapster_EN.bin" -> "Sonic X".
/// (Not ported: Python's `$` also matching before a final newline, for file
/// names that end in one.)
pub fn from_filename(filename: &str) -> Option<String> {
    // re.sub(r"\.[A-Za-z0-9]+$", "", t): the last dot and the letters and
    // digits after it, when nothing else follows.
    let mut t = filename.to_string();
    if let Some(dot) = t.rfind('.') {
        let ext = &t[dot + 1..];
        if !ext.is_empty() && ext.bytes().all(|b| b.is_ascii_alphanumeric()) {
            t.truncate(dot);
        }
    }
    // re.sub(r"\s*[\(\[].*$", "", t): from the first bracket (and the
    // spaces before it) to the end.
    if let Some(open) = t.find(['(', '[']) {
        let start = t[..open].trim_end_matches(py_space).len();
        t.truncate(start);
    }
    // re.sub(r"_Leapster(_[A-Z]{2})?$", "", t)
    if let Some(s) = t.strip_suffix("_Leapster") {
        t = s.to_string();
    } else if let [.., b'_', a, b] = *t.as_bytes()
        && a.is_ascii_uppercase()
        && b.is_ascii_uppercase()
        && let Some(s) = t[..t.len() - 3].strip_suffix("_Leapster")
    {
        t = s.to_string();
    }
    if !t.contains(' ') {
        if !t.contains('-') && !t.contains('_') {
            return None;
        }
        t = t.replace("-39-s", "'s").replace('_', " ").replace('-', " ");
    }
    let t = t.trim_matches(py_space);
    (!t.is_empty()).then(|| t.to_string())
}

/// The cartridge's title (resource 0x1003/0x0B), or None (mkcard.title_of;
/// where Python would raise on a damaged image, None).
pub fn title_of(image: &[u8]) -> Option<String> {
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
            if rid == 0x0B && v >= base && ((v - base) as usize) < image.len() {
                let o = (v - base) as usize;
                let end = o + image[o..].iter().position(|&b| b == 0)?;
                // Latin-1: each byte is the character of that number.
                return Some(image[o..end].iter().map(|&b| b as char).collect());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_from_file_names() {
        assert_eq!(from_filename("1st Grade (2003)(LeapFrog)(US).bin").as_deref(), Some("1st Grade"));
        assert_eq!(from_filename("Sonic-X_Leapster_EN.bin").as_deref(), Some("Sonic X"));
        assert_eq!(from_filename("2ndgrade.bin"), None);
        assert_eq!(from_filename("letrfactry.bin"), None);
        assert_eq!(
            from_filename("Foster-39-s-Home-for-Imaginary-Friends_Leapster_EN.bin").as_deref(),
            Some("Foster's Home for Imaginary Friends")
        );
        assert_eq!(
            from_filename("Batman, The - Strength in Numbers (USA).bin").as_deref(),
            Some("Batman, The - Strength in Numbers")
        );
        assert_eq!(from_filename("Word Chasers 500-12353-A.bin").as_deref(), Some("Word Chasers 500-12353-A"));
        // (One word left: a short code to gamenames.py too.)
        assert_eq!(from_filename("Outwit_Leapster.bin"), None);
        assert_eq!(from_filename("Outwit_Leapster_EN.bin"), None);
        assert_eq!(from_filename("Cars_Leapster_us.bin").as_deref(), Some("Cars Leapster us"));
        assert_eq!(from_filename("(USA).bin"), None);
        assert_eq!(from_filename("a.b-c"), Some("a.b c".into()));
    }

    #[test]
    fn known_dumps() {
        assert_eq!(known_name(0x9D1C2F35), Some("The Letter Factory"));
        assert_eq!(known_name(0x9A3BED14), Some("Story Explorers"));
        assert_eq!(NAMES.len(), 75);
    }
}
