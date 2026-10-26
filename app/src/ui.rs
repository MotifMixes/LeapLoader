// SPDX-License-Identifier: GPL-3.0-or-later
//! The window's contents (egui), in Ribbit's look: its fonts, green accent,
//! dark cards and gradient backdrop (crates/ribbit-frontend/src/ui.rs). The
//! UI only reads state and emits `Action`s; `app.rs` performs them.

use crate::files::Pick;
use crate::games::{Dump, Outcome};
use crate::settings::{Menu, Settings};
use std::path::PathBuf;

/// The Leapster 2 steps that change something, each asked first.
#[derive(Debug, Clone, PartialEq)]
pub enum UsbStep {
    /// Send "mount" (C2) to the console's SD card disk.
    Open(crate::usb::Disk),
    /// Build the card into the SD card's drive.
    BuildOnto(PathBuf),
    /// Close the drive and send "eject" (C6).
    Eject(crate::usb::Disk),
}

/// What can be done to the selected games at once.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Bulk {
    TurnOn,
    TurnOff,
    Remove,
    /// Unselect them.
    Clear,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    Pick(Pick),
    /// Add every dump in the Ribbit emulator's games folders.
    AddRibbitGames,
    /// Look for a Leapster 2 on USB (reading only).
    FindLeapster,
    /// Ask before a USB step (opening the SD card, building onto it, ejecting).
    AskUsb(UsbStep),
    /// Do the USB step (asked and answered yes).
    DoUsb(UsbStep),
    CopyUsbLog,
    SaveUsbLog,
    RemoveDump(usize),
    /// A click on a game in the list (choosing the games for the card).
    Click {
        index: usize,
        ctrl: bool,
        shift: bool,
    },
    /// Choose every game (true) or none.
    SelectAll(bool),
    /// Do something to the games selected in the list.
    Selected(Bulk),
    /// Select every game in the list (Ctrl+A).
    PickAll,
    ClearDumps,
    /// Build the card (asks first when the output folder holds other files).
    Build,
    /// Build even though the output folder holds other files.
    BuildAnyway,
    StopBuild,
    OpenFolder(PathBuf),
    SettingsChanged,
}

/// What the window shows that lives elsewhere (app.rs).
pub struct Info<'a> {
    pub dumps: &'a [Dump],
    pub building: bool,
    /// The last build: whether it succeeded, and how it ended.
    pub last_build: Option<&'a (bool, String)>,
    pub research: Option<PathBuf>,
    pub nativescan: Option<PathBuf>,
    /// The Leapster 2 BIOS for the menu music (None: no music).
    pub bios: Option<PathBuf>,
    /// LeapFrog's SD menu found in the output folder.
    pub menu_on_card: Option<&'a std::path::Path>,
    /// The Ribbit emulator's games folders (empty: Ribbit isn't installed).
    pub ribbit_folders: &'a [PathBuf],
    /// The last look for a Leapster 2 on USB (None: not looked yet).
    pub usb: Option<&'a crate::usb::Scan>,
    /// A USB step running now (what it is doing).
    pub usb_busy: Option<&'a str>,
    /// The drive a card was last built onto (eject it next).
    pub usb_built: Option<&'a std::path::Path>,
}

#[derive(Default)]
pub struct UiState {
    /// mkcard's output, newest last.
    pub log: Vec<String>,
    pub show_settings: bool,
    pub show_about: bool,
    /// Asking before building into a folder with other files in it.
    pub confirm_output: Option<PathBuf>,
    /// Asking before a USB step.
    pub confirm_usb: Option<UsbStep>,
    /// A problem to show: title, explanation.
    pub problem: Option<(String, String)>,
    /// A message in the status bar.
    pub message: Option<String>,
}

impl UiState {
    pub fn problem(&mut self, title: impl Into<String>, explain: impl Into<String>) {
        self.problem = Some((title.into(), explain.into()));
    }
}

/// Ribbit's green (the frog), for the main buttons and highlights.
const ACCENT: egui::Color32 = egui::Color32::from_rgb(46, 170, 82);
const ACCENT_HOVER: egui::Color32 = egui::Color32::from_rgb(64, 196, 104);
const SKIP_RED: egui::Color32 = egui::Color32::from_rgb(235, 90, 90);
/// An incompatible game switched on anyway ("May be skipped").
const TRY_AMBER: egui::Color32 = egui::Color32::from_rgb(240, 180, 60);
/// The Leapster 2's purple, for LeapLoader's mark (`brand`) and headings
/// (lighter shades to read on the dark backdrop).
const PURPLE: egui::Color32 = egui::Color32::from_rgb(112, 96, 196);
const PURPLE_LIGHT: egui::Color32 = egui::Color32::from_rgb(160, 144, 240);
/// Ribbit's dark card colour (its dialogs and notes).
const CARD: egui::Color32 = egui::Color32::from_rgb(22, 26, 24);

pub fn draw(ui: &mut egui::Ui, st: &mut UiState, settings: &mut Settings, info: &Info, actions: &mut Vec<Action>) {
    let ctx = ui.ctx().clone();
    egui::Panel::top("menu").show(ui, |ui| menu_bar(ui, st, settings, info, actions));
    egui::Panel::bottom("status").show(ui, |ui| status_bar(ui, st, info));
    // The card's panel the window's full height (the log only under the
    // games), scrolling when the window is short.
    egui::Panel::right("card")
        .resizable(false)
        .exact_size(360.0)
        .frame(egui::Frame::new().fill(egui::Color32::from_gray(22)).inner_margin(egui::Margin::symmetric(18, 16)))
        .show(ui, |ui| {
            // A floating scroll bar: hidden until the mouse is over the panel
            // or it scrolls (the user's choice; the wheel works either way).
            ui.style_mut().spacing.scroll.floating = true;
            egui::ScrollArea::vertical()
                .auto_shrink([false, false])
                .scroll_bar_visibility(egui::scroll_area::ScrollBarVisibility::VisibleWhenNeeded)
                .show(ui, |ui| card_panel(ui, settings, info, actions));
        });
    if settings.show_log {
        egui::Panel::bottom("log")
            .resizable(true)
            .default_size(150.0)
            .min_size(80.0)
            .frame(egui::Frame::new().fill(egui::Color32::from_gray(14)).inner_margin(egui::Margin::symmetric(12, 8)))
            .show(ui, |ui| log_panel(ui, st));
    }
    egui::CentralPanel::default().frame(egui::Frame::NONE).show(ui, |ui| {
        backdrop(ui);
        egui::Frame::NONE.inner_margin(egui::Margin { left: 28, right: 12, top: 20, bottom: 12 }).show(ui, |ui| {
            games_screen(ui, info, actions);
        });
    });
    dialogs(&ctx, st, settings, info, actions);
}

