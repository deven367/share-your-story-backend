"""Social sharing — generates Reels/Shorts video and MP3 audiobook."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import llm
from PIL import Image, ImageDraw, ImageFont

from storyteller.tts import synthesize, TTSError

logger = logging.getLogger(__name__)

MODEL_ID = "claude-opus-4.6"

# ElevenLabs voice IDs
VOICE_FEMALE = "21m00Tcm4TlvDq8ikWAM"   # Rachel — warm, calm
VOICE_MALE   = "pNInz6obpgDQGcFmaJgB"   # Adam — clear, natural

# Video dimensions — 9:16 for Reels / Shorts
VIDEO_W = 1080
VIDEO_H = 1920
MAX_DURATION = 90  # seconds

# Gradient palette — terracotta warm tones matching the app
GRADIENT_TOP    = (62,  36,  25)   # deep brown
GRADIENT_BOTTOM = (180, 90,  60)   # terracotta

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _guess_voice(person_name: str) -> str:
    """Heuristic: pick female voice for common female names, male otherwise."""
    female_names = {
        "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth",
        "susan", "jessica", "sarah", "karen", "lisa", "nancy", "betty",
        "margaret", "helen", "sandra", "donna", "carol", "ruth", "sharon",
        "michelle", "dorothy", "laura", "alice", "emily", "anna", "grace",
        "emma", "sophia", "olivia", "ava", "isabella", "mia", "amelia",
        "charlotte", "harper", "evelyn", "abigail", "ella", "aria",
        "priya", "ananya", "divya", "pooja", "neha", "shreya", "nisha",
        "rekha", "sunita", "kavya", "meera", "lakshmi", "deepa", "radha",
    }
    first = person_name.strip().split()[0].lower()
    return VOICE_FEMALE if first in female_names else VOICE_MALE


def _build_gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    r1, g1, b1 = GRADIENT_TOP
    r2, g2, b2 = GRADIENT_BOTTOM
    for y in range(h):
        t = y / h
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _render_text_frame(
    text: str,
    person_name: str,
    title: str | None = None,
    watermark: bool = True,
) -> Image.Image:
    img = _build_gradient(VIDEO_W, VIDEO_H)
    draw = ImageDraw.Draw(img)

    padding = 90
    text_w = VIDEO_W - padding * 2

    title_font  = _get_font(72)
    body_font   = _get_font(52)
    small_font  = _get_font(38)
    wm_font     = _get_font(34)

    # Title / person name header
    header = f"{person_name}\u2019s Story"
    if title:
        header = title
    draw.text((VIDEO_W // 2, 180), header, font=title_font, fill=(255, 220, 190), anchor="mm")

    # Ornament
    draw.text((VIDEO_W // 2, 270), "\u2727 \u00B7 \u2727 \u00B7 \u2727", font=small_font, fill=(200, 160, 130), anchor="mm")

    # Body text — wrapped
    lines = _wrap_text(text, body_font, text_w, draw)
    line_h = 72
    total_h = len(lines) * line_h
    y = (VIDEO_H - total_h) // 2 - 40
    for line in lines:
        draw.text((VIDEO_W // 2, y), line, font=body_font, fill=(255, 245, 235), anchor="mm")
        y += line_h

    # Watermark
    if watermark:
        draw.text(
            (VIDEO_W - padding, VIDEO_H - 80),
            "Share Your Story",
            font=wm_font,
            fill=(200, 160, 130),
            anchor="rm",
        )

    return img


# ── Public API ───────────────────────────────────────────────────────────────

def generate_summary(conversations: list[dict], person_name: str) -> str:
    """Generate a 3-4 sentence warm social-media summary. Preserves all context."""
    transcript = ""
    for conv in conversations:
        for msg in conv.get("messages", []):
            if msg["role"] == "user":
                text = msg.get("polished") or msg.get("content", "")
                transcript += text + " "

    transcript = transcript.strip()
    if not transcript:
        return f"{person_name} shared their story."

    model = llm.get_model(MODEL_ID)
    system = f"""You are writing a 3-4 sentence social media caption for {person_name}'s life story.

