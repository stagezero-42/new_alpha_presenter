# tests/test_utils/test_security.py
import pytest
from myapp.utils.security import is_safe_filename_component

@pytest.mark.parametrize("filename, expected", [
    ("image.png", True),
    ("playlist_1.json", True),
    ("my-document.txt", True),
    (".config", True),
    (" leading_space", True), # Generally allowed, but be mindful
    ("trailing_space ", True), # Generally allowed, but be mindful
    ("", False),              # Empty is not safe
    (None, False),            # None is not safe
    ("..", False),             # Disallowed
    (".", False),              # Disallowed
    ("path/to/file.txt", False),# Contains /
    ("path\\to\\file.txt", False),# Contains \
    ("file\0with_null.txt", False), # Contains null byte
    ("C:file.txt", True), # This *is* considered safe by our simple check, as C: isn't / or \
])
def test_is_safe_filename_component(filename, expected):
    """Tests various filenames against is_safe_filename_component."""
    assert is_safe_filename_component(filename) == expected