fn menu_bar(ui: &mut egui::Ui, st: &mut UiState, settings: &mut Settings, info: &Info, actions: &mut Vec<Action>) {
    egui::MenuBar::new().ui(ui, |ui| {
        ui.menu_button("File", |ui| {
            if ui.button("Add roms…").clicked() {
                actions.push(Action::Pick(Pick::Dumps));
                ui.close();
            }
            if ui.button("Add a folder of dumps…").clicked() {
                actions.push(Action::Pick(Pick::DumpFolder));
                ui.close();
            }
            if ui.add_enabled(!info.dumps.is_empty() && !info.building, egui::Button::new("Clear the list")).clicked() {
                actions.push(Action::ClearDumps);
                ui.close();
            }
            ui.separator();
            if ui.button("Settings…").clicked() {
                st.show_settings = true;
                ui.close();
            }
        });
        ui.menu_button("View", |ui| {
            if ui.checkbox(&mut settings.show_log, "Build log").changed() {
                actions.push(Action::SettingsChanged);
            }
        });
        ui.menu_button("Help", |ui| {
            if ui.button("About LeapLoader").clicked() {
                st.show_about = true;
                ui.close();
            }
        });
    });
}

fn status_bar(ui: &mut egui::Ui, st: &UiState, info: &Info) {
    ui.horizontal(|ui| {
        if let Some(m) = &st.message {
            ui.label(egui::RichText::new(m).color(ACCENT).strong());
        } else {
            let n = info.dumps.len();
            ui.label(match n {
                0 => "No games yet".to_string(),
                1 => "1 game".to_string(),
                _ => format!("{n} games"),
            });
        }
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if info.building {
                let done = info.dumps.iter().filter(|d| d.outcome.is_some()).count();
                let on_card = info.dumps.iter().filter(|d| d.enabled).count();
                ui.label(format!("Building… {done} of {on_card}"));
                ui.spinner();
            } else if let Some((ok, how)) = info.last_build {
                let text = egui::RichText::new(format!("Last build {how}"));
                ui.label(if *ok { text.color(ACCENT) } else { text.color(SKIP_RED) });
            }
        });
    });
}

fn log_panel(ui: &mut egui::Ui, st: &UiState) {
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("BUILD LOG").size(12.5).color(egui::Color32::from_gray(140)).strong());
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.small_button("Copy").on_hover_text("Copy the log").clicked() {
                ui.ctx().copy_text(st.log.join("\n"));
            }
        });
    });
    ui.add_space(4.0);
    egui::ScrollArea::vertical().auto_shrink([false, false]).stick_to_bottom(true).show(ui, |ui| {
        if st.log.is_empty() {
            ui.label(egui::RichText::new("What mkcard says while it builds a card shows here.").weak());
        }
        for line in &st.log {
            let color = if line.starts_with("ok ") {
                egui::Color32::from_rgb(120, 210, 140)
            } else if line.starts_with("skip ") || line.starts_with("Traceback") || line.contains("Error") {
                SKIP_RED
            } else {
                egui::Color32::from_gray(200)
            };
            ui.add(egui::Label::new(egui::RichText::new(line).monospace().size(12.5).color(color)).wrap());
        }
    });
}

/// Ribbit's library backdrop: a dark green fading to near black.
fn backdrop(ui: &egui::Ui) {
    let r = ui.max_rect();
    let top = egui::Color32::from_rgb(18, 46, 30);
    let bottom = egui::Color32::from_rgb(11, 12, 14);
    let mid = egui::pos2(r.max.x, r.min.y + r.height() * 0.55);
    let mut mesh = egui::Mesh::default();
    mesh.colored_vertex(r.left_top(), top);
    mesh.colored_vertex(r.right_top(), top);
    mesh.colored_vertex(egui::pos2(r.min.x, mid.y), bottom);
    mesh.colored_vertex(mid, bottom);
    mesh.colored_vertex(r.left_bottom(), bottom);
    mesh.colored_vertex(r.right_bottom(), bottom);
    mesh.add_triangle(0, 1, 2);
    mesh.add_triangle(1, 3, 2);
    mesh.add_triangle(2, 3, 4);
    mesh.add_triangle(3, 5, 4);
    ui.painter().add(mesh);
}

/// The frog, as a texture kept in egui's memory.
fn frog(ui: &egui::Ui) -> egui::TextureHandle {
    let id = egui::Id::new("frog icon");
    ui.ctx().data_mut(|d| d.get_temp::<egui::TextureHandle>(id)).unwrap_or_else(|| {
        let img = egui::ColorImage::from_rgba_unmultiplied([256, 256], &crate::icon::frog_glyph_rgba(256));
        let tex = ui.ctx().load_texture("frog icon", img, egui::TextureOptions::LINEAR);
        ui.ctx().data_mut(|d| d.insert_temp(id, tex.clone()));
        tex
    })
}

/// LeapLoader's mark in the header: the icon's own picture (Ribbit's frog
/// with a USB stick in its corner, frog_glyph.rs), `height` points square.
fn brand(ui: &mut egui::Ui, height: f32) {
    ui.add(egui::Image::new((frog(ui).id(), egui::vec2(height, height))));
}

