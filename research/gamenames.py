"""Display names for Leapster cartridge dumps, by the CRC-32 of the whole dump file.

Dump file names are often short codes ("letrfactry.bin") and the cartridge's own title field
(0x1003/0x0B) is an internal name ("PUZ - Puzzle Power", "Diego_L2"), so known dumps get the name
printed on the box. ASCII only: the menu's pixel font has no accents.
"""
import re
import zlib

NAMES = {
    0xDB36283F: "1st Grade",
    0x597418D4: "2nd Grade",
    0xB0BA6D76: "Adibou: A la recherche de Robitoc",
    0xAF063BA4: "Animal Genius",
    0xDE5FB26E: "The Backyardigans",
    0x7C934681: "The Batman: Strength in Numbers",
    0xA0A362AA: "The Batman: Multiply, Divide and Conquer (German)",
    0x5D4F7CD0: "Bratz World",
    0xD4A7E5D4: "Cars",
    0x29AF42BA: "Cars 2",
    0x175D575F: "Cars: Supercharged",
    0x0134AF49: "Clifford the Big Red Dog: Reading",
    0x979346D5: "Cosmic Math",
    0xE4DB446F: "Crayola Art Adventure",
    0x9F08D02A: "Creature Create",
    0x822CA3DA: "Digging for Dinosaurs",
    0x8A605512: "Disney Fairies",
    0xD2F560C7: "Disney Fairies (Spanish)",
    0x5CCB2AD3: "Disney Princess: Enchanted Learning",
    0x2465F01D: "Disney Princess: Worlds of Enchantment",
    0x71778536: "Dora the Explorer: Camping Adventure",
    0xEA544030: "Dora the Explorer: Pinata Party",
    0x74AF5D57: "Dora the Explorer: Wildlife Rescue",
    0x1895F946: "Finding Nemo",
    0xE62D1684: "Foster's Home for Imaginary Friends",
    0x05B608F0: "Get Puzzled!",
    0xEBBF83A0: "Go, Diego, Go! Animal Rescuer",
    0xF1D6DB36: "The Incredibles",
    0xDA56181C: "I Spy Challenger",
    0x7C716016: "I Spy Treasure Hunt",
    0x78FCE75A: "Junie B. Jones: Top-Secret Personal Beeswax",
    0xDB262164: "Kindergarten",
    0x2C1FCF40: "Learning with Leap",
    0x9D1C2F35: "The Letter Factory",
    0x9B86A0FB: "Letterpillar",
    0xB186A3BF: "Letters on the Loose",
    0xA9C75D90: "Madagascar",
    0xFE8BD3FD: "Math Baseball",
    0xDBB767CC: "Mr. Pencil's Learn to Draw & Write",
    0x2FC77C9D: "My Amusement Park",
    0x95C78F34: "NASCAR",
    0x63C7DD95: "Ni Hao, Kai-lan: Beach Day",
    0x0F6D55CF: "Number Raiders",
    0x01F12CE7: "Numbers on the Run: Counting on Zero",
    0x24C28BCD: "Oui-Oui: Aventures au Pays des Jouets",
    0x9E69C26A: "Outwit!",
    0x076AD299: "The Penguins of Madagascar",
    0x3C428A13: "Pet Pals",
    0x0B83B8FA: "Phonics: Lesson One",
    0xD8AC1A09: "Pixar Pals",
    0xD0C4DE47: "Ratatouille",
    0x2C6E623E: "Reading with Phonics: Mole's Huge Nose",
    0x49AAB0FE: "Rock the World",
    0x7D7FC192: "Scholastic Math Missions",
    0xF3C31FAF: "Schoolhouse Rock! America Rock",
    0x53C9D9B2: "Schoolhouse Rock! Grammar Rock",
    0xC12B39A7: "Scooby-Doo! Arcade",
    0x19DA3DD8: "Scooby-Doo! Spooky Snacks",
    0x648E3EE5: "Scooby-Doo! Et les nombres fous !",
    0xA9D2CDBD: "Sonic X",
    0x0EF61CBB: "Spider-Man: The Case of the Sinister Speller",
    0x0F2AD725: "SpongeBob SquarePants: Saves the Day",
    0x6B24A3EF: "SpongeBob SquarePants: Through the Wormhole",
    0x27000674: "Star Wars: Jedi Math",
    0x6239A178: "Star Wars: Jedi Reading",
    0x9A3BED14: "Story Explorers",
    0x58D08F36: "The Talking Words Factory",
    0xCE9CE136: "Tangled",
    0x5303D366: "Thomas & Friends: Calling All Engines",
    0xA72C61FD: "Toy Story 3",
    0x1E2A5031: "Up",
    0xC71CFF35: "WALL-E",
    0x2C247582: "WALL-E (Prototype)",
    0x67BD4A6A: "Wolverine and the X-Men",
    0xF5A3052A: "Word Chasers",
}


def known_name(data):
    return NAMES.get(zlib.crc32(data))


def from_filename(filename):
    """A readable title from a dump's file name, or None for short codes ("2ndgrade.bin").
    "1st Grade (2003)(LeapFrog)(US).bin" -> "1st Grade";
    "Sonic-X_Leapster_EN.bin" -> "Sonic X"."""
    t = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    t = re.sub(r"\s*[\(\[].*$", "", t)
    t = re.sub(r"_Leapster(_[A-Z]{2})?$", "", t)
    if " " not in t:
        if "-" not in t and "_" not in t:
            return None
        t = t.replace("-39-s", "'s").replace("_", " ").replace("-", " ")
    return t.strip() or None