Rules:
- Write in third person ("John grew up…")
- Warm, personal, and human — like a loving family tribute
- Do NOT change, invent, or embellish any facts. Only use what is in the transcript.
- No hashtags, no emojis, no promotional language
- End with one sentence that invites others to share their own story
- Return ONLY the caption text, nothing else"""

    try:
        response = model.prompt(transcript[:4000], system=system)
        return response.text().strip()
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return f"{person_name} shared their story — a collection of memories, moments, and the little things that make a life."


def synthesize_summary(summary: str, person_name: str, voice_id: str | None = None) -> bytes:
    """TTS for the social summary text only."""
    vid = voice_id or _guess_voice(person_name)
    return synthesize(summary, voice_id=vid)


def generate_audiobook(conversations: list[dict], person_name: str, voice_id: str | None = None) -> bytes:
    """Generate a full MP3 audiobook from all chapter conversations."""
    vid = voice_id or _guess_voice(person_name)

    # Build narration script from all polished user messages
    parts: list[str] = []
    for conv in conversations:
        chapter_title = conv.get("chapter_title")
        if chapter_title:
            parts.append(f"Chapter: {chapter_title}.")
        for msg in conv.get("messages", []):
            if msg["role"] == "user":
                text = msg.get("polished") or msg.get("content", "")
                if text.strip():
                    parts.append(text.strip())

    if not parts:
        raise TTSError("No story content to narrate.")

    full_script = "\n\n".join(parts)

    # ElevenLabs has a ~5000 char limit per call — chunk if needed
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 2 > 4500 and current:
            chunks.append(current.strip())
            current = part
        else:
            current = (current + "\n\n" + part).strip() if current else part
    if current:
        chunks.append(current.strip())

    audio_parts: list[bytes] = []
    for chunk in chunks:
        audio_parts.append(synthesize(chunk, voice_id=vid))

    # Concatenate raw MP3 bytes (valid for simple playback)
    return b"".join(audio_parts)


def _render_overlay(summary: str, person_name: str, title: str | None = None) -> Image.Image:
    """Render a transparent RGBA overlay with text for compositing onto the video."""
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    padding = 60
    text_w = VIDEO_W - padding * 2
    bar_y = 1340
    bar_h = 540

    # Semi-transparent dark bar at the bottom
    bar = Image.new("RGBA", (VIDEO_W, bar_h), (0, 0, 0, 160))
    img.paste(bar, (0, bar_y), bar)

    title_font = _get_font(56)
    body_font  = _get_font(36)
    wm_font    = _get_font(28)

    header = title or f"{person_name}\u2019s Story"

    # Title centred
    draw.text((VIDEO_W // 2, bar_y + 50), header, font=title_font, fill=(255, 255, 255, 255), anchor="mm")

    # Body wrapped
    words = summary.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=body_font)
        if bbox[2] > text_w and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y = bar_y + 100
    for line in lines:
        draw.text((padding, y), line, font=body_font, fill=(240, 240, 240, 230))
        y += 46
        if y > bar_y + bar_h - 60:
            break

    # Watermark
    draw.text((VIDEO_W - padding, VIDEO_H - 50), "Share Your Story",
              font=wm_font, fill=(200, 200, 200, 140), anchor="rm")

    return img


def generate_reel(
    summary: str,
    audio_bytes: bytes,
    person_name: str,
    title: str | None = None,
    music_path: Path | None = None,
    bg_video_path: Path | None = None,
) -> bytes:
    """Generate a 9:16 MP4 Reel with background video, Pillow text overlay, and narration audio."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Write narration audio
        audio_path = tmp / "narration.mp3"
        audio_path.write_bytes(audio_bytes)

        # Get narration duration
        dur_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True,
        )
        try:
            audio_dur = float(dur_result.stdout.strip())
        except ValueError:
            audio_dur = MAX_DURATION

        video_dur = min(audio_dur, MAX_DURATION)

        # Render text overlay as transparent PNG via Pillow (no drawtext needed)
        overlay = _render_overlay(summary, person_name, title=title)
        overlay_path = tmp / "overlay.png"
        overlay.save(overlay_path)

        # Mix narration + optional background music
        music_file = music_path or (ASSETS_DIR / "music.mp3")
        has_music = music_file.exists()

        if has_music:
            mixed_audio = tmp / "mixed.mp3"
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-i", str(music_file),
                "-filter_complex",
                "[1:a]volume=0.15[music];[0:a][music]amix=inputs=2:duration=first[out]",
                "-map", "[out]",
                "-t", str(video_dur),
                str(mixed_audio),
            ], check=True, capture_output=True)
            final_audio = mixed_audio
        else:
            final_audio = audio_path

        output_path = tmp / "reel.mp4"
        bg_video = bg_video_path or (ASSETS_DIR / "background.mp4")

        if bg_video.exists():
            # Scale/crop bg video to 9:16, overlay the PNG, mix in audio
            subprocess.run([
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", str(bg_video),
                "-i", str(overlay_path),
                "-i", str(final_audio),
                "-filter_complex",
                f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H}[bg];"
                f"[bg][1:v]overlay=0:0[v]",
                "-map", "[v]",
                "-map", "2:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-t", str(video_dur),
                "-shortest",
                str(output_path),
            ], check=True, capture_output=True)
        else:
            # Fallback: gradient still frame + overlay
            frame = _build_gradient(VIDEO_W, VIDEO_H).convert("RGBA")
            frame.alpha_composite(overlay)
            frame_path = tmp / "frame.png"
            frame.convert("RGB").save(frame_path)
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(frame_path),
                "-i", str(final_audio),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-t", str(video_dur),
                "-vf", f"scale={VIDEO_W}:{VIDEO_H}",
                "-shortest",
                str(output_path),
            ], check=True, capture_output=True)

        return output_path.read_bytes()