/// The games list: a header with LeapLoader's mark and the add buttons
/// (laid out as Ribbit's library header), then a row for each dump.
fn games_screen(ui: &mut egui::Ui, info: &Info, actions: &mut Vec<Action>) {
    ui.horizontal(|ui| {
        brand(ui, 64.0);
        // Ribbit's folder right beside the mark, in purple; Add roms and Add
        // a folder on the right.
        if !info.ribbit_folders.is_empty() {
            ui.add_space(10.0);
            ui.add_enabled_ui(!info.building, |ui| {
                let ribbit =
                    colored_button(ui, "🐸  Import Ribbit's Rom Folder", egui::vec2(0.0, 32.0), PURPLE, PURPLE_LIGHT);
                if ribbit.on_hover_text(ribbit_hover(info.ribbit_folders)).clicked() {
                    actions.push(Action::AddRibbitGames);
                }
            });
        }
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            ui.spacing_mut().item_spacing.x = 8.0;
            ui.add_space(8.0);
            ui.add_enabled_ui(!info.building, |ui| {
                let folder = egui::Button::new("📁  Add a folder…").corner_radius(8).min_size(egui::vec2(0.0, 32.0));
                if ui.add(folder).on_hover_text("Every .bin and .zip in a folder").clicked() {
                    actions.push(Action::Pick(Pick::DumpFolder));
                }
                if primary_button(ui, "+  Add roms…", egui::vec2(0.0, 32.0)).clicked() {
                    actions.push(Action::Pick(Pick::Dumps));
                }
            });
        });
    });
    ui.add_space(10.0);
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("Games").size(26.0).family(crate::fonts::title()).color(egui::Color32::WHITE));
        if !info.dumps.is_empty() {
            // The count is of the compatible games; the others have a count
            // of their own, in red.
            // On the card: the compatible games switched on, and any
            // incompatible one switched on anyway (the card panel counts the same).
            let compatible = info.dumps.iter().filter(|d| d.tested()).count();
            let forced = info.dumps.iter().filter(|d| d.enabled && !d.tested()).count();
            let chosen = info.dumps.iter().filter(|d| d.enabled).count();
            badge(ui, &format!("{chosen} of {} on the card", compatible + forced));
            let incompatible = info.dumps.len() - compatible;
            if incompatible > 0 {
                egui::Frame::NONE
                    .fill(SKIP_RED.gamma_multiply(0.2))
                    .stroke(egui::Stroke::new(1.0, SKIP_RED.gamma_multiply(0.6)))
                    .corner_radius(6)
                    .inner_margin(egui::Margin::symmetric(7, 2))
                    .show(ui, |ui| {
                        ui.label(
                            egui::RichText::new(format!("{incompatible} incompatible")).size(11.5).color(SKIP_RED),
                        );
                    })
                    .response
                    .on_hover_text("Dumps LeapLoader doesn't know: not counted with the games above");
            }
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.add_space(8.0);
                ui.add_enabled_ui(!info.building, |ui| {
                    let picked = info.dumps.iter().filter(|d| d.picked).count();
                    if picked > 0 {
                        selection_bar(ui, picked, actions);
                    } else {
                        if ui.small_button("Disable all").on_hover_text("Take every game off the card").clicked() {
                            actions.push(Action::SelectAll(false));
                        }
                        if ui.small_button("Enable all").on_hover_text("Put every game on the card").clicked() {
                            actions.push(Action::SelectAll(true));
                        }
                    }
                });
            });
        }
    });
    ui.add_space(8.0);
    if info.dumps.is_empty() {
        empty_list(ui, info, actions);
        return;
    }
    // Keys for the selection, unless a text box has them: Ctrl+A (Cmd+A on
    // macOS) selects every game, Delete removes the selected ones from the
    // list, Escape unselects them.
    let ctx = ui.ctx().clone();
    if !info.building && !ctx.egui_wants_keyboard_input() {
        if ctx.input_mut(|i| i.consume_key(egui::Modifiers::COMMAND, egui::Key::A)) {
            actions.push(Action::PickAll);
        }
        if info.dumps.iter().any(|d| d.picked) {
            if ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Delete)) {
                actions.push(Action::Selected(Bulk::Remove));
            }
            if ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape)) {
                actions.push(Action::Selected(Bulk::Clear));
            }
        }
    }
    ui.style_mut().spacing.scroll.floating = false;
    egui::ScrollArea::vertical()
        .auto_shrink([false, false])
        .scroll_bar_visibility(egui::scroll_area::ScrollBarVisibility::AlwaysVisible)
        .show(ui, |ui| {
            ui.spacing_mut().item_spacing.y = 8.0;
            for (i, dump) in info.dumps.iter().enumerate() {
                game_row(ui, i, dump, info.building, actions);
            }
            ui.add_space(8.0);
        });
}

/// What to do to the selected games: shown in place of All on / All off
/// while some are selected (right to left).
fn selection_bar(ui: &mut egui::Ui, picked: usize, actions: &mut Vec<Action>) {
    if ui.small_button("×").on_hover_text("Unselect (Esc)").clicked() {
        actions.push(Action::Selected(Bulk::Clear));
    }
    if ui.small_button("Remove").on_hover_text("Take them off the list (Delete)").clicked() {
        actions.push(Action::Selected(Bulk::Remove));
    }
    if ui.small_button("Disable").on_hover_text("Take them off the card").clicked() {
        actions.push(Action::Selected(Bulk::TurnOff));
    }
    if ui.small_button("Enable").on_hover_text("Put them on the card").clicked() {
        actions.push(Action::Selected(Bulk::TurnOn));
    }
    let text = if picked == 1 { "1 selected".to_string() } else { format!("{picked} selected") };
    ui.label(egui::RichText::new(text).color(PURPLE_LIGHT).strong());
}

fn game_row(ui: &mut egui::Ui, i: usize, dump: &Dump, building: bool, actions: &mut Vec<Action>) {
    // Green for a dump known to work (or just converted); red for one the
    // last build left off, or one LeapLoader doesn't know.
    let (state, color, hover) = match &dump.outcome {
        Some(Outcome::Ok(what)) => (Mark::Ok, ACCENT, format!("On the card: {what}")),
        Some(Outcome::Skip(why)) => (Mark::Skip, SKIP_RED, format!("Left off the card: {why}")),
        None if dump.tested() => (
            Mark::Ok,
            ACCENT,
            "Compatible: this dump converts and runs from the SD card (tested in the Ribbit emulator)".to_string(),
        ),
        None => (
            Mark::Skip,
            SKIP_RED,
            "Incompatible: not one of the Leapster games LeapLoader works with (an unknown or damaged dump, or \
             another console's)"
                .to_string(),
        ),
    };
    let edge = color.gamma_multiply(0.55);
    let fill = CARD.lerp_to_gamma(color, 0.07);
    // Selected (Ctrl+click, Shift+click): a purple edge and tint.
    let (edge, edge_w, fill) =
        if dump.picked { (PURPLE_LIGHT, 2.0, fill.lerp_to_gamma(PURPLE, 0.22)) } else { (edge, 1.0, fill) };
    // The whole row takes clicks (its buttons first).
    let row = ui.scope_builder(egui::UiBuilder::new().sense(egui::Sense::click()), |ui| {
        // A game not on the card is greyed out (less when selected, so its
        // purple edge shows).
        if !dump.enabled {
            ui.multiply_opacity(if dump.picked { 0.65 } else { 0.35 });
        }
        egui::Frame::new()
            .fill(fill)
            .stroke(egui::Stroke::new(edge_w, edge))
            .corner_radius(10)
            .inner_margin(egui::Margin::symmetric(14, 10))
            .show(ui, |ui| {
                ui.set_width(ui.available_width());
                ui.horizontal(|ui| {
                    mark(ui, state, color).on_hover_text(&hover);
                    ui.add_space(4.0);
                    // The name and path get what the badge and × leave, cut
                    // short with "…" when long (they ran under the badge).
                    let spacing = ui.spacing().item_spacing.x;
                    let left = (ui.available_width() - BADGE_W - REMOVE_W - 3.0 * spacing).max(40.0);
                    ui.allocate_ui_with_layout(
                        egui::vec2(left, ROW_LINES),
                        egui::Layout::top_down(egui::Align::Min),
                        |ui| {
                            ui.set_width(left);
                            ui.spacing_mut().item_spacing.y = 2.0;
                            let name_color = if state == Mark::Ok {
                                egui::Color32::from_rgb(150, 235, 165)
                            } else {
                                egui::Color32::WHITE
                            };
                            // The name, then its tags on the same line (as Ribbit's
                            // library); the name is what shortens when they don't fit.
                            ui.horizontal(|ui| {
                                let tags_w: f32 = dump.tags.iter().map(|t| badge_width(ui, t) + 8.0).sum();
                                let name_w = (ui.available_width() - tags_w).max(60.0);
                                ui.scope(|ui| {
                                    ui.set_max_width(name_w);
                                    ui.add(
                                        egui::Label::new(egui::RichText::new(&dump.name).size(17.0).color(name_color))
                                            .truncate(),
                                    );
                                });
                                for t in &dump.tags {
                                    badge(ui, t);
                                }
                            });
                            let mut where_ = dump.path.display().to_string();
                            if let Some(e) = &dump.zip_entry {
                                where_ = format!("{where_}  ›  {e}");
                            }
                            ui.horizontal(|ui| {
                                badge(ui, &crate::games::size_text(dump.size));
                                ui.add(
                                    egui::Label::new(
                                        egui::RichText::new(where_).size(13.0).color(egui::Color32::from_gray(150)),
                                    )
                                    .truncate(),
                                )
                                .on_hover_text(format!("CRC-32 {:08X}", dump.crc));
                            });
                        },
                    );
                    let (word, color) = match (&dump.outcome, dump.tested(), dump.enabled) {
                        (Some(Outcome::Ok(_)), ..) => ("On the card", color),
                        (Some(Outcome::Skip(_)), ..) => ("Skipped", color),
                        (None, true, _) => ("Compatible", color),
                        // Switched on anyway: it goes to mkcard, which may skip it.
                        (None, false, true) => ("May be skipped", TRY_AMBER),
                        (None, false, false) => ("Incompatible", color),
                    };
                    let hover = if word == "May be skipped" {
                        "Switched on anyway: LeapLoader will try it, but it may be skipped when the card is built"
                            .to_string()
                    } else {
                        hover
                    };
                    outcome_badge(ui, word, color).on_hover_text(&hover);
                    if remove_button(ui, !building).on_hover_text("Take it off the list").clicked() {
                        actions.push(Action::RemoveDump(i));
                    }
                });
            });
    });
    if row.response.clicked() && !building {
        let m = ui.input(|i| i.modifiers);
        actions.push(Action::Click { index: i, ctrl: m.command, shift: m.shift });
    }
}

