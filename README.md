# Hikvision Video Düzeltici

**Türkçe** | [English](README.en.md)

Hikvision kameraların `.mp4` uzantısıyla dışa aktardığı, ancak standart olmayan
MPEG kapsayıcı ve H.265/HEVC video kullanan kayıtları WhatsApp, telefonlar ve web
tarayıcılarıyla uyumlu MP4 dosyalarına dönüştüren Windows aracıdır.

Kaynak kayıt değiştirilmez veya silinmez. Yeni video aynı klasörde
`_WhatsApp.mp4` ekiyle oluşturulur.

## Özellikler

- Standart dışı Hikvision dışa aktarımlarını otomatik algılar.
- Bozuk paketleri atlar ve eksik zaman damgalarını yeniden oluşturur.
- Videoyu MP4 içinde H.264 High Profile ve `yuv420p` biçimine dönüştürür.
- Varsa sesi AAC stereo biçimine çevirir.
- MP4 `faststart` düzeni sayesinde videonun indirme sürerken başlamasını sağlar.
- Önerilen 1080p, küçük dosya için 720p ve özgün çözünürlük seçenekleri sunar.
- Dönüştürme sonunda codec, kapsayıcı ve renk biçimini doğrular.
- Türkçe grafik arayüz, ilerleme göstergesi ve iptal desteği içerir.

## Gereksinimler

- Windows 10 veya 11
- Python 3.10 veya üzeri
- `libx264` destekli [FFmpeg](https://ffmpeg.org/)

Araç önce sistem `PATH` değişkeninde FFmpeg'i arar. Alternatif olarak
`ffmpeg.exe` ve `ffprobe.exe` dosyaları uygulamanın yanına, `bin` klasörüne veya
`ffmpeg\bin` klasörüne konabilir.

## Kullanım

1. `Hikvision Video Duzeltici.bat` dosyasına çift tıklayın.
2. **Seç…** düğmesiyle kamera videosunu seçin.
3. İhtiyaç halinde boyut ve kalite ayarlarını değiştirin.
4. **Videoyu Düzelt** düğmesine basın.
5. Oluşturulan `_WhatsApp.mp4` dosyasını paylaşın.

Bir video dosyasını doğrudan `.bat` dosyasının üzerine sürükleyip bırakarak da
arayüzde açabilirsiniz.

## Komut satırı

```powershell
python .\hikvision_video_duzeltici.py "kamera.mp4" --cli
```

Örnek seçenekler:

```powershell
# Daha küçük 720p çıktı
python .\hikvision_video_duzeltici.py "kamera.mp4" --cli --size 720p

# Belirli bir çıktı yolu ve yüksek kalite
python .\hikvision_video_duzeltici.py "kamera.mp4" --cli --crf 20 -o "duzeltilmis.mp4"

# Var olan çıktının üzerine yaz
python .\hikvision_video_duzeltici.py "kamera.mp4" --cli --overwrite
```

Tüm seçenekler için:

```powershell
python .\hikvision_video_duzeltici.py --help
```

## Gizlilik

Video dosyaları `.gitignore` tarafından dışlanır. Kamera kayıtları ve oluşturulan
çıktılar repoya eklenmez.

## Lisans

Bu proje [MIT Lisansı](LICENSE) ile sunulur. Kişisel veya ticari amaçla
kullanabilir, değiştirebilir ve yeniden dağıtabilirsiniz; telif ve lisans
bildiriminin kopyalarda korunması gerekir.
