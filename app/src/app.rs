// SPDX-License-Identifier: GPL-3.0-or-later
//! The window and what the UI's actions do: the games list, the settings
//! file, file dialogs and the card build. The event loop follows Ribbit's
//! (crates/ribbit-frontend/src/app.rs), but draws only when something
//! changed instead of every frame.

use crate::card::{self, Build, Event};
use crate::files::Pick;
use crate::games::Dump;
use crate::gpu::Gpu;
use crate::settings::{Menu, Settings};
use crate::ui::{self, Action, Bulk, Info, UiState, UsbStep};
use anyhow::{Context as _, Result};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;
use winit::application::ApplicationHandler;
use winit::event::{StartCause, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::window::{Window, WindowId};

const APP_NAME: &str = concat!("LeapLoader v", env!("CARGO_PKG_VERSION"));
const START_WINDOW: winit::dpi::LogicalSize<f64> = winit::dpi::LogicalSize::new(1180.0, 760.0);
const MIN_WINDOW: winit::dpi::LogicalSize<f64> = winit::dpi::LogicalSize::new(760.0, 480.0);

/// What a finished USB step gives back.
enum UsbDone {
    /// The SD card is open: the drive it appeared as.
    Opened(PathBuf),
    Ejected,
}

/// Sent to the event loop to draw again (a build's output came in).
#[derive(Debug, Clone, Copy)]
pub struct Wake;

pub struct App {
    data_dir: PathBuf,
    /// An installed update asked for a restart (install.rs).
    restart_for_update: bool,
    settings: Settings,
    dumps: Vec<Dump>,
    ui: UiState,
    build: Option<Build>,
    last_build: Option<(bool, String)>,
    /// The dumps the running build was given (indices into `dumps`).
    on_card: Vec<usize>,
    /// Where the last plain or Ctrl click in the list was (for Shift).
    anchor: Option<usize>,
    /// mkcard's folder and nativescan, looked up after each change (not
    /// every frame: they are files to find).
    research: Option<PathBuf>,
    nativescan: Option<PathBuf>,
    bios: Option<PathBuf>,
    /// The settings they were found for.
    tools_for: Option<(Option<PathBuf>, Option<PathBuf>, Option<PathBuf>)>,
    /// LeapFrog's SD menu in the output folder, if it has one.
    menu_on_card: Option<PathBuf>,
    /// The last look for a Leapster 2 on USB (usb.rs): its disks, and the
    /// number of other disks left alone.
    usb: Option<crate::usb::Scan>,
    /// A USB step running on its own thread: what it is doing, and its answer.
    usb_job: Option<(String, std::sync::mpsc::Receiver<Result<UsbDone, crate::usb::UsbError>>)>,
    /// The drive the running (or last) build went onto, when it was the
    /// Leapster 2's.
    usb_built: Option<PathBuf>,
    /// The Ribbit emulator's games folders (looked up at start).
    ribbit_folders: Vec<PathBuf>,
    gpu: Option<Gpu>,
    egui_state: Option<egui_winit::State>,
    egui_ctx: egui::Context,
    /// The file dialog open now, if any.
    sheet: Option<crate::files::SheetPick>,
    fatal: Option<anyhow::Error>,
}

pub fn run(data_dir: PathBuf) -> Result<()> {
    let event_loop = EventLoop::<Wake>::with_user_event().build().context("creating event loop")?;
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App::new(data_dir, event_loop.create_proxy());
    event_loop.run_app(&mut app)?;
    app.save_settings();
    match app.fatal {
        Some(e) => Err(e),
        None => Ok(()),
    }
}

/// An egui context with Ribbit's fonts and look.
fn egui_context() -> egui::Context {
    let ctx = egui::Context::default();
    crate::fonts::install(&ctx);
    // The colours in ui.rs are made for the dark theme, whatever the system's.
    ctx.set_theme(egui::Theme::Dark);
    // Buttons keep their size when pointed at or pressed (egui grows them a
    // pixel, so their text jumped). (Ribbit's `egui_context`.)
    ctx.all_styles_mut(|s| {
        let w = &mut s.visuals.widgets;
        for state in [&mut w.hovered, &mut w.active, &mut w.open] {
            state.expansion = 0.0;
        }
    });
    ctx
}

impl App {
    fn new(data_dir: PathBuf, proxy: EventLoopProxy<Wake>) -> Self {
        let settings = Settings::load(&data_dir.join("settings.toml"));
        // The USB log's clock starts with the app.
        crate::usb::note("app started");
        // What the last update moved aside.
        crate::install::remove_leftovers();
        let egui_ctx = egui_context();
        {
            // Another thread asking egui to draw (the build's output) wakes
            // the event loop; egui's own timed repaints are `redraw`'s.
            egui_ctx.set_request_repaint_callback(move |info| {
                if info.delay.is_zero() {
                    let _ = proxy.send_event(Wake);
                }
            });
        }
        let mut app = Self {
            data_dir,
            restart_for_update: false,
            dumps: Vec::new(),
            ui: UiState::default(),
            build: None,
            last_build: None,
            on_card: Vec::new(),
            anchor: None,
            ribbit_folders: crate::games::ribbit_rom_folders(),
            menu_on_card: None,
            usb: None,
            usb_job: None,
            usb_built: None,
            research: None,
            nativescan: None,
            bios: None,
            tools_for: None,
            gpu: None,
            egui_state: None,
            egui_ctx,
            sheet: None,
            fatal: None,
            settings,
        };
        // The list from last time (dumps since moved or deleted drop off).
        let saved = std::mem::take(&mut app.settings.dumps);
        app.add_dumps(saved, false);
        for d in &mut app.dumps {
            // Compatible: on unless switched off; incompatible: off unless
            // switched on anyway.
            d.enabled = if d.tested() {
                !app.settings.unselected.contains(&d.path)
            } else {
                app.settings.try_anyway.contains(&d.path)
            };
        }
        // The emulators LeapLoader comes with: on the list once (taken off, they stay off).
        let mut added = false;
        for (id, dir) in crate::emulators::install(&app.data_dir) {
            if !app.settings.emulators_added.iter().any(|a| a == id) {
                app.add_dumps(vec![dir], false);
                app.settings.emulators_added.push(id.to_string());
                added = true;
            }
        }
        if added {
            app.save_settings();
        }
        app.look_for_menu();
        app.find_tools();
        app
    }

    /// Looks in the output folder for LeapFrog's SD menu (on choosing it, and
    /// after builds); a choice of it that is gone falls back to LeapLoader's.
    fn look_for_menu(&mut self) {
        self.menu_on_card = self.settings.output.as_deref().and_then(card::leapfrog_menu_in);
        if self.settings.menu == Menu::LeapFrogOnCard && self.menu_on_card.is_none() {
            self.settings.menu = Menu::LeapLoader;
        }
    }

    /// Finds mkcard's folder and nativescan again if their settings changed.
    fn find_tools(&mut self) {
        let key = (self.settings.research.clone(), self.settings.nativescan.clone(), self.settings.bios.clone());
        if self.tools_for.as_ref() != Some(&key) {
            self.research = card::research_dir(&self.settings);
            self.nativescan = card::default_nativescan(&self.settings);
            self.bios = card::find_bios(&self.settings);
            self.tools_for = Some(key);
        }
    }

    fn settings_path(&self) -> PathBuf {
        self.data_dir.join("settings.toml")
    }

    fn save_settings(&mut self) {
        self.settings.dumps = self.dumps.iter().map(|d| d.path.clone()).collect();
        self.settings.unselected = self.dumps.iter().filter(|d| !d.enabled).map(|d| d.path.clone()).collect();
        self.settings.try_anyway =
            self.dumps.iter().filter(|d| d.enabled && !d.tested()).map(|d| d.path.clone()).collect();
        if let Err(e) = self.settings.save(&self.settings_path()) {
            eprintln!("could not save the settings: {e:#}");
        }
    }

    /// Adds dumps to the list (each file once); `tell`: say what could not
    /// be read.
    fn add_dumps(&mut self, paths: Vec<PathBuf>, tell: bool) {
        let mut problems = Vec::new();
        let mut added = 0;
        for path in paths {
            if self.dumps.iter().any(|d| d.path == path) {
                continue;
            }
            match Dump::open(&path) {
                Ok(d) => {
                    self.dumps.push(d);
                    added += 1;
                }
                Err(e) => problems.push(format!("{}: {e:#}", path.display())),
            }
        }
        if added > 0 {
            self.sort_dumps();
        }
        if tell {
            self.ui.message = Some(match added {
                1 => "Added 1 game".into(),
                n => format!("Added {n} games"),
            });
            if !problems.is_empty() {
                self.ui.problem("Some files could not be added", problems.join("\n"));
            }
        }
    }

    /// Keeps the list in A-Z order of the names, as the menu on the card
    /// (mkcard sorts its titles the same way). A running build's games
    /// (`on_card`) keep pointing at the same dumps.
    fn sort_dumps(&mut self) {
        let card: Vec<PathBuf> = self.on_card.iter().map(|&i| self.dumps[i].path.clone()).collect();
        self.dumps.sort_by_cached_key(|d| (d.name.to_lowercase(), d.path.clone()));
        self.on_card = card.iter().filter_map(|p| self.dumps.iter().position(|d| &d.path == p)).collect();
        self.anchor = None;
    }

    fn pick(&mut self, what: Pick) {
        let start = match what {
            Pick::Dumps | Pick::DumpFolder => self.settings.dumps_folder.clone(),
            Pick::Output => self.settings.output.clone(),
            Pick::LeapFrogMenu => match &self.settings.menu {
                Menu::LeapFrog(p) => Some(p.clone()),
                Menu::LeapLoader | Menu::LeapFrogOnCard => None,
            },
            Pick::Research => card::research_dir(&self.settings),
            Pick::Nativescan => card::default_nativescan(&self.settings),
            Pick::Bios => card::find_bios(&self.settings),
        };
        if self.sheet.is_none()
            && let Some(g) = &self.gpu
        {
            self.sheet = Some(crate::files::SheetPick::start(what, start.as_deref(), &g.window));
        }
    }

    fn picked(&mut self, what: Pick, paths: Vec<PathBuf>) {
        let Some(first) = paths.first().cloned() else {
            return;
        };
        match what {
            Pick::Dumps => {
                self.settings.dumps_folder = first.parent().map(Path::to_path_buf);
                self.add_dumps(paths, true);
            }
            Pick::DumpFolder => {
                let found = crate::games::dumps_in(&first);
                self.settings.dumps_folder = Some(first.clone());
                if found.is_empty() {
                    self.ui.problem("No dumps there", format!("{} has no .bin or .zip files.", first.display()));
                }
                self.add_dumps(found, true);
            }
            Pick::Output => {
                self.settings.output = Some(first);
                self.look_for_menu();
            }
            Pick::LeapFrogMenu => self.settings.menu = Menu::LeapFrog(first),
            Pick::Research => {
                if first.join("mkcard.py").is_file() {
                    self.settings.research = Some(first);
                } else {
                    self.ui.problem(
                        "That isn't LeapLoader's research folder",
                        format!("{} has no mkcard.py.", first.display()),
                    );
                }
            }
            Pick::Nativescan => self.settings.nativescan = Some(first),
            Pick::Bios => self.settings.bios = Some(first),
        }
        self.save_settings();
    }

    fn act(&mut self, action: Action) {
        match action {
            Action::Pick(what) => self.pick(what),
            Action::FindLeapster => self.look_for_leapster(),
            Action::AskUsb(step) => self.ui.confirm_usb = Some(step),
            Action::DoUsb(step) => self.usb_step(step),
            Action::CopyUsbLog => {
                self.egui_ctx.copy_text(crate::usb::log_text());
                self.ui.message = Some("USB log copied".into());
            }
            Action::SaveUsbLog => match crate::usb::save_log(&self.data_dir) {
                Ok(path) => {
                    self.ui.message = Some(format!("USB log saved: {}", path.display()));
                    open_folder(&self.data_dir);
                }
                Err(e) => self.ui.problem("The USB log can't be saved", e.to_string()),
            },
            Action::AddRibbitGames => {
                let found: Vec<PathBuf> = self.ribbit_folders.iter().flat_map(|f| crate::games::dumps_in(f)).collect();
                self.add_dumps(found, true);
                self.save_settings();
            }
            Action::RemoveDump(i) => {
                if i < self.dumps.len() {
                    self.dumps.remove(i);
                    self.anchor = None;
                    self.save_settings();
                }
            }
            Action::ClearDumps => {
                self.dumps.clear();
                self.anchor = None;
                self.save_settings();
            }
            Action::Click { index, ctrl, shift } => {
                self.anchor = crate::games::click(&mut self.dumps, self.anchor, index, ctrl, shift);
                self.save_settings();
            }
            Action::PickAll => {
                for d in &mut self.dumps {
                    d.picked = true;
                }
            }
            Action::Selected(what) => {
                match what {
                    Bulk::TurnOn | Bulk::TurnOff => {
                        for d in self.dumps.iter_mut().filter(|d| d.picked) {
                            d.enabled = what == Bulk::TurnOn;
                        }
                    }
                    Bulk::Remove => {
                        self.dumps.retain(|d| !d.picked);
                        self.anchor = None;
                    }
                    Bulk::Clear => {}
                }
                for d in &mut self.dumps {
                    d.picked = false;
                }
                self.save_settings();
            }
            Action::SelectAll(on) => {
                // (Enable all leaves the incompatible ones off: each is
                // switched on deliberately, one at a time.)
                for d in &mut self.dumps {
                    d.enabled = on && d.tested();
                }
                self.save_settings();
            }
            Action::Build => {
                let Some(out) = self.settings.output.clone() else {
                    return;
                };
                // Anything there but an earlier card: ask first.
                let others = std::fs::read_dir(&out)
                    .map(|d| d.flatten().any(|e| !e.file_name().eq_ignore_ascii_case("Leapster")))
                    .unwrap_or(false);
                if others {
                    self.ui.confirm_output = Some(out);
                } else {
                    self.start_build(out);
                }
            }
            Action::BuildAnyway => {
                if let Some(out) = self.settings.output.clone() {
                    self.start_build(out);
                }
            }
            Action::StopBuild => {
                if let Some(b) = &self.build {
                    b.stop();
                    self.ui.log.push("(stopping…)".into());
                }
            }
            Action::OpenFolder(path) => open_folder(&path),
            Action::SettingsChanged => self.save_settings(),
            Action::RestartForUpdate => self.restart_for_update = true,
        }
    }

    /// Builds the card into `out` (the output folder, or the Leapster 2's
    /// SD card drive).
    fn start_build(&mut self, out: PathBuf) {
        self.usb_built = None;
        for d in &mut self.dumps {
            d.outcome = None;
        }
        // Only the games chosen in the list go on the card.
        let on_card: Vec<usize> = (0..self.dumps.len()).filter(|&i| self.dumps[i].enabled).collect();
        let dumps: Vec<(PathBuf, Option<String>)> =
            on_card.iter().map(|&i| (self.dumps[i].path.clone(), self.dumps[i].zip_entry.clone())).collect();
        let ctx = self.egui_ctx.clone();
        match Build::start(&self.settings, &out, &dumps, move || ctx.request_repaint()) {
            Ok(b) => {
                self.ui.log.clear();
                self.ui.message = None;
                self.build = Some(b);
                self.last_build = None;
                self.on_card = on_card;
            }
            Err(e) => self.ui.problem("The card can't be built", format!("{e:#}")),
        }
    }

    /// Looks for the Leapster 2 (reading only).
    fn look_for_leapster(&mut self) {
        let scan = crate::usb::scan();
        self.ui.message = Some(match scan.found.len() {
            0 => format!("No Leapster 2 found ({} other disks left alone)", scan.others),
            n => format!("Leapster 2 found ({n} of its disks)"),
        });
        self.usb = Some(scan);
        let _ = crate::usb::save_log(&self.data_dir);
    }

    /// Does a USB step the user said yes to: opening the SD card and ejecting
    /// run on a thread (they wait for the admin prompt and the console);
    /// building onto it is a build into its drive.
    fn usb_step(&mut self, step: UsbStep) {
        let logdir = self.data_dir.clone();
        let (what, job): (String, Box<dyn FnOnce() -> Result<UsbDone, crate::usb::UsbError> + Send>) = match step {
            UsbStep::BuildOnto(volume) => {
                crate::usb::note(format!("build onto {}: started", volume.display()));
                self.start_build(volume.clone());
                if self.build.is_some() {
                    self.usb_built = Some(volume);
                }
                return;
            }
            UsbStep::Open(disk) => (
                "Opening the SD card (answer the admin prompt)…".into(),
                Box::new(move || {
                    crate::usb::note(format!("open {}", disk.device));
                    crate::usb::run_elevated("mount", &disk.device, None, &logdir)?;
                    crate::usb::wait_for_volume(&disk.device, 30).map(UsbDone::Opened)
                }),
            ),
            UsbStep::Eject(disk) => (
                "Ejecting (answer the admin prompt)…".into(),
                Box::new(move || {
                    crate::usb::note(format!("eject {}", disk.device));
                    crate::usb::run_elevated("eject", &disk.device, disk.mounted.as_deref(), &logdir)
                        .map(|()| UsbDone::Ejected)
                }),
            ),
        };
        let (tx, rx) = std::sync::mpsc::channel();
        let ctx = self.egui_ctx.clone();
        std::thread::spawn(move || {
            let _ = tx.send(job());
            ctx.request_repaint();
        });
        self.usb_job = Some((what, rx));
    }

    /// Takes in a finished USB step.
    fn poll_usb(&mut self) {
        let Some((_, rx)) = &self.usb_job else { return };
        let Ok(result) = rx.try_recv() else { return };
        self.usb_job = None;
        match result {
            Ok(UsbDone::Opened(at)) => {
                crate::usb::note(format!("open: done, SD card at {}", at.display()));
                self.ui.message = Some(format!("Leapster 2's SD card open at {}", at.display()));
            }
            Ok(UsbDone::Ejected) => {
                crate::usb::note("eject: done");
                self.ui.message = Some("Leapster 2 ejected: you can unplug it".into());
                self.usb_built = None;
            }
            Err(e) => {
                crate::usb::note(format!("failed: {e}"));
                self.ui.problem(
                    "Leapster 2 over USB",
                    format!("{e}\n\nThe USB log has the details: Save USB log, and send it with your report."),
                );
            }
        }
        let _ = crate::usb::save_log(&self.data_dir);
        // What the disks look like now.
        self.usb = Some(crate::usb::scan());
    }

    /// Takes in what the build said since the last frame.
    fn poll_build(&mut self) {
        let Some(build) = &self.build else {
            return;
        };
        let labels: Vec<String> = self.on_card.iter().map(|&i| self.dumps[i].label()).collect();
        let mut finished = None;
        while let Ok(event) = build.events.try_recv() {
            match event {
                Event::Line(line) => {
                    let taken: Vec<bool> = self.on_card.iter().map(|&i| self.dumps[i].outcome.is_some()).collect();
                    if let Some((k, outcome)) = card::outcome_for(&line, &labels, &taken) {
                        self.dumps[self.on_card[k]].outcome = Some(outcome);
                    }
                    self.ui.log.push(line);
                }
                Event::Done(ok, how) => finished = Some((ok, how)),
            }
        }
        if let Some((ok, how)) = finished {
            let made = self.dumps.iter().filter(|d| matches!(d.outcome, Some(crate::games::Outcome::Ok(_)))).count();
            self.ui.log.push(format!("— {how}: {made} of {} games on the card", self.on_card.len()));
            self.ui.message = Some(if ok { format!("Card built: {made} games") } else { format!("The build {how}") });
            // Flash the taskbar button and say so, for a user looking elsewhere.
            if let Some(g) = &self.gpu {
                let (title, body) = if ok {
                    let n = self.on_card.len();
                    let games = if n == 1 { "game is" } else { "games are" };
                    ("Card built".to_string(), format!("{made} of {n} {games} on the card."))
                } else {
                    ("The card wasn't built".to_string(), format!("The build {how}. The log says why."))
                };
                crate::notify::finished(&g.window, &title, &body);
            }
            if let Some(v) = &self.usb_built {
                crate::usb::note(format!("build onto {}: {how}, {made} games", v.display()));
                let _ = crate::usb::save_log(&self.data_dir);
            }
            self.last_build = Some((ok, how));
            self.build = None;
            self.look_for_menu();
        }
    }

    fn redraw(&mut self, event_loop: &ActiveEventLoop) {
        if let Some(answer) = self.sheet.as_mut().and_then(|s| s.poll()) {
            let what = self.sheet.take().map(|s| s.what).unwrap();
            self.picked(what, answer);
        }
        self.poll_build();
        self.poll_usb();
        let (Some(gpu), Some(state)) = (&mut self.gpu, &mut self.egui_state) else {
            return;
        };
        let raw = state.take_egui_input(&gpu.window);
        let mut actions = Vec::new();
        let info = Info {
            dumps: &self.dumps,
            building: self.build.is_some(),
            last_build: self.last_build.as_ref(),
            research: self.research.clone(),
            nativescan: self.nativescan.clone(),
            bios: self.bios.clone(),
            menu_on_card: self.menu_on_card.as_deref(),
            ribbit_folders: &self.ribbit_folders,
            usb: self.usb.as_ref(),
            usb_busy: self.usb_job.as_ref().map(|(what, _)| what.as_str()),
            usb_built: self.usb_built.as_deref(),
        };
        let (ui_state, settings) = (&mut self.ui, &mut self.settings);
        let out = self.egui_ctx.run_ui(raw, |ui| ui::draw(ui, ui_state, settings, &info, &mut actions));
        state.handle_platform_output(&gpu.window, out.platform_output);
        let ppp = out.pixels_per_point;
        let jobs = self.egui_ctx.tessellate(out.shapes, ppp);
        let mut deltas = out.textures_delta;
        let rendered = gpu.render(&jobs, &deltas, ppp);
        // Handled by `render` (debug builds of egui panic when an unhandled
        // delta is dropped).
        deltas.clear();
        if let Err(e) = rendered {
            self.fatal = Some(e);
            event_loop.exit();
            return;
        }
        // egui's next frame: now (an animation, a click's effects), later
        // (a tooltip), or when something happens.
        if let Some(v) = out.viewport_output.get(&egui::ViewportId::ROOT) {
            if v.repaint_delay.is_zero() {
                gpu.window.request_redraw();
            } else if let Some(at) = Instant::now().checked_add(v.repaint_delay) {
                event_loop.set_control_flow(ControlFlow::WaitUntil(at));
            }
        }
        // What the clicks did shows at once (not on the next mouse move).
        if !actions.is_empty() {
            gpu.window.request_redraw();
        }
        for a in actions {
            self.act(a);
        }
        if std::mem::take(&mut self.restart_for_update) {
            // Everything saved before the new version starts and reads it.
            self.save_settings();
            match crate::install::restart() {
                Ok(()) => {
                    event_loop.exit();
                    return;
                }
                Err(e) => self.ui.problem(
                    "The update is installed",
                    format!("LeapLoader couldn't restart by itself: close it and open it again to use the new version. ({e})"),
                ),
            }
        }
        self.find_tools();
        if self.build.is_some() || self.sheet.is_some() || self.usb_job.is_some() {
            // Keep the spinner turning while mkcard works, and look for the
            // file dialog's answer.
            event_loop.set_control_flow(ControlFlow::WaitUntil(Instant::now() + std::time::Duration::from_millis(100)));
        }
    }
}

impl ApplicationHandler<Wake> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.gpu.is_some() {
            return;
        }
        // The start size, or less on a small screen (at 150% scaling a
        // 1080p screen is 1280 x 720 points): the whole window, with its
        // edges to resize by, stays on the screen.
        let size = event_loop.primary_monitor().map_or(START_WINDOW, |m| {
            let screen = m.size().to_logical::<f64>(m.scale_factor());
            winit::dpi::LogicalSize::new(
                START_WINDOW.width.min(screen.width * 0.9).max(MIN_WINDOW.width),
                START_WINDOW.height.min(screen.height * 0.85).max(MIN_WINDOW.height),
            )
        });
        let attrs = Window::default_attributes()
            .with_title(APP_NAME)
            .with_inner_size(size)
            .with_resizable(true)
            .with_min_inner_size(MIN_WINDOW)
            .with_window_icon(crate::icon::window_icon());
        #[cfg(windows)]
        let attrs = {
            use winit::platform::windows::WindowAttributesExtWindows as _;
            attrs.with_taskbar_icon(crate::icon::taskbar_icon())
        };
        match event_loop
            .create_window(attrs)
            .context("creating window")
            .and_then(|w| Gpu::new(Arc::new(w), Some(&self.data_dir.join("gpu-setup-crashed.txt"))))
        {
            Ok(gpu) => {
                self.egui_state = Some(egui_winit::State::new(
                    self.egui_ctx.clone(),
                    egui::ViewportId::ROOT,
                    &gpu.window,
                    Some(gpu.window.scale_factor() as f32),
                    None,
                    None,
                ));
                // The icons again, now the window is set up: the taskbar kept
                // a blank button when they came only with the window's
                // creation (seen on Windows 11).
                gpu.window.set_window_icon(crate::icon::window_icon());
                #[cfg(windows)]
                {
                    use winit::platform::windows::WindowExtWindows as _;
                    gpu.window.set_taskbar_icon(crate::icon::taskbar_icon());
                }
                gpu.window.request_redraw();
                self.gpu = Some(gpu);
            }
            Err(e) => {
                self.fatal = Some(e);
                event_loop.exit();
            }
        }
    }

    fn new_events(&mut self, _event_loop: &ActiveEventLoop, cause: StartCause) {
        if let (StartCause::ResumeTimeReached { .. }, Some(g)) = (cause, &self.gpu) {
            g.window.request_redraw();
        }
    }

    fn user_event(&mut self, _event_loop: &ActiveEventLoop, _: Wake) {
        if let Some(g) = &self.gpu {
            g.window.request_redraw();
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let repaint = match (&mut self.egui_state, &self.gpu) {
            (Some(st), Some(g)) => st.on_window_event(&g.window, &event).repaint,
            _ => false,
        };
        match event {
            WindowEvent::CloseRequested => {
                if let Some(g) = &self.gpu {
                    crate::notify::clear(&g.window);
                }
                // mkcard stops with the app (its files so far stay).
                if let Some(b) = &self.build {
                    b.stop();
                }
                event_loop.exit();
            }
            WindowEvent::Resized(size) => {
                if let Some(g) = &mut self.gpu {
                    g.resize(size);
                }
            }
            WindowEvent::DroppedFile(path) => {
                if self.build.is_none() {
                    let paths = if path.is_dir() { crate::games::dumps_in(&path) } else { vec![path] };
                    self.add_dumps(paths, true);
                    self.save_settings();
                }
            }
            WindowEvent::RedrawRequested => {
                event_loop.set_control_flow(ControlFlow::Wait);
                self.redraw(event_loop);
                return;
            }
            _ => {}
        }
        if repaint && let Some(g) = &self.gpu {
            g.window.request_redraw();
        }
    }
}

/// Shows `path` in the system's file manager (Ribbit's `open_folder`).
fn open_folder(path: &Path) {
    #[cfg(windows)]
    let program = "explorer";
    #[cfg(target_os = "macos")]
    let program = "open";
    #[cfg(not(any(windows, target_os = "macos")))]
    let program = "xdg-open";
    if let Err(e) = std::process::Command::new(program).arg(path).spawn() {
        eprintln!("could not open {}: {e}", path.display());
    }
}