/// Every row's badge is this wide, so they line up.
const BADGE_W: f32 = 124.0;
/// The row's × button.
const REMOVE_W: f32 = 28.0;

/// The row's ×: drawn, so it sits in the middle of its round button
/// (the font's × sat low).
fn remove_button(ui: &mut egui::Ui, enabled: bool) -> egui::Response {
    let sense = if enabled { egui::Sense::click() } else { egui::Sense::hover() };
    let (rect, response) = ui.allocate_exact_size(egui::vec2(28.0, 28.0), sense);
    let p = ui.painter();
    let c = rect.center();
    let hot = enabled && response.hovered();
    if hot {
        p.circle_filled(c, 14.0, egui::Color32::from_white_alpha(22));
    }
    let gray = if !enabled {
        90
    } else if hot {
        245
    } else {
        190
    };
    let stroke = egui::Stroke::new(2.2, egui::Color32::from_gray(gray));
    let d = 5.0;
    p.line_segment([c + egui::vec2(-d, -d), c + egui::vec2(d, d)], stroke);
    p.line_segment([c + egui::vec2(d, -d), c + egui::vec2(-d, d)], stroke);
    if enabled { response.on_hover_cursor(egui::CursorIcon::PointingHand) } else { response }
}

/// The height of a game row's two lines (its name, then size and path).
const ROW_LINES: f32 = 44.0;

#[derive(Clone, Copy, PartialEq)]
enum Mark {
    Ok,
    Skip,
}

/// A round badge: a check mark or a cross.
fn mark(ui: &mut egui::Ui, state: Mark, color: egui::Color32) -> egui::Response {
    // As tall as the row's two lines, so the bubble sits in their middle (a
    // horizontal row centres its items on the height it has so far).
    let (rect, response) = ui.allocate_exact_size(egui::vec2(28.0, ROW_LINES), egui::Sense::hover());
    let p = ui.painter();
    let c = rect.center();
    let ink = egui::Stroke::new(3.0, egui::Color32::WHITE);
    match state {
        Mark::Ok => {
            p.circle_filled(c, 13.0, color);
            p.line(vec![c + egui::vec2(-6.0, 0.5), c + egui::vec2(-1.5, 5.0), c + egui::vec2(6.5, -4.5)], ink);
        }
        Mark::Skip => {
            p.circle_filled(c, 13.0, color);
            p.line_segment([c + egui::vec2(-5.0, -5.0), c + egui::vec2(5.0, 5.0)], ink);
            p.line_segment([c + egui::vec2(5.0, -5.0), c + egui::vec2(-5.0, 5.0)], ink);
        }
    }
    response
}

/// How wide `badge` draws `text`.
fn badge_width(ui: &egui::Ui, text: &str) -> f32 {
    ui.painter().layout_no_wrap(text.to_string(), egui::FontId::proportional(11.5), egui::Color32::WHITE).size().x
        + 14.0
}

/// Ribbit's small grey label (sizes, regions).
fn badge(ui: &mut egui::Ui, text: &str) {
    egui::Frame::NONE
        .fill(egui::Color32::from_white_alpha(14))
        .corner_radius(6)
        .inner_margin(egui::Margin::symmetric(7, 2))
        .show(ui, |ui| {
            ui.label(egui::RichText::new(text).size(11.5).color(egui::Color32::from_gray(200)));
        });
}

fn outcome_badge(ui: &mut egui::Ui, text: &str, color: egui::Color32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(egui::vec2(BADGE_W, 30.0), egui::Sense::hover());
    let p = ui.painter();
    p.rect(
        rect,
        6,
        color.gamma_multiply(0.22),
        egui::Stroke::new(1.0, color.gamma_multiply(0.7)),
        egui::StrokeKind::Inside,
    );
    p.text(rect.center(), egui::Align2::CENTER_CENTER, text, egui::FontId::proportional(14.0), color);
    response
}

/// "Every dump in Ribbit's games folder:" and the folders.
fn ribbit_hover(folders: &[PathBuf]) -> String {
    let list: Vec<String> = folders.iter().map(|f| f.display().to_string()).collect();
    format!(
        "Every .bin and .zip in the Ribbit emulator's games folder:
{}",
        list.join(
            "
"
        )
    )
}

fn empty_list(ui: &mut egui::Ui, info: &Info, actions: &mut Vec<Action>) {
    ui.vertical_centered(|ui| {
        ui.add_space((ui.available_height() * 0.16).max(12.0));
        ui.label(egui::RichText::new("🎮").size(64.0));
        ui.add_space(8.0);
        ui.label(egui::RichText::new("Which games go on the card?").size(24.0).strong().color(egui::Color32::WHITE));
        ui.add_space(6.0);
        ui.label(
            egui::RichText::new(
                "Add the dumps of your own Leapster cartridges (.bin, or zipped), or a whole folder of them.",
            )
            .weak(),
        );
        ui.add_space(22.0);
        ui.add_enabled_ui(!info.building, |ui| {
            if primary_button(ui, "+  Add roms…", egui::vec2(280.0, 46.0)).clicked() {
                actions.push(Action::Pick(Pick::Dumps));
            }
            ui.add_space(10.0);
            if ui
                .add(egui::Button::new("📁  Add a folder of dumps…").corner_radius(8).min_size(egui::vec2(280.0, 36.0)))
                .clicked()
            {
                actions.push(Action::Pick(Pick::DumpFolder));
            }
            if !info.ribbit_folders.is_empty() {
                ui.add_space(10.0);
                let ribbit =
                    colored_button(ui, "🐸  Import Ribbit's Rom Folder", egui::vec2(280.0, 36.0), PURPLE, PURPLE_LIGHT);
                if ribbit.on_hover_text(ribbit_hover(info.ribbit_folders)).clicked() {
                    actions.push(Action::AddRibbitGames);
                }
            }
        });
    });
}

