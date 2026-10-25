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
    /// Sets up the window for drawing: the system's usual backends first,
    /// then OpenGL, then a software renderer (an old or missing GPU driver).
    pub fn new(window: Arc<Window>) -> Result<Self> {
        let mut last = anyhow::anyhow!("no backend tried");
        for (backends, software) in
            [(wgpu::Backends::PRIMARY, false), (wgpu::Backends::GL, false), (wgpu::Backends::all(), true)]
        {
            match Self::connect(&window, backends, software) {
                Ok(gpu) => return Ok(gpu),
                Err(e) => {
                    eprintln!("GPU ({backends:?}, software: {software}) cannot show the window: {e:#}");
                    last = e;
                }
            }
        }
        Err(last.context("no GPU can draw to the window"))
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
        let scope = device.push_error_scope(wgpu::ErrorFilter::Validation);
        surface.configure(&device, &config);
        if let Some(e) = pollster::block_on(scope.pop()) {
            anyhow::bail!("{:?} window setup failed: {e}", adapter.get_info().backend);
        }
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
