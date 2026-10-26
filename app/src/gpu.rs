// SPDX-License-Identifier: GPL-3.0-or-later
//! Drawing egui into the window with wgpu: a cut-down copy of Ribbit's
//! crates/ribbit-frontend/src/gpu.rs (its window setup and its tool
//! windows' egui-only drawing; no emulated screen here).

use anyhow::{Context as _, Result};
use std::sync::Arc;
use winit::dpi::PhysicalSize;
use winit::window::Window;

pub struct Gpu {
    pub window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    egui: egui_wgpu::Renderer,
}

impl Gpu {
    /// Sets up the window for drawing (Ribbit's `Gpu::connect`): the
    /// platform's usual API first (or the one `WGPU_BACKEND` names), then on
    /// Windows DirectX 12 on the card, then OpenGL, then on Windows the
    /// software DirectX 12 renderer (WARP, part of Windows 10 and 11) for
    /// graphics chips that offer neither DirectX 12 nor a recent OpenGL.
    ///
    /// A graphics driver that crashes the process while the card is tried
    /// cannot be caught: the window opens, hangs a moment and closes, at every
    /// start (players saw this with Ribbit, then with LeapLoader 0.1.0). So
    /// on Windows `guard` (a file in the data folder) holds the version and
    /// the step to start from. Before a step, the file says to start after
    /// it: a crash in that step is skipped at the next start. A step that
    /// works is written back, so later starts begin there. An update starts
    /// from the first step again. LEAPLOADER_SOFTWARE_GPU goes straight to
    /// software drawing.
    pub fn new(window: Arc<Window>, guard: Option<&std::path::Path>) -> Result<Self> {
        // WSL's Vulkan driver cannot keep a window going (it fails a few
        // frames in), so OpenGL comes first there.
        let wsl = cfg!(target_os = "linux")
            && std::fs::read_to_string("/proc/sys/kernel/osrelease")
                .is_ok_and(|r| r.to_lowercase().contains("microsoft"));
        let usual = if wsl { wgpu::Backends::GL } else { wgpu::Backends::all() };
        let first = wgpu::Backends::from_env().unwrap_or(usual);
        let software = cfg!(windows).then_some((wgpu::Backends::DX12, true));
        let hardware = if std::env::var_os("LEAPLOADER_SOFTWARE_GPU").is_some() && software.is_some() {
            crate::log::line("LEAPLOADER_SOFTWARE_GPU is set: drawing in software");
            vec![]
        } else if software.is_some() {
            vec![(first, false), (wgpu::Backends::DX12, false), (wgpu::Backends::GL, false)]
        } else {
            vec![(first, false), (wgpu::Backends::GL, false)]
        };
        let steps: Vec<_> = hardware.into_iter().chain(software).collect();
        let guard = guard.filter(|_| software.is_some() && steps.len() > 1);
        let version = env!("CARGO_PKG_VERSION");
        let start = guard
            .and_then(|g| std::fs::read_to_string(g).ok())
            .and_then(|t| {
                let (v, step) = t.trim().split_once(' ')?;
                (v == version).then(|| step.parse::<usize>().ok()).flatten()
            })
            .unwrap_or(0)
            .min(steps.len() - 1);
        if start > 0 {
            crate::log::line(&format!(
                "an earlier start ended while setting up the graphics card (its driver crashed?): starting from \
                 GPU {:?} (delete {} to try every way again; an update does too)",
                steps[start],
                guard.map_or_else(Default::default, |g| g.display().to_string())
            ));
        }
        let note = |step: usize| {
            if let Some(g) = guard {
                let _ = std::fs::write(g, format!("{version} {step}"));
            }
        };
        let mut tried = Vec::new();
        let mut last = anyhow::anyhow!("no GPU backend available");
        for (i, &(backends, software)) in steps.iter().enumerate().skip(start) {
            if tried.contains(&(backends, software)) {
                continue;
            }
            tried.push((backends, software));
            note(i + 1);
            // Said before each try: a driver that crashes the process here
            // leaves this as the log's last line.
            crate::log::line(&format!("setting up the window with GPU ({backends:?}, software: {software})"));
            match Self::connect(&window, backends, software) {
                Ok(gpu) => {
                    match guard {
                        Some(g) if i == 0 => drop(std::fs::remove_file(g)),
                        _ => note(i),
                    }
                    if software {
                        crate::log::line("no GPU can draw the window: drawing in software (WARP)");
                    }
                    return Ok(gpu);
                }
                Err(e) => {
                    crate::log::line(&format!(
                        "GPU ({backends:?}, software: {software}) cannot show the window: {e:#}"
                    ));
                    last = e;
                }
            }
        }
        if let Some(g) = guard {
            let _ = std::fs::remove_file(g);
        }
        Err(last.context(format!("no GPU can draw to the window (tried {tried:?})")))
    }