/// Ribbit's green button (the library's Play, Choose games folder).
fn primary_button(ui: &mut egui::Ui, text: &str, min: egui::Vec2) -> egui::Response {
    colored_button(ui, text, min, ACCENT, ACCENT_HOVER)
}

/// A filled button in `fill` (`hover` when pointed at), white text.
fn colored_button(
    ui: &mut egui::Ui,
    text: &str,
    min: egui::Vec2,
    fill: egui::Color32,
    hover: egui::Color32,
) -> egui::Response {
    let galley = egui::WidgetText::from(egui::RichText::new(text).strong()).into_galley(
        ui,
        Some(egui::TextWrapMode::Extend),
        f32::INFINITY,
        egui::TextStyle::Button,
    );
    let pad = ui.spacing().button_padding;
    let size = (galley.size() + 2.0 * pad).max(min);
    let (rect, response) = ui.allocate_exact_size(size, egui::Sense::click());
    if ui.is_rect_visible(rect) {
        let enabled = ui.is_enabled();
        let fill = if !enabled {
            egui::Color32::from_gray(60)
        } else if response.hovered() || response.has_focus() {
            hover
        } else {
            fill
        };
        ui.painter().rect_filled(rect, 8, fill);
        let at = rect.center() - galley.size() / 2.0;
        let fg = if enabled { egui::Color32::WHITE } else { egui::Color32::from_gray(140) };
        ui.painter().galley(at, galley, fg);
    }
    response.on_hover_cursor(egui::CursorIcon::PointingHand)
}

/// A section heading, as Ribbit's side menu's.
fn section(ui: &mut egui::Ui, title: &str) {
    ui.add_space(10.0);
    // (Ribbit's grey, tinted with the mark's purple.)
    ui.label(
        egui::RichText::new(title.to_uppercase()).size(12.5).color(egui::Color32::from_rgb(150, 140, 196)).strong(),
    );
    ui.add_space(4.0);
}

/// The right-hand panel: which console, the menu, the output folder and the
/// Build button with its progress, and the (coming) Leapster 2 over USB.
fn card_panel(ui: &mut egui::Ui, settings: &mut Settings, info: &Info, actions: &mut Vec<Action>) {
    ui.label(egui::RichText::new("Card").size(26.0).family(crate::fonts::title()).color(PURPLE_LIGHT));
    ui.add_space(2.0);
    leapster2_notice(ui);
    ui.add_enabled_ui(!info.building, |ui| {
        section(ui, "Menu");
        let leapfrog = matches!(settings.menu, Menu::LeapFrog(_) | Menu::LeapFrogOnCard);
        // "(Recommended)" after the name: the word in purple, its brackets grey.
        let font = egui::TextStyle::Body.resolve(ui.style());
        let mut label = egui::text::LayoutJob::default();
        let format = |color| egui::TextFormat { font_id: font.clone(), color, ..Default::default() };
        label.append("LeapLoader ", 0.0, format(ui.visuals().text_color()));
        let grey = egui::Color32::from_gray(140);
        label.append("(", 0.0, format(grey));
        label.append("Recommended", 0.0, format(PURPLE_LIGHT));
        label.append(")", 0.0, format(grey));
        let ours = ui.radio(!leapfrog, label);
        if ours.on_hover_text("LeapLoader's own menu: the games' names, search, music").clicked() && leapfrog {
            settings.menu = Menu::LeapLoader;
            actions.push(Action::SettingsChanged);
        }
        // LeapFrog's menu isn't LeapLoader's to hand out: it comes from the
        // user's own .lfp package, or from the card if it has it already.
        let (theirs, import) = ui
            .horizontal(|ui| {
                let theirs = ui.radio(leapfrog, "LeapFrog's SD menu");
                let import = ui.small_button("Import .lfp…").on_hover_text(
                    "LeapFrog's SD menu package, from your own console (e.g. LSTR-0x00130001-000000.lfp)",
                );
                (theirs, import)
            })
            .inner;
        if import.clicked() {
            actions.push(Action::Pick(Pick::LeapFrogMenu));
        }
        let hover = "LeapFrog's own menu: 6 games a page, no music";
        if theirs.on_hover_text(hover).clicked() && !leapfrog {
            if info.menu_on_card.is_some() {
                settings.menu = Menu::LeapFrogOnCard;
                actions.push(Action::SettingsChanged);
            } else {
                actions.push(Action::Pick(Pick::LeapFrogMenu));
            }
        }
        let note = |ui: &mut egui::Ui, text: &str| {
            ui.add(egui::Label::new(egui::RichText::new(text).size(13.0).color(egui::Color32::from_gray(150))).wrap());
        };
        ui.indent("leapfrog menu", |ui| match &settings.menu {
            Menu::LeapFrog(p) => {
                let name = p.file_name().map_or_else(String::new, |n| n.to_string_lossy().into_owned());
                note(ui, &format!("From {name}"));
            }
            Menu::LeapFrogOnCard => note(ui, "The one already in the output folder"),
            Menu::LeapLoader if info.menu_on_card.is_some() => note(ui, "The output folder has it already"),
            Menu::LeapLoader => {}
        });
        section(ui, "Output folder");
        ui.horizontal(|ui| {
            let text = settings.output.as_ref().map_or_else(|| "Choose…".to_string(), |p| p.display().to_string());
            let width = ui.available_width() - if settings.output.is_some() { 40.0 } else { 0.0 };
            let b = egui::Button::new(text).truncate().corner_radius(8).min_size(egui::vec2(width, 30.0));
            let hover = "The card's files are built into this folder: the SD card's drive, or any folder (then copy \
                         its files to the root of the SD card)";
            if ui.add_sized([width, 30.0], b).on_hover_text(hover).clicked() {
                actions.push(Action::Pick(Pick::Output));
            }
            if let Some(out) = &settings.output {
                let open = egui::Button::new("📂").corner_radius(8).min_size(egui::vec2(32.0, 30.0));
                if ui.add(open).on_hover_text("Show the folder").clicked() {
                    actions.push(Action::OpenFolder(out.clone()));
                }
            }
        });
    });
    section(ui, "On the card");
    let chosen: Vec<&Dump> = info.dumps.iter().filter(|d| d.enabled).collect();
    let size = crate::games::card_size_estimate(chosen.iter().copied());
    ui.horizontal(|ui| {
        let games = match chosen.len() {
            1 => "1 game".to_string(),
            n => format!("{n} games"),
        };
        ui.label(egui::RichText::new(games).size(16.0).color(egui::Color32::WHITE));
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            let text = egui::RichText::new(format!("about {}", crate::games::size_text(size))).size(16.0).strong();
            ui.label(text.color(PURPLE_LIGHT))
                .on_hover_text("The room the card's files take: about the size of the dumps, plus the menu");
        });
    });
    ui.add_space(8.0);
    let ready = !chosen.is_empty() && settings.output.is_some() && info.research.is_some();
    if info.building {
        build_progress(ui, info);
        ui.add_space(8.0);
        let stop = egui::Button::new("Stop").corner_radius(8).min_size(egui::vec2(ui.available_width(), 36.0));
        if ui.add(stop).clicked() {
            actions.push(Action::StopBuild);
        }
    } else {
        let w = ui.available_width();
        let label = match chosen.len() {
            0 => "Build card".to_string(),
            1 => "Build card (1 game)".to_string(),
            n => format!("Build card ({n} games)"),
        };
        let b = ui.add_enabled_ui(ready, |ui| primary_button(ui, &label, egui::vec2(w, 44.0))).inner;
        if b.clicked() {
            actions.push(Action::Build);
        }
        let why = if info.dumps.is_empty() {
            Some("Add some games first.")
        } else if chosen.is_empty() {
            Some("Choose some games in the list first.")
        } else if settings.output.is_none() {
            Some("Choose the output folder first.")
        } else if info.research.is_none() {
            Some("LeapLoader's research folder was not found (File → Settings).")
        } else {
            None
        };
        if let Some(why) = why {
            ui.label(egui::RichText::new(why).size(13.0).color(egui::Color32::from_gray(150)));
        }
    }
    ui.add_space(4.0);
    ui.add(egui::Label::new(egui::RichText::new(HARDWARE_WARNING).size(12.0).color(SKIP_RED)).wrap());
    usb_section(ui, info, actions);
}

