"""
Sprite / GIF -> Video  (Streamlit web app)

- Reads a GIF (and PNG/APNG/WebP animations) directly.
- Reads .ase / .aseprite via your installed LibreSprite/Aseprite CLI.
- Converts to MP4 / MKV / WebM with a loop count and a 1x-20x pixel-art scale.
- FFmpeg is bundled via the imageio-ffmpeg package -- no separate install needed.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import shutil
import subprocess
import tempfile

import streamlit as st
import imageio_ffmpeg

# FFmpeg comes bundled with imageio-ffmpeg (downloaded into the package on first use).
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

st.set_page_config(page_title="Sprite / GIF to Video", page_icon="🎞️", layout="centered")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def find_aseprite_cli():
    """Best-effort auto-detect of a LibreSprite/Aseprite binary for .aseprite files."""
    candidates = [
        "/Applications/LibreSprite.app/Contents/MacOS/libresprite",
        "/Applications/Aseprite.app/Contents/MacOS/aseprite",
        shutil.which("libresprite"),
        shutil.which("aseprite"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def build_vf(scale):
    # scale=...:flags=neighbor -> crisp pixel-art upscaling (no blur)
    # pad -> round width/height up to even numbers (required by yuv420p)
    if scale > 1:
        return ("scale=iw*%d:ih*%d:flags=neighbor,"
                "pad=ceil(iw/2)*2:ceil(ih/2)*2" % (scale, scale))
    return "pad=ceil(iw/2)*2:ceil(ih/2)*2"


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
st.title("🎞️ Sprite / GIF → Video")
st.caption("Turn a GIF or Aseprite animation into a video, with looping and crisp "
           "pixel-art scaling.")

with st.sidebar:
    st.header("Settings")
    aseprite_cli = st.text_input(
        "LibreSprite / Aseprite path",
        value=find_aseprite_cli(),
        help="Only needed to read .ase/.aseprite files. GIFs don't need this.",
    )
    st.markdown("**FFmpeg:** bundled ✅")
    with st.expander("Why a GIF step for Aseprite?"):
        st.write(
            "FFmpeg can't read .aseprite directly, so the app asks your "
            "LibreSprite/Aseprite to render the sprite to a temporary GIF "
            "(frame timing preserved), then encodes that. GIFs you upload skip "
            "this step entirely."
        )

uploaded = st.file_uploader(
    "Upload a GIF or Aseprite file",
    type=["gif", "ase", "aseprite", "png", "webp", "apng"],
)

c1, c2 = st.columns(2)
with c1:
    scale = st.slider("Scale (×)", min_value=1, max_value=20, value=4,
                      help="Nearest-neighbor upscale — keeps pixels sharp.")
with c2:
    loop = st.number_input("Loop count", min_value=1, max_value=999, value=1, step=1,
                           help="How many times the animation plays (1 = once).")

fmt = st.selectbox("Output format", ["mp4", "mkv", "webm"], index=0)

go = st.button("Convert to video", type="primary", disabled=uploaded is None)


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #
if go and uploaded is not None:
    workdir = tempfile.mkdtemp(prefix="sprite2video_")
    in_name = uploaded.name
    in_ext = os.path.splitext(in_name)[1].lower().lstrip(".")
    in_path = os.path.join(workdir, in_name)
    with open(in_path, "wb") as f:
        f.write(uploaded.getbuffer())

    # Preview the source (GIFs/PNGs/WebP render in the browser).
    if in_ext in ("gif", "png", "webp", "apng"):
        st.image(in_path, caption="Original", width=240)

    # Step 1: make sure we have something FFmpeg can read (a GIF).
    gif_path = in_path
    if in_ext in ("ase", "aseprite"):
        if not aseprite_cli or not os.path.exists(aseprite_cli):
            st.error(
                "To read .aseprite files, set a valid LibreSprite/Aseprite path in "
                "the sidebar — or export a GIF from your editor and upload that instead."
            )
            st.stop()
        gif_path = os.path.join(workdir, "frames.gif")
        with st.spinner("Rendering Aseprite frames…"):
            r = run([aseprite_cli, "-b", in_path, "--save-as", gif_path])
        if not os.path.exists(gif_path):
            st.error("Couldn't render the .aseprite file via the CLI.")
            if r.stderr or r.stdout:
                st.code((r.stderr or r.stdout)[-2000:])
            st.info("Workaround: open it in LibreSprite, File ▸ Save a Copy As ▸ .gif, "
                    "then upload that GIF here.")
            st.stop()

    # Step 2: encode with FFmpeg.
    out_path = os.path.join(workdir, "output.%s" % fmt)
    cmd = [FFMPEG, "-y"]
    if int(loop) > 1:
        cmd += ["-stream_loop", str(int(loop) - 1)]
    cmd += ["-i", gif_path, "-vf", build_vf(int(scale))]
    if fmt == "webm":
        cmd += ["-pix_fmt", "yuv420p", "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30"]
    else:  # mp4 / mkv
        cmd += ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "23", "-preset", "veryfast"]
    cmd += [out_path]

    with st.spinner("Encoding video…"):
        r = run(cmd)

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        st.error("FFmpeg failed to produce a video.")
        st.code(" ".join(cmd))
        if r.stderr:
            st.code(r.stderr[-3000:])
        st.stop()

    st.success("Done! 🎉")
    with open(out_path, "rb") as f:
        data = f.read()

    # MP4/WebM play inline; MKV browsers can't preview, but download still works.
    if fmt in ("mp4", "webm"):
        st.video(data)

    mime = {"mp4": "video/mp4", "webm": "video/webm", "mkv": "video/x-matroska"}[fmt]
    base = os.path.splitext(in_name)[0]
    st.download_button("⬇️ Download video", data=data,
                       file_name="%s.%s" % (base, fmt), mime=mime)

    st.caption("Settings used:  scale ×%d,  loop %d,  %s" % (int(scale), int(loop), fmt.upper()))
