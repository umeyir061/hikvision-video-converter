import os
import string
import unittest
from unittest.mock import patch

import hikvision_video_duzeltici as app


class LocalizationTests(unittest.TestCase):
    def test_translation_keys_match(self) -> None:
        self.assertEqual(set(app.TRANSLATIONS["tr"]), set(app.TRANSLATIONS["en"]))

    def test_translation_placeholders_match(self) -> None:
        formatter = string.Formatter()
        for key, turkish in app.TRANSLATIONS["tr"].items():
            english = app.TRANSLATIONS["en"][key]
            turkish_fields = {name for _, name, _, _ in formatter.parse(turkish) if name}
            english_fields = {name for _, name, _, _ in formatter.parse(english) if name}
            self.assertEqual(turkish_fields, english_fields, key)

    def test_turkish_windows_language_id(self) -> None:
        self.assertEqual(app.language_from_windows_id(0x041F), "tr")

    def test_non_turkish_windows_language_ids_use_english(self) -> None:
        for language_id in (0x0409, 0x0407, 0x040C, 0x0411):
            with self.subTest(language_id=language_id):
                self.assertEqual(app.language_from_windows_id(language_id), "en")

    def test_language_override_is_available_for_automated_tests(self) -> None:
        with patch.dict(os.environ, {"HIKVISION_VIDEO_FIXER_LANG": "tr"}):
            self.assertEqual(app.detect_language(), "tr")
        with patch.dict(os.environ, {"HIKVISION_VIDEO_FIXER_LANG": "en"}):
            self.assertEqual(app.detect_language(), "en")


if __name__ == "__main__":
    unittest.main()