/// The build's progress: the games converted so far, then the menu (and its
/// music, which takes a while) once every game is done.
fn build_progress(ui: &mut egui::Ui, info: &Info) {
    let on_card = info.dumps.iter().filter(|d| d.enabled).count();
    let done = info.dumps.iter().filter(|d| d.outcome.is_some()).count();
    // The games are most of the work; the menu the last tenth.
    let (fraction, text) = if done < on_card {
        (done as f32 / on_card as f32 * 0.9, format!("Converting games… {done} of {on_card}"))
    } else {
        (0.95, "Making the menu…".to_string())
    };
    let bar = egui::ProgressBar::new(fraction)
        .text(egui::RichText::new(text).color(egui::Color32::WHITE))
        .fill(ACCENT)
        .corner_radius(8)
        .desired_height(26.0)
        .animate(true);
    ui.add(bar);
}

/// LeapLoader's cards are for the Leapster 2 only.
/// The disclaimer (user's request): nothing has been tried on a real
/// console yet, only in the Ribbit emulator.
const HARDWARE_WARNING: &str = "⚠ Not yet tested on a real Leapster 2, only in the Ribbit emulator. Use at your \
                                own risk, and copy your SD card's files somewhere first.";

fn leapster2_notice(ui: &mut egui::Ui) {
    egui::Frame::NONE
        .fill(PURPLE.gamma_multiply(0.18))
        .stroke(egui::Stroke::new(1.0, PURPLE.gamma_multiply(0.6)))
        .corner_radius(10)
        .inner_margin(egui::Margin::symmetric(10, 6))
        .show(ui, |ui| {
            ui.set_width(ui.available_width());
            let grey = egui::TextFormat {
                font_id: egui::FontId::proportional(12.5),
                color: egui::Color32::from_gray(205),
                ..Default::default()
            };
            let white = egui::TextFormat { color: egui::Color32::WHITE, ..grey.clone() };
            // Which console (the first Leapster and the L-MAX have no SD card),
            let mut job = egui::text::LayoutJob::default();
            job.append("For the ", 0.0, grey.clone());
            job.append("Leapster 2", 0.0, white.clone());
            job.append(" only (the Leapster 1 and L-MAX have no SD card).", 0.0, grey.clone());
            ui.add(egui::Label::new(job).wrap());
            // and how to get back to the menu from a game (research/ingame.py):
            // the one thing on the console a player has to know.
            let mut back = egui::text::LayoutJob::default();
            back.append("In a game, hold ", 0.0, grey.clone());
            back.append("HINT + A + B", 0.0, white);
            back.append(" to save and go back to the menu.", 0.0, grey);
            ui.add(egui::Label::new(back).wrap());
        });
}

/// The console's own storage over USB (docs/usb-research.md, usb.rs):
/// find it, open its SD card, build the card onto it, eject it. Each step
/// that changes something is asked first (`dialogs`).
fn usb_section(ui: &mut egui::Ui, info: &Info, actions: &mut Vec<Action>) {
    ui.add_space(12.0);
    egui::Frame::new()
        .fill(CARD)
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_white_alpha(14)))
        .corner_radius(10)
        .inner_margin(egui::Margin::symmetric(12, 9))
        .show(ui, |ui| {
            ui.set_width(ui.available_width());
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("🔌  Leapster 2 over USB").size(16.0).strong());
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| badge(ui, "Beta"));
            });
            ui.add_space(4.0);
            let note = |ui: &mut egui::Ui, text: &str, color: egui::Color32| {
                ui.add(egui::Label::new(egui::RichText::new(text).size(13.0).color(color)).wrap());
            };
            let grey = egui::Color32::from_gray(170);
            note(
                ui,
                "Plug in your Leapster 2 with its USB cable, turn it on, and build straight onto its SD card.",
                grey,
            );
            ui.add_space(6.0);
            let busy = info.usb_busy.is_some() || info.building;
            ui.add_enabled_ui(!busy, |ui| {
                let look = egui::Button::new("Look for a Leapster 2").corner_radius(8);
                if ui
                    .add_sized([ui.available_width(), 30.0], look)
                    .on_hover_text("Reads the disks' names only")
                    .clicked()
                {
                    actions.push(Action::FindLeapster);
                }
            });
            if let Some(what) = info.usb_busy {
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(egui::RichText::new(what).size(13.0).color(grey));
                });
            }
            match info.usb {
                None => {}
                Some(scan) if scan.found.is_empty() => {
                    ui.add_space(4.0);
                    note(
                        ui,
                        "No Leapster 2 found. Connect it with its USB cable and turn it on (it shows its \
                         \"connected\" screen), then look again.",
                        egui::Color32::from_gray(150),
                    );
                }
                Some(scan) => {
                    for (kind, disk) in &scan.found {
                        ui.add_space(6.0);
                        let at = disk.mounted.as_ref().map_or_else(String::new, |m| format!(" at {}", m.display()));
                        let text = format!("✔ Leapster 2 {}{at}", kind.label());
                        ui.label(egui::RichText::new(text).size(13.5).color(ACCENT)).on_hover_text(format!(
                            "{}: {} {} {}",
                            disk.device,
                            disk.vendor.trim(),
                            disk.product.trim(),
                            disk.revision.trim()
                        ));
                        ui.add_enabled_ui(!busy, |ui| match (kind, &disk.mounted) {
                            (crate::usb::Kind::Internal, _) => {
                                note(ui, "Internal storage: looking only, for now.", egui::Color32::from_gray(150));
                            }
                            (crate::usb::Kind::Sd, None) => {
                                let open = egui::Button::new("Open the SD card…").corner_radius(8);
                                if ui.add_sized([ui.available_width(), 28.0], open).clicked() {
                                    actions.push(Action::AskUsb(UsbStep::Open(disk.clone())));
                                }
                            }
                            (crate::usb::Kind::Sd, Some(volume)) => {
                                let w = ui.available_width();
                                let chosen = info.dumps.iter().filter(|d| d.enabled).count();
                                ui.add_enabled_ui(chosen > 0, |ui| {
                                    let label = format!("Build card onto the Leapster 2 ({chosen})");
                                    if primary_button(ui, &label, egui::vec2(w, 32.0)).clicked() {
                                        actions.push(Action::AskUsb(UsbStep::BuildOnto(volume.clone())));
                                    }
                                });
                                ui.add_space(4.0);
                                let text = if info.usb_built == Some(volume.as_path()) {
                                    "Eject the Leapster 2 (done)…"
                                } else {
                                    "Eject the Leapster 2…"
                                };
                                if ui.add_sized([w, 28.0], egui::Button::new(text).corner_radius(8)).clicked() {
                                    actions.push(Action::AskUsb(UsbStep::Eject(disk.clone())));
                                }
                            }
                        });
                    }
                }
            }
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui.small_button("Copy USB log").on_hover_text("For a bug report").clicked() {
                    actions.push(Action::CopyUsbLog);
                }
                if ui.small_button("Save USB log").on_hover_text("Saves usb-log.txt and shows it").clicked() {
                    actions.push(Action::SaveUsbLog);
                }
            });
        });
}

