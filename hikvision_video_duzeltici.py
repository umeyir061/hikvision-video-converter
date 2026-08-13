#!/usr/bin/env python3
"""Convert Hikvision camera recordings to WhatsApp-compatible MP4 files."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


TRANSLATIONS: dict[str, dict[str, str]] = {
    "tr": {
        "app_title": "Hikvision Video Düzeltici",
        "app_description": (
            "Hikvision H.265 kayıtlarını gerçek, paylaşılabilir H.264 MP4 "
            "dosyalarına çevirir."
        ),
        "probe_unreadable": "Video bilgisi okunamadı.",
        "probe_invalid": "FFprobe geçersiz bir sonuç döndürdü.",
        "output_not_created": "Çıktı dosyası oluşturulamadı.",
        "validation_h264_failed": "Çıktının H.264 video doğrulaması başarısız oldu.",
        "validation_mp4_failed": "Çıktının MP4 kapsayıcı doğrulaması başarısız oldu.",
        "validation_pixel_failed": "Çıktının renk biçimi doğrulaması başarısız oldu.",
        "ffmpeg_not_found": (
            "FFmpeg bulunamadı. ffmpeg.exe ile ffprobe.exe dosyalarını uygulamanın "
            "yanına koyun veya FFmpeg'i PATH'e ekleyin."
        ),
        "source_not_found": "Seçilen kaynak video bulunamadı.",
        "same_path": "Kaynak ve çıktı dosyası aynı olamaz.",
        "no_video_stream": "Kaynak dosyada video akışı bulunamadı.",
        "source_log": "Kaynak: {codec} — {width}×{height}\n",
        "preparing_log": "Bozuk paketler atlanıyor ve uyumlu MP4 hazırlanıyor...\n",
        "cancelled": "Dönüştürme kullanıcı tarafından iptal edildi.",
        "ffmpeg_failed": "FFmpeg dönüştürmeyi tamamlayamadı.\n{detail}",
        "cli_missing_input": "Hata: Bir kaynak video yolu belirtin.",
        "cli_output_exists": (
            "Hata: Çıktı zaten var: {path}\n--overwrite ile üzerine yazabilirsiniz."
        ),
        "cli_progress": "Dönüştürülüyor: %{percent:3d}",
        "cli_error": "Hata: {error}",
        "cli_completed": "Tamamlandı: {path} ({size})",
        "source_video": "Kaynak video",
        "output_file": "Çıktı dosyası",
        "browse": "Seç…",
        "save": "Kaydet…",
        "size": "Boyut",
        "quality": "Kalite",
        "size_1080p": "WhatsApp için önerilen (en fazla 1080p)",
        "size_720p": "Daha küçük dosya (en fazla 720p)",
        "size_original": "Özgün çözünürlüğü koru",
        "quality_balanced": "Dengeli — önerilen",
        "quality_high": "Yüksek kalite",
        "quality_small": "Küçük dosya",
        "select_prompt": "Bir Hikvision videosu seçin.",
        "cancel": "İptal",
        "fix_video": "Videoyu Düzelt",
        "select_video_title": "Hikvision videosunu seçin",
        "video_files": "Video dosyaları",
        "all_files": "Tüm dosyalar",
        "video_ready": "Video seçildi. Dönüştürmeye hazır.",
        "selected_file_log": "Seçilen dosya: {name}\n",
        "save_video_title": "Düzeltilmiş videoyu kaydedin",
        "mp4_video": "MP4 video",
        "invalid_path": "Dosya yolu geçerli değil.",
        "select_valid_source": "Lütfen geçerli bir kaynak video seçin.",
        "overwrite_question": "Bu çıktı zaten var:\n{path}\n\nÜzerine yazılsın mı?",
        "starting": "Dönüştürme başlatılıyor…",
        "converting": "Video dönüştürülüyor… %{percent}",
        "completed_status": "Tamamlandı — video paylaşılmaya hazır.",
        "validation_success_log": "\nDoğrulama başarılı: MP4 / H.264 / yuv420p\n",
        "output_log": "Çıktı: {resolution}, {size}\n{path}\n",
        "success_question": (
            "Video başarıyla düzeltildi.\n\n{resolution} — {size}\n\n"
            "Çıktının bulunduğu klasör açılsın mı?"
        ),
        "failed_status": "Dönüştürme tamamlanamadı.",
        "error_log": "\nHATA: {error}\n",
        "cancel_question": "Devam eden dönüştürme iptal edilsin mi?",
        "cancelling": "Dönüştürme iptal ediliyor…",
        "close_question": "Dönüştürme sürüyor. İptal edilip uygulama kapatılsın mı?",
        "arg_description": (
            "Hikvision kamera videolarını WhatsApp uyumlu MP4 dosyalarına dönüştürür."
        ),
        "arg_input": "Kaynak video",
        "arg_output": "Çıktı MP4 yolu",
        "arg_size": "Azami çıktı boyutu (varsayılan: 1080p)",
        "arg_cli": "Grafik arayüz olmadan çalıştır",
        "arg_overwrite": "Var olan çıktının üzerine yaz",
    },
    "en": {
        "app_title": "Hikvision Video Fixer",
        "app_description": (
            "Converts Hikvision H.265 recordings to real, shareable H.264 MP4 files."
        ),
        "probe_unreadable": "Could not read the video information.",
        "probe_invalid": "FFprobe returned an invalid result.",
        "output_not_created": "The output file could not be created.",
        "validation_h264_failed": "H.264 video validation failed for the output.",
        "validation_mp4_failed": "MP4 container validation failed for the output.",
        "validation_pixel_failed": "Pixel format validation failed for the output.",
        "ffmpeg_not_found": (
            "FFmpeg was not found. Place ffmpeg.exe and ffprobe.exe next to the "
            "application or add FFmpeg to PATH."
        ),
        "source_not_found": "The selected source video was not found.",
        "same_path": "The source and output paths cannot be the same.",
        "no_video_stream": "No video stream was found in the source file.",
        "source_log": "Source: {codec} — {width}×{height}\n",
        "preparing_log": "Skipping corrupt packets and preparing a compatible MP4...\n",
        "cancelled": "The conversion was cancelled by the user.",
        "ffmpeg_failed": "FFmpeg could not complete the conversion.\n{detail}",
        "cli_missing_input": "Error: Specify a source video path.",
        "cli_output_exists": (
            "Error: Output already exists: {path}\nUse --overwrite to replace it."
        ),
        "cli_progress": "Converting: {percent:3d}%",
        "cli_error": "Error: {error}",
        "cli_completed": "Completed: {path} ({size})",
        "source_video": "Source video",
        "output_file": "Output file",
        "browse": "Browse…",
        "save": "Save…",
        "size": "Size",
        "quality": "Quality",
        "size_1080p": "Recommended for WhatsApp (up to 1080p)",
        "size_720p": "Smaller file (up to 720p)",
        "size_original": "Keep original resolution",
        "quality_balanced": "Balanced — recommended",
        "quality_high": "High quality",
        "quality_small": "Smaller file",
        "select_prompt": "Select a Hikvision video.",
        "cancel": "Cancel",
        "fix_video": "Fix Video",
        "select_video_title": "Select a Hikvision video",
        "video_files": "Video files",
        "all_files": "All files",
        "video_ready": "Video selected. Ready to convert.",
        "selected_file_log": "Selected file: {name}\n",
        "save_video_title": "Save the fixed video",
        "mp4_video": "MP4 video",
        "invalid_path": "The file path is invalid.",
        "select_valid_source": "Select a valid source video.",
        "overwrite_question": "This output already exists:\n{path}\n\nOverwrite it?",
        "starting": "Starting conversion…",
        "converting": "Converting video… {percent}%",
        "completed_status": "Completed — the video is ready to share.",
        "validation_success_log": "\nValidation passed: MP4 / H.264 / yuv420p\n",
        "output_log": "Output: {resolution}, {size}\n{path}\n",
        "success_question": (
            "The video was fixed successfully.\n\n{resolution} — {size}\n\n"
            "Open the folder containing the output?"
        ),
        "failed_status": "The conversion could not be completed.",
        "error_log": "\nERROR: {error}\n",
        "cancel_question": "Cancel the conversion in progress?",
        "cancelling": "Cancelling the conversion…",
        "close_question": "A conversion is in progress. Cancel it and close the application?",
        "arg_description": (
            "Convert Hikvision camera recordings to WhatsApp-compatible MP4 files."
        ),
        "arg_input": "Source video",
        "arg_output": "Output MP4 path",
        "arg_size": "Maximum output size (default: 1080p)",
        "arg_cli": "Run without the graphical interface",
        "arg_overwrite": "Overwrite an existing output",
    },
}


def language_from_windows_id(language_id: int) -> str:
    """Map a Windows language ID to one of the two supported UI languages."""
    primary_language = int(language_id) & 0x03FF
    return "tr" if primary_language == 0x001F else "en"


def detect_language() -> str:
    """Use Turkish only for a Turkish Windows UI; use English everywhere else."""
    override = os.environ.get("HIKVISION_VIDEO_FIXER_LANG", "").lower()
    if override in TRANSLATIONS:
        return override
    if os.name != "nt":
        return "en"
    try:
        import ctypes

        language_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
        return language_from_windows_id(language_id)
    except (AttributeError, OSError, TypeError, ValueError):
        return "en"


LANGUAGE = detect_language()


def t(key: str, **values: object) -> str:
    text = TRANSLATIONS[LANGUAGE][key]
    return text.format(**values) if values else text


class ConversionError(RuntimeError):
    pass


def find_program(name: str) -> str | None:
    """PATH'i ve uygulamanın yanındaki olası FFmpeg konumlarını denetler."""
    executable = f"{name}.exe" if os.name == "nt" else name
    app_dir = Path(__file__).resolve().parent
    candidates = (
        app_dir / executable,
        app_dir / "ffmpeg" / "bin" / executable,
        app_dir / "bin" / executable,
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


def probe_video(path: Path, ffprobe: str) -> dict:
    result = run_capture(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            (
                "format=format_name,duration,size,bit_rate:"
                "stream=index,codec_name,codec_type,width,height,pix_fmt,"
                "r_frame_rate,channels,sample_rate"
            ),
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or t("probe_unreadable")
        raise ConversionError(detail)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ConversionError(t("probe_invalid")) from exc


def first_stream(info: dict, stream_type: str) -> dict | None:
    return next(
        (stream for stream in info.get("streams", []) if stream.get("codec_type") == stream_type),
        None,
    )


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_WhatsApp.mp4")


def scale_filter(max_size: str) -> str:
    filters: dict[str, str] = {
        "1080p": (
            "scale=1920:1080:force_original_aspect_ratio=decrease:"
            "force_divisible_by=2:flags=lanczos:out_range=tv"
        ),
        "720p": (
            "scale=1280:720:force_original_aspect_ratio=decrease:"
            "force_divisible_by=2:flags=lanczos:out_range=tv"
        ),
        "original": (
            "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos:out_range=tv"
        ),
    }
    return f"{filters[max_size]},setsar=1,format=yuv420p"


def conversion_command(
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    max_size: str,
    crf: int,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-fflags",
        "+genpts+discardcorrupt",
        "-err_detect",
        "ignore_err",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-sn",
        "-dn",
        "-vf",
        scale_filter(max_size),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-profile:v",
        "high",
        "-level:v",
        "5.1" if max_size == "original" else "4.1",
        "-pix_fmt",
        "yuv420p",
        "-tag:v",
        "avc1",
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-max_muxing_queue_size",
        "2048",
        "-avoid_negative_ts",
        "make_zero",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output_path),
    ]


def validate_output(path: Path, ffprobe: str) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise ConversionError(t("output_not_created"))
    info = probe_video(path, ffprobe)
    video = first_stream(info, "video")
    format_name = info.get("format", {}).get("format_name", "")
    if not video or video.get("codec_name") != "h264":
        raise ConversionError(t("validation_h264_failed"))
    if "mp4" not in format_name:
        raise ConversionError(t("validation_mp4_failed"))
    if video.get("pix_fmt") != "yuv420p":
        raise ConversionError(t("validation_pixel_failed"))
    return info


def convert(
    input_path: Path,
    output_path: Path,
    max_size: str,
    crf: int,
    on_progress: Callable[[float], None] | None = None,
    on_log: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
    process_callback: Callable[[subprocess.Popen[str] | None], None] | None = None,
) -> dict:
    ffmpeg = find_program("ffmpeg")
    ffprobe = find_program("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ConversionError(t("ffmpeg_not_found"))
    if not input_path.is_file():
        raise ConversionError(t("source_not_found"))
    if input_path.resolve() == output_path.resolve():
        raise ConversionError(t("same_path"))

    source_info = probe_video(input_path, ffprobe)
    video = first_stream(source_info, "video")
    if not video:
        raise ConversionError(t("no_video_stream"))
    try:
        duration = float(source_info.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = conversion_command(ffmpeg, input_path, output_path, max_size, crf)
    if on_log:
        on_log(
            t(
                "source_log",
                codec=video.get("codec_name", "?").upper(),
                width=video.get("width", "?"),
                height=video.get("height", "?"),
            )
        )
        on_log(t("preparing_log"))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    if process_callback:
        process_callback(process)

    recent_lines: list[str] = []
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.strip()
        if stop_event and stop_event.is_set():
            process.terminate()
            process.wait(timeout=10)
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            raise ConversionError(t("cancelled"))

        if "=" in line:
            key, value = line.split("=", 1)
            if key in {"out_time_us", "out_time_ms"} and duration > 0:
                try:
                    # Yeni FFmpeg sürümleri out_time_us ve tarihsel adıyla
                    # out_time_ms değerlerini mikrosaniye cinsinden verir.
                    percent = min(99.5, float(value) / 1_000_000 / duration * 100)
                    if on_progress:
                        on_progress(percent)
                except ValueError:
                    pass
            elif key == "progress" and value == "end" and on_progress:
                on_progress(100)
        elif line:
            recent_lines.append(line)
            recent_lines = recent_lines[-20:]
            if on_log and ("error" in line.lower() or "corrupt" in line.lower()):
                on_log(f"FFmpeg: {line}\n")

    return_code = process.wait()
    if process_callback:
        process_callback(None)
    if return_code != 0:
        detail = "\n".join(recent_lines[-8:])
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConversionError(t("ffmpeg_failed", detail=detail).strip())

    try:
        result = validate_output(output_path, ffprobe)
    except ConversionError:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    if on_progress:
        on_progress(100)
    return result


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def run_cli(args: argparse.Namespace) -> int:
    if not args.input:
        print(t("cli_missing_input"), file=sys.stderr)
        return 2
    input_path = Path(args.input).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve() if args.output else default_output_path(input_path)
    )
    if output_path.exists() and not args.overwrite:
        print(t("cli_output_exists", path=output_path))
        return 2

    last_percent = -1

    def show_progress(percent: float) -> None:
        nonlocal last_percent
        rounded = int(percent)
        if rounded != last_percent:
            print(f"\r{t('cli_progress', percent=rounded)}", end="", flush=True)
            last_percent = rounded

    try:
        convert(
            input_path,
            output_path,
            args.size,
            args.crf,
            on_progress=show_progress,
            on_log=lambda message: print(f"\n{message}", end=""),
        )
    except (ConversionError, OSError) as exc:
        print(f"\n{t('cli_error', error=exc)}", file=sys.stderr)
        return 1
    print(
        f"\n{t('cli_completed', path=output_path, size=human_size(output_path.stat().st_size))}"
    )
    return 0


def run_gui(args: argparse.Namespace) -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    class App:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.app_title = t("app_title")
            self.root.title(self.app_title)
            self.root.geometry("760x550")
            self.root.minsize(680, 500)

            self.input_var = tk.StringVar()
            self.output_var = tk.StringVar()
            self.size_choices = {
                t("size_1080p"): "1080p",
                t("size_720p"): "720p",
                t("size_original"): "original",
            }
            self.quality_choices = {
                t("quality_balanced"): 23,
                t("quality_high"): 20,
                t("quality_small"): 27,
            }
            self.size_var = tk.StringVar(value=t("size_1080p"))
            self.quality_var = tk.StringVar(value=t("quality_balanced"))
            self.status_var = tk.StringVar(value=t("select_prompt"))
            self.progress_var = tk.DoubleVar(value=0)
            self.events: queue.Queue[tuple[str, object]] = queue.Queue()
            self.stop_event = threading.Event()
            self.process: subprocess.Popen[str] | None = None
            self.worker: threading.Thread | None = None
            self.output_was_manual = False

            self._build()
            self.root.protocol("WM_DELETE_WINDOW", self.close)
            self.root.after(100, self._poll_events)

            if args.input:
                self.set_input(Path(args.input))

        def _build(self) -> None:
            style = ttk.Style()
            if "vista" in style.theme_names():
                style.theme_use("vista")

            outer = ttk.Frame(self.root, padding=20)
            outer.pack(fill="both", expand=True)
            outer.columnconfigure(1, weight=1)

            ttk.Label(outer, text=self.app_title, font=("Segoe UI", 18, "bold")).grid(
                row=0, column=0, columnspan=3, sticky="w"
            )
            ttk.Label(
                outer,
                text=t("app_description"),
                foreground="#555555",
            ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 20))

            ttk.Label(outer, text=t("source_video")).grid(
                row=2, column=0, sticky="w", pady=6
            )
            ttk.Entry(outer, textvariable=self.input_var).grid(
                row=2, column=1, sticky="ew", padx=10, pady=6
            )
            ttk.Button(outer, text=t("browse"), command=self.choose_input).grid(
                row=2, column=2, sticky="ew", pady=6
            )

            ttk.Label(outer, text=t("output_file")).grid(
                row=3, column=0, sticky="w", pady=6
            )
            output_entry = ttk.Entry(outer, textvariable=self.output_var)
            output_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
            output_entry.bind("<Key>", lambda _event: setattr(self, "output_was_manual", True))
            ttk.Button(outer, text=t("save"), command=self.choose_output).grid(
                row=3, column=2, sticky="ew", pady=6
            )

            ttk.Label(outer, text=t("size")).grid(row=4, column=0, sticky="w", pady=6)
            ttk.Combobox(
                outer,
                textvariable=self.size_var,
                state="readonly",
                values=tuple(self.size_choices),
            ).grid(row=4, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=6)

            ttk.Label(outer, text=t("quality")).grid(row=5, column=0, sticky="w", pady=6)
            ttk.Combobox(
                outer,
                textvariable=self.quality_var,
                state="readonly",
                values=tuple(self.quality_choices),
            ).grid(row=5, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=6)

            ttk.Separator(outer).grid(
                row=6, column=0, columnspan=3, sticky="ew", pady=(15, 12)
            )
            ttk.Label(outer, textvariable=self.status_var).grid(
                row=7, column=0, columnspan=3, sticky="w", pady=(0, 7)
            )
            ttk.Progressbar(outer, variable=self.progress_var, maximum=100).grid(
                row=8, column=0, columnspan=3, sticky="ew"
            )

            log_frame = ttk.Frame(outer)
            log_frame.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(12, 10))
            log_frame.columnconfigure(0, weight=1)
            log_frame.rowconfigure(0, weight=1)
            outer.rowconfigure(9, weight=1)
            self.log = tk.Text(
                log_frame,
                height=7,
                wrap="word",
                state="disabled",
                font=("Consolas", 9),
                background="#f7f7f7",
                relief="solid",
                borderwidth=1,
            )
            self.log.grid(row=0, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            self.log.configure(yscrollcommand=scrollbar.set)

            buttons = ttk.Frame(outer)
            buttons.grid(row=10, column=0, columnspan=3, sticky="e")
            self.cancel_button = ttk.Button(
                buttons, text=t("cancel"), command=self.cancel, state="disabled"
            )
            self.cancel_button.pack(side="left", padx=(0, 8))
            self.start_button = ttk.Button(
                buttons, text=t("fix_video"), command=self.start
            )
            self.start_button.pack(side="left")

        def choose_input(self) -> None:
            path = filedialog.askopenfilename(
                title=t("select_video_title"),
                filetypes=(
                    (t("video_files"), "*.mp4 *.avi *.dav *.mov *.mkv *.ts *.mpeg *.mpg"),
                    (t("all_files"), "*.*"),
                ),
            )
            if path:
                self.set_input(Path(path))

        def set_input(self, path: Path) -> None:
            path = path.expanduser().resolve()
            self.input_var.set(str(path))
            if not self.output_was_manual:
                self.output_var.set(str(default_output_path(path)))
            self.status_var.set(t("video_ready"))
            self._append_log(t("selected_file_log", name=path.name))

        def choose_output(self) -> None:
            initial = Path(self.output_var.get()) if self.output_var.get() else Path.cwd()
            path = filedialog.asksaveasfilename(
                title=t("save_video_title"),
                initialdir=str(initial.parent),
                initialfile=initial.name,
                defaultextension=".mp4",
                filetypes=((t("mp4_video"), "*.mp4"),),
            )
            if path:
                self.output_was_manual = True
                self.output_var.set(str(Path(path).resolve()))

        def start(self) -> None:
            if self.worker and self.worker.is_alive():
                return
            try:
                input_path = Path(self.input_var.get()).expanduser().resolve()
                output_path = Path(self.output_var.get()).expanduser().resolve()
            except (OSError, ValueError):
                messagebox.showerror(self.app_title, t("invalid_path"))
                return
            if not input_path.is_file():
                messagebox.showerror(self.app_title, t("select_valid_source"))
                return
            if output_path.exists() and not messagebox.askyesno(
                self.app_title, t("overwrite_question", path=output_path)
            ):
                return

            max_size = self.size_choices[self.size_var.get()]
            crf = self.quality_choices[self.quality_var.get()]

            self.stop_event.clear()
            self.progress_var.set(0)
            self.status_var.set(t("starting"))
            self.start_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            self.worker = threading.Thread(
                target=self._convert_worker,
                args=(input_path, output_path, max_size, crf),
                daemon=True,
            )
            self.worker.start()

        def _convert_worker(
            self, input_path: Path, output_path: Path, max_size: str, crf: int
        ) -> None:
            try:
                result = convert(
                    input_path,
                    output_path,
                    max_size,
                    crf,
                    on_progress=lambda value: self.events.put(("progress", value)),
                    on_log=lambda value: self.events.put(("log", value)),
                    stop_event=self.stop_event,
                    process_callback=lambda value: self.events.put(("process", value)),
                )
                video = first_stream(result, "video") or {}
                self.events.put(
                    (
                        "done",
                        (
                            output_path,
                            f"{video.get('width', '?')}×{video.get('height', '?')}",
                            human_size(output_path.stat().st_size),
                        ),
                    )
                )
            except (ConversionError, OSError, subprocess.SubprocessError) as exc:
                self.events.put(("error", str(exc)))

        def _poll_events(self) -> None:
            try:
                while True:
                    event, value = self.events.get_nowait()
                    if event == "progress":
                        percent = float(value)
                        self.progress_var.set(percent)
                        self.status_var.set(t("converting", percent=int(percent)))
                    elif event == "log":
                        self._append_log(str(value))
                    elif event == "process":
                        self.process = value if isinstance(value, subprocess.Popen) else None
                    elif event == "done":
                        path, resolution, size = value  # type: ignore[misc]
                        self._set_idle()
                        self.progress_var.set(100)
                        self.status_var.set(t("completed_status"))
                        self._append_log(
                            t("validation_success_log")
                            + t(
                                "output_log",
                                resolution=resolution,
                                size=size,
                                path=path,
                            )
                        )
                        if messagebox.askyesno(
                            self.app_title,
                            t("success_question", resolution=resolution, size=size),
                        ):
                            subprocess.Popen(["explorer", "/select,", str(path)])
                    elif event == "error":
                        self._set_idle()
                        self.status_var.set(t("failed_status"))
                        self._append_log(t("error_log", error=value))
                        messagebox.showerror(self.app_title, str(value))
            except queue.Empty:
                pass
            self.root.after(100, self._poll_events)

        def _append_log(self, text: str) -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text)
            self.log.see("end")
            self.log.configure(state="disabled")

        def _set_idle(self) -> None:
            self.process = None
            self.start_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")

        def cancel(self) -> None:
            if self.worker and self.worker.is_alive() and messagebox.askyesno(
                self.app_title, t("cancel_question")
            ):
                self.stop_event.set()
                self.status_var.set(t("cancelling"))
                if self.process and self.process.poll() is None:
                    self.process.terminate()

        def close(self) -> None:
            if self.worker and self.worker.is_alive():
                if not messagebox.askyesno(
                    self.app_title, t("close_question")
                ):
                    return
                self.stop_event.set()
                if self.process and self.process.poll() is None:
                    self.process.terminate()
            self.root.destroy()

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=t("arg_description"))
    parser.add_argument("input", nargs="?", help=t("arg_input"))
    parser.add_argument("-o", "--output", help=t("arg_output"))
    parser.add_argument(
        "--size",
        choices=("1080p", "720p", "original"),
        default="1080p",
        help=t("arg_size"),
    )
    parser.add_argument("--crf", type=int, choices=range(18, 31), default=23)
    parser.add_argument("--cli", action="store_true", help=t("arg_cli"))
    parser.add_argument("--overwrite", action="store_true", help=t("arg_overwrite"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_cli(args) if args.cli else run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
