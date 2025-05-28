# tests/test_text/test_paragraph_manager.py
import pytest
import os
import json
import shutil
from unittest.mock import patch, MagicMock

# Ensure the myapp structure can be imported
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from myapp.text.paragraph_manager import ParagraphManager
from myapp.utils.schemas import PARAGRAPH_SCHEMA
from myapp.utils.json_validator import validate_json

@pytest.fixture
def temp_texts_dir(tmp_path):
    """Creates a temporary directory for text paragraphs."""
    texts_dir = tmp_path / "texts"
    texts_dir.mkdir()
    yield str(texts_dir)

@pytest.fixture
def paragraph_manager(temp_texts_dir):
    """Provides a ParagraphManager instance configured with the temp directory."""
    # --- MODIFIED: Inject the temp_texts_dir directly, remove patch ---
    manager = ParagraphManager(texts_dir=temp_texts_dir)
    yield manager
    # --- END MODIFIED ---

@pytest.fixture
def valid_paragraph_data():
    """Provides valid sample paragraph data."""
    return {
        "name": "sample_para",
        "sentences": [
            {"text": "This is the first sentence.", "delay_seconds": 0.5},
            {"text": "This is the second.", "delay_seconds": 1.0}
        ]
    }

def test_paragraph_manager_init(paragraph_manager, temp_texts_dir):
    """Tests if the manager initializes and creates the directory."""
    assert paragraph_manager.texts_dir == temp_texts_dir
    assert os.path.exists(temp_texts_dir)

# --- MODIFIED: Removed patch, it should now work directly ---
def test_save_and_load_paragraph(paragraph_manager, valid_paragraph_data, temp_texts_dir):
    """Tests saving a valid paragraph and loading it back."""
    para_name = valid_paragraph_data["name"]
    result = paragraph_manager.save_paragraph(para_name, valid_paragraph_data)
    assert result is True
    assert os.path.exists(os.path.join(temp_texts_dir, f"{para_name}.json"))

    loaded_data = paragraph_manager.load_paragraph(para_name)
    assert loaded_data == valid_paragraph_data
# --- END MODIFIED ---

def test_save_invalid_data(paragraph_manager):
    """Tests trying to save data that doesn't match the schema."""
    invalid_data = {"name": "invalid", "sentences": "not an array"}
    result = paragraph_manager.save_paragraph("invalid", invalid_data)
    assert result is False

def test_save_unsafe_name(paragraph_manager, valid_paragraph_data):
    """Tests trying to save with an unsafe filename."""
    result = paragraph_manager.save_paragraph("../unsafe", valid_paragraph_data)
    assert result is False

def test_load_not_found(paragraph_manager):
    """Tests loading a paragraph that doesn't exist."""
    with pytest.raises(FileNotFoundError):
        paragraph_manager.load_paragraph("non_existent")

# --- MODIFIED: Removed patch ---
def test_load_invalid_json(paragraph_manager, temp_texts_dir):
    """Tests loading a file with invalid JSON."""
    para_name = "bad_json"
    file_path = os.path.join(temp_texts_dir, f"{para_name}.json")
    with open(file_path, "w") as f:
        f.write("{this is not json,")

    with pytest.raises(ValueError):
        paragraph_manager.load_paragraph(para_name)
# --- END MODIFIED ---

# --- MODIFIED: Removed patch ---
def test_load_invalid_schema(paragraph_manager, temp_texts_dir):
    """Tests loading JSON that doesn't match the paragraph schema."""
    para_name = "bad_schema"
    invalid_data = {"name": para_name, "sentences": "not an array"}
    file_path = os.path.join(temp_texts_dir, f"{para_name}.json")
    with open(file_path, "w") as f:
        json.dump(invalid_data, f)

    with pytest.raises(ValueError):
        paragraph_manager.load_paragraph(para_name)
# --- END MODIFIED ---

# --- MODIFIED: Removed patch ---
def test_list_paragraphs(paragraph_manager, valid_paragraph_data):
    """Tests listing available paragraphs."""
    assert paragraph_manager.list_paragraphs() == []

    paragraph_manager.save_paragraph("para1", {"name": "para1", "sentences": []})
    paragraph_manager.save_paragraph("para2", {"name": "para2", "sentences": []})

    listed = sorted(paragraph_manager.list_paragraphs())
    assert listed == ["para1", "para2"]
# --- END MODIFIED ---

# --- MODIFIED: Removed patch ---
def test_delete_paragraph(paragraph_manager, valid_paragraph_data, temp_texts_dir):
    """Tests deleting a paragraph."""
    para_name = valid_paragraph_data["name"]
    file_path = os.path.join(temp_texts_dir, f"{para_name}.json")

    paragraph_manager.save_paragraph(para_name, valid_paragraph_data)
    assert os.path.exists(file_path)

    result = paragraph_manager.delete_paragraph(para_name)
    assert result is True
    assert not os.path.exists(file_path)

    # Test deleting non-existent
    result_non_existent = paragraph_manager.delete_paragraph("non_existent")
    assert result_non_existent is True
# --- END MODIFIED ---

def test_delete_unsafe_name(paragraph_manager):
    """Tests trying to delete with an unsafe name."""
    result = paragraph_manager.delete_paragraph("../../unsafe_delete")
    assert result is False

# --- MODIFIED: Removed patch ---
def test_load_name_mismatch(paragraph_manager, temp_texts_dir):
    """Tests loading a file where internal name differs from filename."""
    para_name = "file_name"
    data = {"name": "internal_name", "sentences": []}
    file_path = os.path.join(temp_texts_dir, f"{para_name}.json")
    with open(file_path, "w") as f:
        json.dump(data, f)

    loaded_data = paragraph_manager.load_paragraph(para_name)
    assert loaded_data["name"] == "file_name" # Should be corrected to file name
# --- END MODIFIED ---