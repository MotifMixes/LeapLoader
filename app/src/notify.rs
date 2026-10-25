// SPDX-License-Identifier: GPL-3.0-or-later
//! Telling the user a card is built while they look elsewhere: the taskbar
//! button flashes (winit's `request_user_attention`; the Dock icon bounces
//! on macOS) and a desktop notification shows. Windows: a notification from
//! a tray icon (Shell_NotifyIcon, shown as a toast on Windows 10 and 11),
//! removed again when the window closes; macOS: osascript's "display
//! notification"; Linux: notify-send, when it is installed.

use winit::window::{UserAttentionType, Window};

/// Flashes the taskbar button (until the window is brought forward) and
/// shows a notification.
pub fn finished(window: &Window, title: &str, body: &str) {
    window.request_user_attention(Some(UserAttentionType::Informational));
    show(window, title, body);
}

/// Takes LeapLoader's tray icon away (Windows; the notification's).
pub fn clear(window: &Window) {
    #[cfg(windows)]
    if let Some(hwnd) = hwnd(window) {
        use windows_sys::Win32::UI::Shell::{NIM_DELETE, NOTIFYICONDATAW, Shell_NotifyIconW};
        let mut data: NOTIFYICONDATAW = unsafe { std::mem::zeroed() };
        data.cbSize = std::mem::size_of::<NOTIFYICONDATAW>() as u32;
        data.hWnd = hwnd;
        data.uID = TRAY_ID;
        // SAFETY: a plain Win32 call with a filled-in struct that outlives it.
        unsafe { Shell_NotifyIconW(NIM_DELETE, &data) };
    }
    #[cfg(not(windows))]
    let _ = window;
}

#[cfg(windows)]
const TRAY_ID: u32 = 1;

#[cfg(windows)]
fn hwnd(window: &Window) -> Option<windows_sys::Win32::Foundation::HWND> {
    use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
    match window.window_handle().ok()?.as_raw() {
        RawWindowHandle::Win32(h) => Some(h.hwnd.get() as windows_sys::Win32::Foundation::HWND),
        _ => None,
    }
}

#[cfg(windows)]
fn show(window: &Window, title: &str, body: &str) {
    use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
    use windows_sys::Win32::UI::Shell::{
        NIF_ICON, NIF_INFO, NIF_TIP, NIIF_LARGE_ICON, NIIF_USER, NIM_ADD, NIM_MODIFY, NOTIFYICONDATAW,
        Shell_NotifyIconW,
    };
    use windows_sys::Win32::UI::WindowsAndMessaging::LoadIconW;
    let Some(hwnd) = hwnd(window) else { return };
    // UTF-16 into a fixed field, cut short to fit with its terminating 0.
    fn put(dst: &mut [u16], s: &str) {
        let room = dst.len() - 1;
        for (d, c) in dst.iter_mut().zip(s.encode_utf16().take(room)) {
            *d = c;
        }
    }
    let mut data: NOTIFYICONDATAW = unsafe { std::mem::zeroed() };
    data.cbSize = std::mem::size_of::<NOTIFYICONDATAW>() as u32;
    data.hWnd = hwnd;
    data.uID = TRAY_ID;
    data.uFlags = NIF_ICON | NIF_TIP | NIF_INFO;
    // SAFETY: plain Win32 calls; icon 1 is the .exe's own (build.rs).
    let icon = unsafe { LoadIconW(GetModuleHandleW(std::ptr::null()), 1 as _) };
    data.hIcon = icon;
    data.hBalloonIcon = icon;
    data.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON;
    put(&mut data.szTip, "LeapLoader");
    put(&mut data.szInfoTitle, title);
    put(&mut data.szInfo, body);
    // Added the first time, changed after (the icon stays until `clear`).
    // SAFETY: as above; `data` outlives the calls.
    unsafe {
        if Shell_NotifyIconW(NIM_MODIFY, &data) == 0 {
            Shell_NotifyIconW(NIM_ADD, &data);
        }
    }
}

#[cfg(target_os = "macos")]
fn show(_window: &Window, title: &str, body: &str) {
    let quote = |s: &str| s.replace('\\', "\\\\").replace('"', "\\\"");
    let script = format!("display notification \"{}\" with title \"{}\"", quote(body), quote(title));
    let _ = std::process::Command::new("osascript").args(["-e", &script]).spawn();
}

#[cfg(not(any(windows, target_os = "macos")))]
fn show(_window: &Window, title: &str, body: &str) {
    let _ = std::process::Command::new("notify-send").args(["--app-name=LeapLoader", title, body]).spawn();
}
