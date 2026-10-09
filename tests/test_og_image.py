"""The social preview image renders at the size messengers expect, with or without a system font."""

from PIL import Image

from radar import og_image

SUMMARY = {"as_of": "2026-10-09", "totals": {"jobs": 4220, "median_pay": 16.0, "no_german_share": 0.017}}


def test_renders_1200x630(tmp_path):
    path = og_image.render(SUMMARY, tmp_path / "og.png")
    with Image.open(path) as img:
        assert img.size == (1200, 630)
        assert img.format == "PNG"


def test_falls_back_to_bundled_font(tmp_path, monkeypatch):
    monkeypatch.setattr(og_image, "FONTS", {False: [], True: []})
    og_image.font_path.cache_clear()
    try:
        path = og_image.render(SUMMARY, tmp_path / "og.png")
        with Image.open(path) as img:
            assert img.size == (1200, 630)
    finally:
        og_image.font_path.cache_clear()
