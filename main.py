"""
Sprite / GIF → Video  v2  (Streamlit web app)

A clean, professional "studio" aesthetic — opposite direction from v1's
dark pixel-art look. Light surfaces, green accent, sidebar-less layout,
drag-and-drop-first workflow.

Supports:
  - GIF, APNG, WebP animations (direct FFmpeg encode)
  - PNG sprite sheets  → auto-slice by row/column grid → assembled GIF → video
  - .ase / .aseprite   → LibreSprite/Aseprite CLI → GIF → video

Output: MP4 · MKV · WebM  with loop count, scale, FPS control.
FFmpeg bundled via imageio-ffmpeg — no system install required.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import shutil
import subprocess
import tempfile
import time
import math

import streamlit as st
import imageio_ffmpeg
from PIL import Image, ImageSequence, ImageDraw

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

st.set_page_config(
    page_title="Sprite Studio · GIF → Video",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS  —  clean studio / light theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Overall background ── */
.stApp { background: #f5f7f5; }

/* ── Top header bar ── */
.studio-header {
    background: #ffffff;
    border-bottom: 1px solid #e2e8e2;
    padding: 0.9rem 2rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: -1rem -1rem 1.5rem -1rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.studio-logo {
    width: 32px; height: 32px;
    background: #1a7a3c;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
}
.studio-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.01em;
}
.studio-subtitle {
    font-size: 0.78rem;
    color: #6b7280;
    margin-left: 0.5rem;
}
.studio-badge {
    margin-left: auto;
    background: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
}

/* ── Cards ── */
.card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #374151;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.card-title .step-badge {
    background: #1a7a3c;
    color: #fff;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 0.68rem;
    letter-spacing: 0.04em;
}

/* ── Meta grid ── */
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 0.6rem;
    margin: 0.8rem 0;
}
.meta-cell {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 0.55rem 0.8rem;
}
.meta-cell .label {
    font-size: 0.68rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}
.meta-cell .value {
    font-size: 0.95rem;
    font-family: 'JetBrains Mono', monospace;
    color: #111827;
    font-weight: 500;
    margin-top: 1px;
}

/* ── Summary row ── */
.summary-row {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #065f46;
    margin: 0.8rem 0 0 0;
    line-height: 1.7;
}
.summary-row b { color: #14532d; }

/* ── Output result card ── */
.result-card {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    margin: 0.8rem 0;
    font-size: 0.82rem;
    color: #166534;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.9;
}
.result-card b { color: #14532d; }
.result-card .ok { color: #16a34a; font-weight: 700; }

/* ── Error card ── */
.err-card {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    border-radius: 8px;
    padding: 0.8rem 1.1rem;
    font-size: 0.82rem;
    color: #991b1b;
    font-family: 'JetBrains Mono', monospace;
    margin: 0.5rem 0;
}

/* ── Buttons ── */
.stButton > button {
    background: #1a7a3c;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 0.55rem 1.4rem;
    transition: background 0.15s;
    box-shadow: 0 1px 3px rgba(26,122,60,0.35);
}
.stButton > button:hover { background: #15692f; }
.stButton > button:active { background: #0f4d23; }

.stDownloadButton > button {
    background: #ffffff;
    color: #1a7a3c;
    border: 2px solid #1a7a3c;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88rem;
    transition: all 0.15s;
}
.stDownloadButton > button:hover {
    background: #f0fdf4;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #f3f4f6;
    border-radius: 8px;
    padding: 3px;
    gap: 3px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    font-size: 0.83rem;
    font-weight: 500;
    padding: 5px 16px;
    color: #6b7280;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #1a7a3c !important;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* ── Sliders and inputs ── */
[data-baseweb="slider"] > div:first-child { background: #d1fae5; }
[data-baseweb="thumb"] { background: #1a7a3c !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #d1fae5;
    border-radius: 10px;
    background: #f9fffe;
}
[data-testid="stFileUploader"]:hover {
    border-color: #6ee7b7;
}

/* ── Selectbox / number input ── */
[data-baseweb="select"] > div:first-child {
    border-color: #d1d5db;
    border-radius: 8px;
    background: #ffffff;
}

/* ── Frame strip thumbnails ── */
.frame-label {
    text-align: center;
    font-size: 0.65rem;
    color: #9ca3af;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 2px;
}

/* ── Sidebar collapsed gutter ── */
section[data-testid="stSidebar"] { display: none; }

/* ── Streamlit default overrides ── */
.stSuccess { background: #f0fdf4 !important; border-left: 4px solid #22c55e !important; }
.stError   { background: #fef2f2 !important; border-left: 4px solid #ef4444 !important; }
.stInfo    { background: #eff6ff !important; border-left: 4px solid #3b82f6 !important; }
.stWarning { background: #fffbeb !important; border-left: 4px solid #f59e0b !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_aseprite_cli() -> str:
    candidates = [
        "/Applications/LibreSprite.app/Contents/MacOS/libresprite",
        "/Applications/Aseprite.app/Contents/MacOS/aseprite",
        "/usr/bin/aseprite", "/usr/local/bin/aseprite",
        "/usr/bin/libresprite", "/usr/local/bin/libresprite",
        shutil.which("aseprite"),
        shutil.which("libresprite"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""


def run_cmd(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def even(n: int) -> int:
    return n + (n % 2)


def build_vf(scale: int, fps: int = None) -> str:
    parts = []
    if fps and fps > 0:
        parts.append("fps=%d" % fps)
    if scale > 1:
        parts.append("scale=iw*%d:ih*%d:flags=neighbor" % (scale, scale))
    parts.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
    return ",".join(parts)


def fmt_size(n_bytes: int) -> str:
    if n_bytes < 1024:       return "%d B" % n_bytes
    if n_bytes < 1024**2:    return "%.1f KB" % (n_bytes / 1024)
    return "%.2f MB" % (n_bytes / 1024**2)


def get_anim_info(path: str) -> dict:
    info = {"frames": 0, "width": 0, "height": 0, "fps": None, "duration_ms": []}
    try:
        with Image.open(path) as img:
            info["width"], info["height"] = img.size
            durations = []
            for frame in ImageSequence.Iterator(img):
                info["frames"] += 1
                durations.append(frame.info.get("duration", 0))
            info["duration_ms"] = durations
            total = sum(durations)
            if total > 0 and info["frames"] > 1:
                info["fps"] = round(1000 / (total / info["frames"]), 2)
    except Exception:
        pass
    return info


def get_frame_strip(path: str, max_n: int = 10) -> list:
    frames = []
    try:
        with Image.open(path) as img:
            total = getattr(img, "n_frames", 1)
            step = max(1, total // max_n)
            for i in range(0, total, step):
                img.seek(i)
                frames.append(img.convert("RGBA").copy())
                if len(frames) >= max_n:
                    break
    except Exception:
        pass
    return frames


def slice_spritesheet(img: Image.Image, rows: int, cols: int,
                      frame_w: int = None, frame_h: int = None,
                      frame_dur_ms: int = 100) -> list:
    """Slice a static sprite sheet PNG into individual PIL frames."""
    sw, sh = img.size
    fw = frame_w or (sw // cols)
    fh = frame_h or (sh // rows)
    frames = []
    for r in range(rows):
        for c in range(cols):
            x, y = c * fw, r * fh
            if x + fw > sw or y + fh > sh:
                break
            frame = img.crop((x, y, x + fw, y + fh)).convert("RGBA")
            frames.append(frame)
    return frames


def frames_to_gif(frames: list, out_path: str, frame_dur_ms: int = 100):
    """Save a list of RGBA PIL Images as an animated GIF."""
    if not frames:
        raise ValueError("No frames to save.")
    # Convert to RGBA → palette (P mode) for GIF
    palette_frames = []
    for f in frames:
        p = f.convert("P", palette=Image.ADAPTIVE, colors=256)
        palette_frames.append(p)

    palette_frames[0].save(
        out_path,
        save_all=True,
        append_images=palette_frames[1:],
        loop=0,
        duration=frame_dur_ms,
        optimize=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="studio-header">
  <div class="studio-logo">🟢</div>
  <span class="studio-title">Sprite Studio</span>
  <span class="studio-subtitle">GIF · APNG · WebP · Aseprite · Sprite Sheet → MP4 / MKV / WebM</span>
  <span class="studio-badge">FFmpeg bundled ✓</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Two-column layout
# ─────────────────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([1.15, 1], gap="large")


# ═══════════════════════════════════════════════════════════════════════════ #
#  LEFT COLUMN — Input + Settings
# ═══════════════════════════════════════════════════════════════════════════ #
with left_col:

    # ── Step 1: Source ───────────────────────────────────────────────────── #
    st.markdown("""
    <div class="card">
      <div class="card-title"><span class="step-badge">01</span> SOURCE FILE</div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload your animation or sprite sheet",
        type=["gif", "ase", "aseprite", "png", "webp", "apng"],
        label_visibility="collapsed",
    )
    st.caption("Accepted: GIF · APNG · WebP · PNG sprite sheet · .ase · .aseprite")

    # Aseprite CLI path (shown only when needed)
    if uploaded and uploaded.name.lower().endswith((".ase", ".aseprite")):
        aseprite_cli = st.text_input(
            "LibreSprite / Aseprite binary path",
            value=find_aseprite_cli(),
            placeholder="/usr/bin/aseprite",
            help="Required to decode .ase/.aseprite files.",
        )
    else:
        aseprite_cli = find_aseprite_cli()

    # ── Step 2: Sprite-sheet mode (only for static PNG) ───────────────────── #
    is_sheet = False
    sheet_rows = sheet_cols = 1
    frame_dur_ms = 100

    if uploaded and uploaded.name.lower().endswith(".png"):
        st.markdown("""
        <div class="card" style="margin-top:0.8rem;">
          <div class="card-title"><span class="step-badge">02</span> SPRITE SHEET SLICER</div>
        </div>
        """, unsafe_allow_html=True)

        is_sheet = st.toggle(
            "This PNG is a sprite sheet (slice into frames)",
            value=False,
            help="Enable to split a static sprite sheet grid into individual animation frames.",
        )
        if is_sheet:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                sheet_rows = st.number_input("Rows", min_value=1, max_value=64, value=1, step=1)
            with sc2:
                sheet_cols = st.number_input("Columns", min_value=1, max_value=64, value=4, step=1)
            with sc3:
                frame_dur_ms = st.number_input("Frame ms", min_value=16, max_value=2000, value=100, step=16,
                                               help="Duration per frame in milliseconds.")
            total_frames_est = int(sheet_rows) * int(sheet_cols)
            fps_est = round(1000 / int(frame_dur_ms), 1)
            st.caption("→ %d frames  ·  %.1f FPS" % (total_frames_est, fps_est))

    # ── Step 3: Output settings ───────────────────────────────────────────── #
    step_n = "03" if (uploaded and uploaded.name.lower().endswith(".png")) else "02"
    st.markdown("""
    <div class="card" style="margin-top:0.8rem;">
      <div class="card-title"><span class="step-badge">%s</span> OUTPUT SETTINGS</div>
    </div>
    """ % step_n, unsafe_allow_html=True)

    oc1, oc2 = st.columns(2)
    with oc1:
        scale = st.slider("Scale (×)", 1, 20, 4,
                          help="Nearest-neighbour upscale — pixels stay sharp.")
        loop = st.number_input("Loop count", min_value=1, max_value=999, value=1, step=1)
    with oc2:
        fmt = st.selectbox("Format", ["mp4", "mkv", "webm"], index=0,
                           help="MP4 = universal · WebM = web · MKV = archive")
        fps_force = st.number_input("Force FPS (0 = source)", min_value=0, max_value=120,
                                    value=0, step=1)

    with st.expander("⚙️ Quality settings"):
        qp = st.select_slider("Quality preset",
                              options=["Smallest", "Balanced", "Best"],
                              value="Balanced")
        crf_map = {"Smallest": (32, 42), "Balanced": (23, 30), "Best": (16, 18)}
        crf264, crf_vp9 = crf_map[qp]

        speed = st.select_slider("H.264 encode speed",
                                 options=["veryslow", "slow", "medium", "fast", "veryfast"],
                                 value="veryfast")

    # ── Convert button ───────────────────────────────────────────────────── #
    st.markdown("<br>", unsafe_allow_html=True)
    go = st.button(
        "▶  Convert to Video",
        disabled=(uploaded is None),
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════ #
#  RIGHT COLUMN — Preview + Output
# ═══════════════════════════════════════════════════════════════════════════ #
with right_col:

    # ── Source preview (shown as soon as file is uploaded) ──────────────── #
    if uploaded is not None:
        in_ext = os.path.splitext(uploaded.name)[1].lower().lstrip(".")

        # Write to temp so Pillow / preview can read it
        _tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix="." + in_ext, prefix="spv2_prev_"
        )
        _tmp.write(uploaded.getbuffer())
        _tmp.flush()
        prev_path = _tmp.name
        _tmp.close()

        st.markdown("""
        <div class="card">
          <div class="card-title">👁  PREVIEW</div>
        </div>
        """, unsafe_allow_html=True)

        # -- Animated raster preview --
        if in_ext in ("gif", "png", "webp", "apng"):
            st.image(prev_path, use_container_width=True)
        else:
            st.info("`.aseprite` / `.ase` — preview available after conversion.")

        # -- Metadata --
        if in_ext in ("gif", "webp", "apng") or (in_ext == "png" and not is_sheet):
            info = get_anim_info(prev_path)
        elif in_ext == "png" and is_sheet:
            # Static sheet: get image size only
            try:
                with Image.open(prev_path) as _img:
                    _w, _h = _img.size
                info = {
                    "frames": int(sheet_rows) * int(sheet_cols),
                    "width": _w, "height": _h,
                    "fps": round(1000 / int(frame_dur_ms), 1),
                    "duration_ms": [int(frame_dur_ms)] * (int(sheet_rows) * int(sheet_cols)),
                }
            except Exception:
                info = {"frames": 0, "width": 0, "height": 0, "fps": None, "duration_ms": []}
        else:
            info = {"frames": 0, "width": 0, "height": 0, "fps": None, "duration_ms": []}

        if info["width"]:
            ow = even(info["width"] * scale)
            oh = even(info["height"] * scale)
            total_f = info["frames"] * int(loop)
            dur_list = info["duration_ms"]
            avg_ms   = (sum(dur_list) / len(dur_list)) if dur_list else 100
            est_s    = (total_f * avg_ms) / 1000

            st.markdown("""
            <div class="meta-grid">
              <div class="meta-cell"><div class="label">Frames</div><div class="value">%s</div></div>
              <div class="meta-cell"><div class="label">Source</div><div class="value">%dx%d</div></div>
              <div class="meta-cell"><div class="label">FPS</div><div class="value">%s</div></div>
              <div class="meta-cell"><div class="label">Output</div><div class="value">%dx%d</div></div>
              <div class="meta-cell"><div class="label">File size</div><div class="value">%s</div></div>
              <div class="meta-cell"><div class="label">Est. dur.</div><div class="value">%.1fs</div></div>
            </div>
            """ % (
                info["frames"] or "—",
                info["width"], info["height"],
                str(info["fps"]) if info["fps"] else "—",
                ow, oh,
                fmt_size(len(uploaded.getbuffer())),
                est_s,
            ), unsafe_allow_html=True)

        # Frame strip (animated only)
        if in_ext in ("gif", "webp", "apng"):
            strip = get_frame_strip(prev_path, max_n=8)
            if len(strip) > 1:
                st.markdown("**Frame strip**")
                fcols = st.columns(len(strip))
                for i, (fc, fr) in enumerate(zip(fcols, strip)):
                    fc.image(fr, use_container_width=True)
                    fc.markdown(
                        '<div class="frame-label">#%d</div>' % i,
                        unsafe_allow_html=True,
                    )

        # Sprite sheet grid preview
        if in_ext == "png" and is_sheet and info["width"]:
            st.markdown("**Sheet grid preview** (%d × %d)" % (int(sheet_cols), int(sheet_rows)))
            try:
                with Image.open(prev_path) as _sheet:
                    _preview = _sheet.copy().convert("RGBA")
                    _dw = ImageDraw.Draw(_preview)
                    fw_g = _preview.width // int(sheet_cols)
                    fh_g = _preview.height // int(sheet_rows)
                    for r in range(int(sheet_rows) + 1):
                        y = r * fh_g
                        _dw.line([(0, y), (_preview.width, y)], fill=(0, 200, 80, 180), width=1)
                    for c in range(int(sheet_cols) + 1):
                        x = c * fw_g
                        _dw.line([(x, 0), (x, _preview.height)], fill=(0, 200, 80, 180), width=1)
                    st.image(_preview, use_container_width=True)
            except Exception:
                pass

    else:
        # Placeholder when nothing is uploaded
        st.markdown("""
        <div class="card" style="min-height:320px; display:flex; align-items:center;
             justify-content:center; text-align:center; color:#9ca3af;">
          <div>
            <div style="font-size:3rem; margin-bottom:0.5rem;">🎞️</div>
            <div style="font-size:0.9rem; font-weight:500;">Upload a file to see a preview</div>
            <div style="font-size:0.78rem; margin-top:0.3rem;">GIF · APNG · WebP · PNG sheet · .aseprite</div>
          </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Conversion  — runs in full width below the two columns
# ─────────────────────────────────────────────────────────────────────────────
if go and uploaded is not None:
    in_ext   = os.path.splitext(uploaded.name)[1].lower().lstrip(".")
    in_name  = uploaded.name
    workdir  = tempfile.mkdtemp(prefix="spv2_enc_")
    in_path  = os.path.join(workdir, in_name)

    with open(in_path, "wb") as fh:
        fh.write(uploaded.getbuffer())

    st.divider()
    prog = st.progress(0, text="Starting…")

    # ── A: Sprite sheet PNG → assemble GIF ───────────────────────────── #
    gif_path = in_path

    if in_ext == "png" and is_sheet:
        prog.progress(15, text="🔪  Slicing sprite sheet…")
        try:
            with Image.open(in_path) as _sheet_img:
                frames = slice_spritesheet(
                    _sheet_img,
                    rows=int(sheet_rows),
                    cols=int(sheet_cols),
                    frame_dur_ms=int(frame_dur_ms),
                )
        except Exception as e:
            st.error("Failed to slice sprite sheet: %s" % e)
            st.stop()

        if not frames:
            st.error("No frames were extracted. Check rows/columns settings.")
            st.stop()

        gif_path = os.path.join(workdir, "sheet_assembled.gif")
        prog.progress(30, text="🖼  Assembling %d frames into GIF…" % len(frames))
        try:
            frames_to_gif(frames, gif_path, frame_dur_ms=int(frame_dur_ms))
        except Exception as e:
            st.error("Failed to assemble GIF: %s" % e)
            st.stop()
        st.success("✅  Sprite sheet sliced → %d frames assembled." % len(frames))

    # ── B: .ase/.aseprite → GIF via CLI ──────────────────────────────── #
    elif in_ext in ("ase", "aseprite"):
        if not aseprite_cli or not os.path.exists(aseprite_cli):
            st.error(
                "LibreSprite/Aseprite binary not found. "
                "Set the path in the Source section above, or export a GIF from your editor."
            )
            st.stop()
        gif_path = os.path.join(workdir, "frames.gif")
        prog.progress(20, text="🖌  Rendering Aseprite frames…")
        r = run_cmd([aseprite_cli, "-b", in_path, "--save-as", gif_path])
        if not os.path.exists(gif_path) or os.path.getsize(gif_path) == 0:
            st.error("CLI render failed — no GIF was produced.")
            with st.expander("CLI output"):
                st.code((r.stderr or r.stdout or "")[-2000:])
            st.stop()
        st.success("✅  Aseprite rendered → GIF  (%s)" % fmt_size(os.path.getsize(gif_path)))

    # ── C: FFmpeg encode ──────────────────────────────────────────────── #
    out_path = os.path.join(workdir, "output.%s" % fmt)
    fps_val  = int(fps_force) if int(fps_force) > 0 else None

    cmd = [FFMPEG, "-y"]
    if int(loop) > 1:
        cmd += ["-stream_loop", str(int(loop) - 1)]
    cmd += ["-i", gif_path, "-vf", build_vf(int(scale), fps=fps_val)]

    if fmt == "webm":
        cmd += ["-pix_fmt", "yuv420p", "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf_vp9)]
    else:
        cmd += ["-pix_fmt", "yuv420p", "-c:v", "libx264",
                "-crf", str(crf264), "-preset", speed, "-movflags", "+faststart"]
    cmd += [out_path]

    prog.progress(55, text="⚙️  Encoding with FFmpeg…")
    t0     = time.time()
    result = run_cmd(cmd)
    elapsed = time.time() - t0
    prog.progress(100, text="✅  Done!")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        st.error("FFmpeg failed — no output file produced.")
        with st.expander("FFmpeg command"):
            st.code(" ".join(cmd), language="bash")
        if result.stderr:
            with st.expander("stderr"):
                st.code(result.stderr[-3000:])
        st.stop()

    # ── Result display ────────────────────────────────────────────────── #
    with open(out_path, "rb") as fh:
        video_bytes = fh.read()

    out_sz = fmt_size(os.path.getsize(out_path))
    in_sz  = fmt_size(os.path.getsize(in_path))

    res_left, res_right = st.columns([1.15, 1], gap="large")

    with res_left:
        st.markdown("""
        <div class="result-card">
          <span class="ok">✓ Conversion complete</span><br>
          <b>Format</b>     : %s  (%s)<br>
          <b>Scale</b>      : ×%d<br>
          <b>Loops</b>      : %d<br>
          <b>CRF</b>        : %s<br>
          <b>FPS</b>        : %s<br>
          <b>Input size</b> : %s<br>
          <b>Output size</b>: %s<br>
          <b>Encode time</b>: %.2f s
        </div>
        """ % (
            fmt.upper(),
            "libvpx-vp9" if fmt == "webm" else "libx264",
            int(scale), int(loop),
            str(crf_vp9) if fmt == "webm" else str(crf264),
            ("%d FPS" % int(fps_force)) if int(fps_force) > 0 else "source",
            in_sz, out_sz, elapsed,
        ), unsafe_allow_html=True)

        mime_map = {"mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska"}
        base      = os.path.splitext(in_name)[0]
        dl_name   = "%s_x%d_loop%d.%s" % (base, int(scale), int(loop), fmt)

        st.download_button(
            label="⬇  Download %s  (%s)" % (fmt.upper(), out_sz),
            data=video_bytes,
            file_name=dl_name,
            mime=mime_map[fmt],
            use_container_width=True,
        )

        with st.expander("🔍 FFmpeg command"):
            st.code(" ".join(cmd), language="bash")

    with res_right:
        if fmt in ("mp4", "webm"):
            st.video(video_bytes)
        else:
            st.info("MKV preview not supported in browsers. Download and open in VLC.")

    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#9ca3af; font-size:0.72rem;
            font-family:'JetBrains Mono',monospace; padding:0.3rem 0 0.8rem 0;">
  Sprite Studio v2 &nbsp;·&nbsp; FFmpeg via imageio-ffmpeg &nbsp;·&nbsp; Pillow &nbsp;·&nbsp; Streamlit
</div>
""", unsafe_allow_html=True)
