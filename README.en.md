# Hikvision Video Fixer

[Türkçe](README.md) | **English**

A Windows utility that converts Hikvision camera exports using a non-standard
MPEG container and H.265/HEVC video—even when they have an `.mp4` extension—into
MP4 files compatible with WhatsApp, smartphones, and web browsers.

The source recording is never modified or deleted. The converted video is created
in the same directory with `_WhatsApp.mp4` appended to its name.

## Features

- Automatically detects non-standard Hikvision exports.
- Skips corrupt packets and regenerates missing timestamps.
- Converts video to H.264 High Profile with `yuv420p` inside a real MP4 container.
- Converts audio to stereo AAC when an audio stream is present.
- Uses the MP4 `faststart` layout for playback before the download is complete.
- Offers recommended 1080p, smaller 720p, and original-resolution output modes.
- Validates the codec, container, and pixel format after conversion.
- Includes a Turkish graphical interface with progress and cancellation support.

## Requirements

- Windows 10 or 11
- Python 3.10 or later
- [FFmpeg](https://ffmpeg.org/) built with `libx264` support

The utility first looks for FFmpeg on the system `PATH`. Alternatively, place
`ffmpeg.exe` and `ffprobe.exe` next to the application, inside `bin`, or inside
`ffmpeg\bin`.

## Usage

1. Double-click `Hikvision Video Duzeltici.bat`.
2. Click **Seç…** and select the camera recording.
3. Adjust the size and quality settings if needed.
4. Click **Videoyu Düzelt**.
5. Share the newly created `_WhatsApp.mp4` file.

You can also drag a video file onto the `.bat` launcher to open it directly in
the application.

> The graphical interface is currently in Turkish. **Seç…** means “Browse,” and
> **Videoyu Düzelt** means “Fix Video.”

## Command line

```powershell
python .\hikvision_video_duzeltici.py "camera.mp4" --cli
```

Example options:

```powershell
# Create a smaller 720p output
python .\hikvision_video_duzeltici.py "camera.mp4" --cli --size 720p

# Set an explicit output path and use high quality
python .\hikvision_video_duzeltici.py "camera.mp4" --cli --crf 20 -o "fixed.mp4"

# Overwrite an existing output
python .\hikvision_video_duzeltici.py "camera.mp4" --cli --overwrite
```

To see every option:

```powershell
python .\hikvision_video_duzeltici.py --help
```

## Privacy

Video files are excluded by `.gitignore`. Camera recordings and converted
outputs are not committed to the repository.

## License

This project is available under the [MIT License](LICENSE). You may use, modify,
and redistribute it for personal or commercial purposes, provided that the
copyright and license notice is retained in copies.
