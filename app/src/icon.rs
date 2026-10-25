// SPDX-License-Identifier: GPL-3.0-or-later
//! The window and taskbar icon: LeapLoader's mark (frog_glyph.rs, shared
//! with the .exe icon and the window's header). Copied from Ribbit's
//! crates/ribbit-frontend/src/icon.rs.

#[path = "frog_glyph.rs"]
mod frog_glyph;
#[allow(unused_imports)]
pub use frog_glyph::*;

fn icon(size: u32) -> Option<winit::window::Icon> {
    winit::window::Icon::from_rgba(frog_glyph_rgba(size), size, size).ok()
}

/// Title-bar icon (Windows scales it down to 16-32 px).
pub fn window_icon() -> Option<winit::window::Icon> {
    icon(64)
}

/// Taskbar / Alt-Tab icon (Windows' "big" icon).
#[cfg_attr(not(windows), allow(dead_code))]
pub fn taskbar_icon() -> Option<winit::window::Icon> {
    icon(256)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frog_with_a_usb_stick_in_the_corner() {
        for size in [16u32, 64, 256] {
            let rgba = frog_glyph_rgba(size);
            assert_eq!(rgba.len(), (size * size * 4) as usize);
            assert_eq!(rgba[3], 0, "top left corner is transparent");
            let px = |x: f32, y: f32| {
                let i = ((y * size as f32) as usize * size as usize + (x * size as f32) as usize) * 4;
                [rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]]
            };
            if size >= 64 {
                assert_eq!(px(0.3, 0.8)[..3], FROG_GREEN, "the frog's face");
                assert_eq!(px(0.82, 0.92)[..3], STICK, "the stick's body");
                // The tip is above the body: the stick points up.
                let (body, tip, _) = stick_parts(size as f32);
                assert!(tip.3 <= body.1 && tip.1 < body.1);
            }
        }
        assert!(window_icon().is_some() && taskbar_icon().is_some());
    }
}
