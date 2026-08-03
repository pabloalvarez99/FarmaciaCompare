"""Tests for the image health checker's pure logic.

The DB and network paths are exercised by running the tool; what is worth
pinning down here is the format sniffing, because the whole check rests on it:
if `identify` returns a kind for a soft-404 HTML body, every broken image on the
site reads as healthy.
"""
import pytest

from src.check_images import MAGIC_PREFIXES, identify


class TestIdentify:
    @pytest.mark.parametrize("head,expected", [
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "JPEG"),
        (b"\x89PNG\r\n\x1a\n\x00\x00", "PNG"),
        (b"RIFF\x24\x00\x00\x00WEBP", "WEBP"),
        (b"GIF89a\x01\x00\x01\x00", "GIF"),
        (b"<svg xmlns='http://ww", "SVG"),
        (b"<?xml version='1.0'?>", "SVG"),
    ])
    def test_recognises_real_image_headers(self, head, expected):
        assert identify(head) == expected

    @pytest.mark.parametrize("head", [
        b"<!DOCTYPE html><html>",   # soft 404: 200 with an HTML error page
        b"<html><head><title>",
        b"",                        # 200 with an empty body
        b"{\"error\":\"not found\"",
        b"Not Found",
    ])
    def test_rejects_bodies_that_are_not_images(self, head):
        # This is the case the checker exists for. A CDN answering 200 with an
        # HTML error page must never be counted as a working image.
        assert identify(head) is None

    def test_truncated_header_is_not_guessed(self):
        # We only read the first 16 bytes; a partial magic number must not match.
        assert identify(b"\xff") is None
        assert identify(b"\x89P") is None

    def test_every_declared_prefix_is_identifiable(self):
        for prefix, kind in MAGIC_PREFIXES.items():
            assert identify(prefix + b"\x00" * 8) == kind
