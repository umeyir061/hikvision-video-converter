#!/usr/bin/env python3
"""Hikvision kamera videolarını WhatsApp uyumlu MP4 dosyalarına dönüştürür."""

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


APP_TITLE = "Hikvision Video Düzeltici"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
        detail = result.stderr.strip() or "Video bilgisi okunamadı."
        raise ConversionError(detail)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ConversionError("FFprobe geçersiz bir sonuç döndürdü.") from exc


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
        raise ConversionError("Çıktı dosyası oluşturulamadı.")
    info = probe_video(path, ffprobe)
    video = first_stream(info, "video")
    format_name = info.get("format", {}).get("format_name", "")
    if not video or video.get("codec_name") != "h264":
        raise ConversionError("Çıktının H.264 video doğrulaması başarısız oldu.")
    if "mp4" not in format_name:
        raise ConversionError("Çıktının MP4 kapsayıcı doğrulaması başarısız oldu.")
    if video.get("pix_fmt") != "yuv420p":
        raise ConversionError("Çıktının renk biçimi doğrulaması başarısız oldu.")
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
        raise ConversionError(
            "FFmpeg bulunamadı. ffmpeg.exe ile ffprobe.exe dosyalarını uygulamanın "
            "yanına koyun veya FFmpeg'i PATH'e ekleyin."
        )
    if not input_path.is_file():
        raise ConversionError("Seçilen kaynak video bulunamadı.")
    if input_path.resolve() == output_path.resolve():
        raise ConversionError("Kaynak ve çıktı dosyası aynı olamaz.")

    source_info = probe_video(input_path, ffprobe)
    video = first_stream(source_info, "video")
    if not video:
        raise ConversionError("Kaynak dosyada video akışı bulunamadı.")
    try:
        duration = float(source_info.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = conversion_command(ffmpeg, input_path, output_path, max_size, crf)
    if on_log:
        on_log(
            f"Kaynak: {video.get('codec_name', '?').upper()} — "
            f"{video.get('width', '?')}×{video.get('height', '?')}\n"
        )
        on_log("Bozuk paketler atlanıyor ve uyumlu MP4 hazırlanıyor...\n")

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
            raise ConversionError("Dönüştürme kullanıcı tarafından iptal edildi.")

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
        raise ConversionError(f"FFmpeg dönüştürmeyi tamamlayamadı.\n{detail}".strip())

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
        print("Hata: Bir kaynak video yolu belirtin.", file=sys.stderr)
        return 2
    input_path = Path(args.input).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve() if args.output else default_output_path(input_path)
    )
    if output_path.exists() and not args.overwrite:
        print(f"Hata: Çıktı zaten var: {output_path}\n--overwrite ile üzerine yazabilirsiniz.")
        return 2

    last_percent = -1

    def show_progress(percent: float) -> None:
        nonlocal last_percent
        rounded = int(percent)
        if rounded != last_percent:
            print(f"\rDönüştürülüyor: %{rounded:3d}", end="", flush=True)
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
        print(f"\nHata: {exc}", file=sys.stderr)
        return 1
    print(f"\nTamamlandı: {output_path} ({human_size(output_path.stat().st_size)})")
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
            self.root.title(APP_TITLE)
            self.root.geometry("760x550")
            self.root.minsize(680, 500)

            self.input_var = tk.StringVar()
            self.output_var = tk.StringVar()
            self.size_var = tk.StringVar(value="WhatsApp için önerilen (en fazla 1080p)")
            self.quality_var = tk.StringVar(value="Dengeli — önerilen")
            self.status_var = tk.StringVar(value="Bir Hikvision videosu seçin.")
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

            ttk.Label(outer, text=APP_TITLE, font=("Segoe UI", 18, "bold")).grid(
                row=0, column=0, columnspan=3, sticky="w"
            )
            ttk.Label(
                outer,
                text="Hikvision H.265 kayıtlarını gerçek, paylaşılabilir H.264 MP4 dosyalarına çevirir.",
                foreground="#555555",
            ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 20))

            ttk.Label(outer, text="Kaynak video").grid(row=2, column=0, sticky="w", pady=6)
            ttk.Entry(outer, textvariable=self.input_var).grid(
                row=2, column=1, sticky="ew", padx=10, pady=6
            )
            ttk.Button(outer, text="Seç…", command=self.choose_input).grid(
                row=2, column=2, sticky="ew", pady=6
            )

            ttk.Label(outer, text="Çıktı dosyası").grid(row=3, column=0, sticky="w", pady=6)
            output_entry = ttk.Entry(outer, textvariable=self.output_var)
            output_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
            output_entry.bind("<Key>", lambda _event: setattr(self, "output_was_manual", True))
            ttk.Button(outer, text="Kaydet…", command=self.choose_output).grid(
                row=3, column=2, sticky="ew", pady=6
            )

            ttk.Label(outer, text="Boyut").grid(row=4, column=0, sticky="w", pady=6)
            ttk.Combobox(
                outer,
                textvariable=self.size_var,
                state="readonly",
                values=(
                    "WhatsApp için önerilen (en fazla 1080p)",
                    "Daha küçük dosya (en fazla 720p)",
                    "Özgün çözünürlüğü koru",
                ),
            ).grid(row=4, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=6)

            ttk.Label(outer, text="Kalite").grid(row=5, column=0, sticky="w", pady=6)
            ttk.Combobox(
                outer,
                textvariable=self.quality_var,
                state="readonly",
                values=("Dengeli — önerilen", "Yüksek kalite", "Küçük dosya"),
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
                buttons, text="İptal", command=self.cancel, state="disabled"
            )
            self.cancel_button.pack(side="left", padx=(0, 8))
            self.start_button = ttk.Button(
                buttons, text="Videoyu Düzelt", command=self.start
            )
            self.start_button.pack(side="left")

        def choose_input(self) -> None:
            path = filedialog.askopenfilename(
                title="Hikvision videosunu seçin",
                filetypes=(
                    ("Video dosyaları", "*.mp4 *.avi *.dav *.mov *.mkv *.ts *.mpeg *.mpg"),
                    ("Tüm dosyalar", "*.*"),
                ),
            )
            if path:
                self.set_input(Path(path))

        def set_input(self, path: Path) -> None:
            path = path.expanduser().resolve()
            self.input_var.set(str(path))
            if not self.output_was_manual:
                self.output_var.set(str(default_output_path(path)))
            self.status_var.set("Video seçildi. Dönüştürmeye hazır.")
            self._append_log(f"Seçilen dosya: {path.name}\n")

        def choose_output(self) -> None:
            initial = Path(self.output_var.get()) if self.output_var.get() else Path.cwd()
            path = filedialog.asksaveasfilename(
                title="Düzeltilmiş videoyu kaydedin",
                initialdir=str(initial.parent),
                initialfile=initial.name,
                defaultextension=".mp4",
                filetypes=(("MP4 video", "*.mp4"),),
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
                messagebox.showerror(APP_TITLE, "Dosya yolu geçerli değil.")
                return
            if not input_path.is_file():
                messagebox.showerror(APP_TITLE, "Lütfen geçerli bir kaynak video seçin.")
                return
            if output_path.exists() and not messagebox.askyesno(
                APP_TITLE, f"Bu çıktı zaten var:\n{output_path}\n\nÜzerine yazılsın mı?"
            ):
                return

            sizes = {
                "WhatsApp için önerilen (en fazla 1080p)": "1080p",
                "Daha küçük dosya (en fazla 720p)": "720p",
                "Özgün çözünürlüğü koru": "original",
            }
            qualities = {"Dengeli — önerilen": 23, "Yüksek kalite": 20, "Küçük dosya": 27}
            max_size = sizes[self.size_var.get()]
            crf = qualities[self.quality_var.get()]

            self.stop_event.clear()
            self.progress_var.set(0)
            self.status_var.set("Dönüştürme başlatılıyor…")
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
                        self.status_var.set(f"Video dönüştürülüyor… %{int(percent)}")
                    elif event == "log":
                        self._append_log(str(value))
                    elif event == "process":
                        self.process = value if isinstance(value, subprocess.Popen) else None
                    elif event == "done":
                        path, resolution, size = value  # type: ignore[misc]
                        self._set_idle()
                        self.progress_var.set(100)
                        self.status_var.set("Tamamlandı — video paylaşılmaya hazır.")
                        self._append_log(
                            f"\nDoğrulama başarılı: MP4 / H.264 / yuv420p\n"
                            f"Çıktı: {resolution}, {size}\n{path}\n"
                        )
                        if messagebox.askyesno(
                            APP_TITLE,
                            f"Video başarıyla düzeltildi.\n\n{resolution} — {size}\n\n"
                            "Çıktının bulunduğu klasör açılsın mı?",
                        ):
                            subprocess.Popen(["explorer", "/select,", str(path)])
                    elif event == "error":
                        self._set_idle()
                        self.status_var.set("Dönüştürme tamamlanamadı.")
                        self._append_log(f"\nHATA: {value}\n")
                        messagebox.showerror(APP_TITLE, str(value))
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
                APP_TITLE, "Devam eden dönüştürme iptal edilsin mi?"
            ):
                self.stop_event.set()
                self.status_var.set("Dönüştürme iptal ediliyor…")
                if self.process and self.process.poll() is None:
                    self.process.terminate()

        def close(self) -> None:
            if self.worker and self.worker.is_alive():
                if not messagebox.askyesno(
                    APP_TITLE, "Dönüştürme sürüyor. İptal edilip uygulama kapatılsın mı?"
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Kaynak video")
    parser.add_argument("-o", "--output", help="Çıktı MP4 yolu")
    parser.add_argument(
        "--size",
        choices=("1080p", "720p", "original"),
        default="1080p",
        help="Azami çıktı boyutu (varsayılan: 1080p)",
    )
    parser.add_argument("--crf", type=int, choices=range(18, 31), default=23)
    parser.add_argument("--cli", action="store_true", help="Grafik arayüz olmadan çalıştır")
    parser.add_argument("--overwrite", action="store_true", help="Var olan çıktının üzerine yaz")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_cli(args) if args.cli else run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
