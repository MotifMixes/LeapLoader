// SPDX-License-Identifier: GPL-3.0-or-later
// LeapLoader's mark: Ribbit's frog (the frog-face emoji from Noto Emoji,
// SIL Open Font License, shipped with egui, drawn in Ribbit green the way
// Ribbit's crates/ribbit-frontend/src/frog_glyph.rs does) with a small USB
// stick over its bottom right corner, pointing up. Shared by the window's
// header (ui.rs), the window and taskbar icons (icon.rs) and the .exe icon,
// which build.rs makes by `include!`ing this file.

/// Ribbit green (the frog).
#[allow(dead_code)]
pub const FROG_GREEN: [u8; 3] = [0x3D, 0xC2, 0x5C];
/// The stick's body and its lighter half (no outline: the user's choice).
#[allow(dead_code)]
pub const STICK: [u8; 3] = [0x5A, 0x4C, 0xB4];
#[allow(dead_code)]
pub const STICK_LIGHT: [u8; 3] = [0x8C, 0x7C, 0xE6];
/// The plug's metal tip, and the holes in it.
#[allow(dead_code)]
pub const TIP_GREY: [u8; 3] = [0xE6, 0xE6, 0xEA];
#[allow(dead_code)]
pub const HOLE_GREY: [u8; 3] = [0x50, 0x50, 0x58];

/// The frog-face glyph's coverage of an `n` by `n` image, filling it.
fn frog_cover(n: usize) -> Vec<f32> {
    use ab_glyph::{Font, FontRef, point};
    let font = FontRef::try_from_slice(epaint_default_fonts::NOTO_EMOJI_REGULAR).expect("the emoji font");
    let id = font.glyph_id('\u{1F438}');
    let unit = font.outline_glyph(id.with_scale(100.0)).expect("a frog in the emoji font").px_bounds();
    let side = n as f32;
    let margin = (side * 0.04).max(1.0);
    let scale = 100.0 * (side - 2.0 * margin) / unit.width().max(unit.height());
    let glyph = font.outline_glyph(id.with_scale_and_position(scale, point(0.0, 0.0))).expect("frog outline");
    let b = glyph.px_bounds();
    let (dx, dy) = (((side - b.width()) / 2.0).round() as i32, ((side - b.height()) / 2.0).round() as i32);
    let mut cover = vec![0f32; n * n];
    glyph.draw(|x, y, c| {
        let (x, y) = (x as i32 + dx, y as i32 + dy);
        if (0..n as i32).contains(&x) && (0..n as i32).contains(&y) {
            cover[y as usize * n + x as usize] = c;
        }
    });
    cover
}

/// The USB stick's parts in an image `side` pixels square (left, top,
/// right, bottom): the body, the metal tip above it, the tip's two holes.
#[allow(dead_code)]
pub fn stick_parts(side: f32) -> ((f32, f32, f32, f32), (f32, f32, f32, f32), [(f32, f32, f32, f32); 2]) {
    let (l, r) = (side * 0.70, side * 0.94);
    let body = (l, side * 0.66, r, side * 0.97);
    let inset = (r - l) * 0.16;
    let tip = (l + inset, side * 0.47, r - inset, side * 0.66);
    let (hw, hh) = ((r - l) * 0.16, (tip.3 - tip.1) * 0.22);
    let hy = tip.1 + (tip.3 - tip.1) * 0.38;
    let hole = |cx: f32| (cx - hw / 2.0, hy - hh / 2.0, cx + hw / 2.0, hy + hh / 2.0);
    let w = tip.2 - tip.0;
    (body, tip, [hole(tip.0 + w * 0.3), hole(tip.0 + w * 0.7)])
}

/// The mark: the frog with the stick over its bottom right corner, `size`
/// pixels square, transparent around.
pub fn frog_glyph_rgba(size: u32) -> Vec<u8> {
    let n = size as usize;
    let side = size as f32;
    let frog = frog_cover(n);
    let (body, tip, holes) = stick_parts(side);
    let radius = (body.2 - body.0) * 0.18;
    let inside = |r: (f32, f32, f32, f32), x: f32, y: f32| x >= r.0 && x < r.2 && y >= r.1 && y < r.3;
    // The body with rounded corners.
    let in_body = |r: (f32, f32, f32, f32), rad: f32, x: f32, y: f32| {
        if !inside(r, x, y) {
            return false;
        }
        let cx = x.clamp(r.0 + rad, r.2 - rad);
        let cy = y.clamp(r.1 + rad, r.3 - rad);
        (x - cx).powi(2) + (y - cy).powi(2) <= rad * rad
    };
    let light = (body.0, body.1, body.2, body.1 + (body.3 - body.1) * 0.45);
    let mut out = Vec::with_capacity(n * n * 4);
    for py in 0..n {
        for px in 0..n {
            // Each layer's coverage of this pixel (4 x 4 samples), painted
            // back to front over the frog: the tip, its holes, the body, the
            // body's lighter top.
            let mut layers = [0f32; 4];
            for sy in 0..4 {
                for sx in 0..4 {
                    let (x, y) = (px as f32 + (sx as f32 + 0.5) / 4.0, py as f32 + (sy as f32 + 0.5) / 4.0);
                    let hits = [
                        inside(tip, x, y),
                        holes.iter().any(|&h| inside(h, x, y)),
                        in_body(body, radius, x, y),
                        in_body(body, radius, x, y) && inside(light, x, y),
                    ];
                    for (l, hit) in layers.iter_mut().zip(hits) {
                        if hit {
                            *l += 1.0 / 16.0;
                        }
                    }
                }
            }
            // Premultiplied colour and alpha, painted with "over".
            let (mut rgb, mut a) = ([0f32; 3], 0f32);
            let mut over = |c: [u8; 3], cover: f32| {
                for (v, &ch) in rgb.iter_mut().zip(&c) {
                    *v = *v * (1.0 - cover) + ch as f32 * cover;
                }
                a = a * (1.0 - cover) + cover;
            };
            over(FROG_GREEN, frog[py * n + px].clamp(0.0, 1.0));
            for (c, cover) in [TIP_GREY, HOLE_GREY, STICK, STICK_LIGHT].into_iter().zip(layers) {
                over(c, cover);
            }
            let un = |v: f32| if a > 0.0 { (v / a).round().clamp(0.0, 255.0) as u8 } else { 0 };
            out.extend_from_slice(&[un(rgb[0]), un(rgb[1]), un(rgb[2]), (a * 255.0).round() as u8]);
        }
    }
    out
}