    fn connect(window: &Arc<Window>, backends: wgpu::Backends, software: bool) -> Result<Self> {
        // (OpenGL through EGL needs the display the window is on.)
        let mut desc = wgpu::InstanceDescriptor::new_with_display_handle(Box::new(window.clone()));
        desc.backends = backends;
        let instance = wgpu::Instance::new(desc);
        let surface = instance.create_surface(window.clone()).context("creating surface")?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            compatible_surface: Some(&surface),
            force_fallback_adapter: software,
            ..Default::default()
        }))
        .context("no compatible GPU adapter")?;
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("leaploader"),
            required_limits: wgpu::Limits::downlevel_webgl2_defaults().using_resolution(adapter.limits()),
            ..Default::default()
        }))
        .context("creating GPU device")?;
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .context("surface not supported by adapter")?;
        // egui blends in gamma space and wants a non-sRGB target.
        let caps = surface.get_capabilities(&adapter);
        if let Some(f) = caps.formats.iter().copied().find(|f| !f.is_srgb()) {
            config.format = f;
        }
        // Set up the window and show one blank frame, catching what fails
        // (some drivers say they can present and then fail at the first frame).
        let scope = device.push_error_scope(wgpu::ErrorFilter::Validation);
        surface.configure(&device, &config);
        if let wgpu::CurrentSurfaceTexture::Success(frame) | wgpu::CurrentSurfaceTexture::Suboptimal(frame) =
            surface.get_current_texture()
        {
            let view = frame.texture.create_view(&Default::default());
            let mut encoder = device.create_command_encoder(&Default::default());
            drop(encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("first frame"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            }));
            queue.submit([encoder.finish()]);
            queue.present(frame);
        }
        surface.configure(&device, &config);
        if let Some(e) = pollster::block_on(scope.pop()) {
            anyhow::bail!("{:?} window setup failed: {e}", adapter.get_info().backend);
        }
        let info = adapter.get_info();
        crate::log::line(&format!(
            "graphics: {} ({:?}, driver {}), {:?}",
            info.name, info.backend, info.driver_info, config.present_mode
        ));
        let egui = egui_wgpu::Renderer::new(&device, config.format, egui_wgpu::RendererOptions::default());
        Ok(Self { window: window.clone(), surface, device, queue, config, egui })
    }

    pub fn resize(&mut self, size: PhysicalSize<u32>) {
        if size.width > 0 && size.height > 0 {
            self.config.width = size.width;
            self.config.height = size.height;
            self.surface.configure(&self.device, &self.config);
        }
    }

    /// Draws egui's output (Ribbit's `render_tool`).
    pub fn render(
        &mut self,
        paint_jobs: &[egui::ClippedPrimitive],
        textures: &egui::TexturesDelta,
        pixels_per_point: f32,
    ) -> Result<()> {
        for (id, deltas) in &textures.set {
            for delta in deltas {
                self.egui.update_texture(&self.device, &self.queue, *id, delta);
            }
        }
        use wgpu::CurrentSurfaceTexture as Cst;
        let (output, suboptimal) = match self.surface.get_current_texture() {
            Cst::Success(o) => (o, false),
            Cst::Suboptimal(o) => (o, true),
            Cst::Outdated => {
                self.surface.configure(&self.device, &self.config);
                return Ok(());
            }
            Cst::Timeout | Cst::Occluded => return Ok(()),
            Cst::Lost => anyhow::bail!("GPU surface lost"),
            Cst::Validation => anyhow::bail!("GPU validation error acquiring surface texture"),
        };
        let view = output.texture.create_view(&Default::default());
        let screen =
            egui_wgpu::ScreenDescriptor { size_in_pixels: [self.config.width, self.config.height], pixels_per_point };
        let mut encoder = self.device.create_command_encoder(&Default::default());
        let extra = self.egui.update_buffers(&self.device, &self.queue, &mut encoder, paint_jobs, &screen);
        {
            let mut pass = encoder
                .begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: Some("leaploader window"),
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &view,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    ..Default::default()
                })
                .forget_lifetime();
            self.egui.render(&mut pass, paint_jobs, &screen);
        }
        self.queue.submit(extra.into_iter().chain([encoder.finish()]));
        self.queue.present(output);
        if suboptimal {
            self.surface.configure(&self.device, &self.config);
        }
        for id in &textures.free {
            self.egui.free_texture(id);
        }
        Ok(())
    }
}