/// The question before a USB step: title, text, the yes button's words.
fn usb_question(step: &UsbStep, info: &Info) -> (String, String, &'static str) {
    match step {
        UsbStep::Open(disk) => (
            "Open the Leapster 2's SD card?".into(),
            format!(
                "LeapLoader sends the console its \"mount\" command, as LeapFrog's own software does, so its SD card \
                 shows up as a drive on this PC. Only the Leapster 2's SD card disk is touched ({}).\n\nThe admin prompt \
                 comes up for this one step.",
                disk.device
            ),
            "Open it",
        ),
        UsbStep::BuildOnto(volume) => {
            let chosen: Vec<&Dump> = info.dumps.iter().filter(|d| d.enabled).collect();
            let size = crate::games::card_size_estimate(chosen.iter().copied());
            let free = crate::usb::free_space(volume)
                .map_or_else(String::new, |f| format!(" ({} free)", crate::games::size_text(f)));
            (
                "Build the card onto the Leapster 2?".into(),
                format!(
                    "{} games, about {}, go onto the SD card at {}{free}. LeapLoader adds its Leapster folder there and \
                     replaces the games and menu it put there before; other files are left alone. Nothing is formatted.",
                    chosen.len(),
                    crate::games::size_text(size),
                    volume.display()
                ),
                "Build onto it",
            )
        }
        UsbStep::Eject(disk) => (
            "Eject the Leapster 2?".into(),
            format!(
                "LeapLoader makes sure everything is written to the SD card, closes the drive and sends the console its \
                 \"eject\" command ({}). Then you can unplug it.\n\nThe admin prompt comes up again.",
                disk.device
            ),
            "Eject",
        ),
    }
}

fn dialogs(ctx: &egui::Context, st: &mut UiState, settings: &mut Settings, info: &Info, actions: &mut Vec<Action>) {
    // First start: the AI note and the hardware warning as a pop-up, read
    // once (Ribbit's first-start note).
    if !settings.ai_notice_seen {
        egui::Modal::new(egui::Id::new("ai-notice")).frame(card_frame()).show(ctx, |ui| {
            ui.set_width(ctx.content_rect().width().min(560.0) - 80.0);
            ai_notice_text(ui);
            ui.add_space(16.0);
            ui.vertical_centered(|ui| {
                if primary_button(ui, "Continue", egui::vec2(220.0, 44.0)).clicked() {
                    settings.ai_notice_seen = true;
                    actions.push(Action::SettingsChanged);
                }
            });
        });
    }
    if let Some(step) = st.confirm_usb.clone() {
        let (title, text, yes) = usb_question(&step, info);
        egui::Modal::new(egui::Id::new("confirm usb")).frame(card_frame()).show(ctx, |ui| {
            ui.set_width(460.0);
            ui.label(egui::RichText::new(title).size(20.0).strong().color(egui::Color32::WHITE));
            ui.add_space(6.0);
            ui.add(egui::Label::new(egui::RichText::new(text).color(egui::Color32::from_gray(205))).wrap());
            ui.add_space(14.0);
            ui.horizontal(|ui| {
                if primary_button(ui, yes, egui::vec2(140.0, 36.0)).clicked() {
                    st.confirm_usb = None;
                    actions.push(Action::DoUsb(step.clone()));
                }
                if ui.add(egui::Button::new("Cancel").corner_radius(8).min_size(egui::vec2(100.0, 36.0))).clicked() {
                    st.confirm_usb = None;
                }
            });
        });
    }
    if let Some(out) = st.confirm_output.clone() {
        egui::Modal::new(egui::Id::new("confirm output")).frame(card_frame()).show(ctx, |ui| {
            ui.set_width(440.0);
            ui.label(egui::RichText::new("This folder isn't empty").size(20.0).strong().color(egui::Color32::WHITE));
            ui.add_space(6.0);
            ui.add(
                egui::Label::new(
                    egui::RichText::new(format!(
                        "{}\n\nIt holds other files. LeapLoader adds its Leapster folder here and replaces the \
                         games and menu it built before; other files are left alone.",
                        out.display()
                    ))
                    .color(egui::Color32::from_gray(205)),
                )
                .wrap(),
            );
            ui.add_space(14.0);
            ui.horizontal(|ui| {
                if primary_button(ui, "Build here", egui::vec2(140.0, 36.0)).clicked() {
                    st.confirm_output = None;
                    actions.push(Action::BuildAnyway);
                }
                if ui.add(egui::Button::new("Cancel").corner_radius(8).min_size(egui::vec2(100.0, 36.0))).clicked() {
                    st.confirm_output = None;
                }
            });
        });
    }
    if let Some((title, explain)) = st.problem.clone() {
        egui::Modal::new(egui::Id::new("problem")).frame(card_frame()).show(ctx, |ui| {
            ui.set_width(440.0);
            ui.label(egui::RichText::new(title).size(20.0).strong().color(egui::Color32::WHITE));
            ui.add_space(6.0);
            ui.add(egui::Label::new(egui::RichText::new(explain).color(egui::Color32::from_gray(205))).wrap());
            ui.add_space(14.0);
            if primary_button(ui, "OK", egui::vec2(100.0, 34.0)).clicked() {
                st.problem = None;
            }
        });
    }
    let mut open = st.show_settings;
    egui::Window::new("Settings").open(&mut open).collapsible(false).resizable(false).show(ctx, |ui| {
        ui.set_width(460.0);
        ui.label(egui::RichText::new("The card is built by LeapLoader's research scripts (mkcard.py) for now.").weak());
        ui.add_space(8.0);
        egui::Grid::new("settings grid").num_columns(2).spacing([12.0, 10.0]).show(ui, |ui| {
            ui.label("Research folder");
            ui.horizontal(|ui| {
                let found = info.research.as_ref().map_or_else(|| "(not found)".into(), |p| p.display().to_string());
                if ui.button(found).on_hover_text("The folder with mkcard.py").clicked() {
                    actions.push(Action::Pick(Pick::Research));
                }
                if settings.research.is_some()
                    && ui.small_button("×").on_hover_text("Find it next to the program").clicked()
                {
                    settings.research = None;
                    actions.push(Action::SettingsChanged);
                }
            });
            ui.end_row();
            ui.label("Python");
            if ui.add(egui::TextEdit::singleline(&mut settings.python).desired_width(260.0)).lost_focus() {
                actions.push(Action::SettingsChanged);
            }
            ui.end_row();
            ui.label("nativescan");
            ui.horizontal(|ui| {
                let found =
                    info.nativescan.as_ref().map_or_else(|| "(mkcard's own)".into(), |p| p.display().to_string());
                if ui.button(found).on_hover_text("The converter's helper (NATIVESCAN)").clicked() {
                    actions.push(Action::Pick(Pick::Nativescan));
                }
                if settings.nativescan.is_some() && ui.small_button("×").clicked() {
                    settings.nativescan = None;
                    actions.push(Action::SettingsChanged);
                }
            });
            ui.end_row();
            ui.label("Leapster 2 BIOS");
            ui.horizontal(|ui| {
                let found =
                    info.bios.as_ref().map_or_else(|| "(none: no menu music)".into(), |p| p.display().to_string());
                if ui
                    .button(found)
                    .on_hover_text(
                        "Your Leapster 2 BIOS 0.6 dump: LeapLoader's menu music is played with its instruments",
                    )
                    .clicked()
                {
                    actions.push(Action::Pick(Pick::Bios));
                }
                if settings.bios.is_some()
                    && ui.small_button("×").on_hover_text("Use the one picked in Ribbit").clicked()
                {
                    settings.bios = None;
                    actions.push(Action::SettingsChanged);
                }
            });
            ui.end_row();
        });
    });
    st.show_settings = open;
    let mut open = st.show_about;
    egui::Window::new("About LeapLoader").open(&mut open).collapsible(false).resizable(false).show(ctx, |ui| {
        ui.horizontal(|ui| {
            ui.add(egui::Image::new((frog(ui).id(), egui::vec2(48.0, 48.0))));
            ui.vertical(|ui| {
                ui.label(egui::RichText::new("LeapLoader").size(24.0).family(crate::fonts::title()));
                ui.label(format!("Version {}", env!("CARGO_PKG_VERSION")));
            });
        });
        ui.add_space(6.0);
        ui.label("Puts your own Leapster cartridge dumps on an SD card for the Leapster 2.");
        ui.add_space(4.0);
        ui.add(egui::Label::new(egui::RichText::new(HARDWARE_WARNING).color(SKIP_RED)).wrap());
        ui.add_space(4.0);
        ui.label("LeapLoader is free software under the GNU GPL v3 or later.");
        ui.label(
            egui::RichText::new(
                "Credits: the Leapster 2's USB mount/eject method is from LFTools by Ian Mathews (awes145), \
                 GPL-3.0. Look and code from the Ribbit emulator, used with its author's permission. Fonts: \
                 Fredoka (SIL Open Font License); the frog: Noto Emoji (SIL Open Font License).",
            )
            .size(12.5)
            .weak(),
        );
        ui.label(egui::RichText::new("LeapLoader is not affiliated with or endorsed by LeapFrog.").size(12.5).weak());
    });
    st.show_about = open;
}

/// The README's "This project was made with AI", shortened (as Ribbit's
/// first-start note), and that nothing has been tried on a real console.
fn ai_notice_text(ui: &mut egui::Ui) {
    ui.with_layout(egui::Layout::top_down(egui::Align::Min), |ui| {
        ui.label(egui::RichText::new("This project was made with AI").size(21.0).strong().color(egui::Color32::WHITE));
        ui.add_space(2.0);
        ui.label(egui::RichText::new("Please read this before you start").size(13.5).color(ACCENT));
        ui.add_space(12.0);
        for text in [
            "LeapLoader is written almost entirely by an AI coding assistant (Anthropic's Claude), working under my \
             direction: I choose what to work on, test it, supply the hardware references and decide what goes in.",
            "Many people don't want to use AI-written software, for reasons I respect: licensing and where training \
             data comes from, code quality, and the work of people who reverse-engineer hardware by hand. If that's \
             you, no hard feelings.",
            "Otherwise, please judge LeapLoader by its results: every hardware claim in its notes says how sure it \
             is and where it comes from.",
        ] {
            ui.add(egui::Label::new(egui::RichText::new(text).size(15.0).color(egui::Color32::from_gray(205))).wrap());
            ui.add_space(9.0);
        }
        ui.label(egui::RichText::new("Use at your own risk").size(16.0).strong().color(SKIP_RED));
        ui.add_space(2.0);
        ui.add(
            egui::Label::new(
                egui::RichText::new(
                    "LeapLoader has not been tested on a real Leapster 2 yet, only in the Ribbit emulator. Copy your \
                     SD card's files somewhere before you put LeapLoader's files on it.",
                )
                .size(15.0)
                .color(SKIP_RED),
            )
            .wrap(),
        );
        ui.add_space(11.0);
        ui.label(
            egui::RichText::new("LeapLoader is not affiliated with or endorsed by LeapFrog.")
                .size(12.5)
                .color(egui::Color32::from_gray(130)),
        );
    });
}

/// Ribbit's dialog card: dark, rounded, with a soft green edge.
fn card_frame() -> egui::Frame {
    egui::Frame::new()
        .fill(CARD)
        .stroke(egui::Stroke::new(1.0, ACCENT.gamma_multiply(0.55)))
        .corner_radius(16)
        .inner_margin(egui::Margin::symmetric(24, 20))
        .shadow(egui::epaint::Shadow {
            offset: [0, 8],
            blur: 28,
            spread: 0,
            color: egui::Color32::from_black_alpha(110),
        })
}
