# tests/test_utils/test_json_validator.py
import pytest
from myapp.utils.json_validator import validate_json
from jsonschema.exceptions import ValidationError

@pytest.fixture
def sample_schema():
    """A simple schema for testing."""
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0}
        },
        "required": ["name", "age"]
    }

def test_validate_json_valid(sample_schema):
    """Test validation with valid data."""
    data = {"name": "Alice", "age": 30}
    is_valid, error = validate_json(data, sample_schema)
    assert is_valid is True
    assert error is None

def test_validate_json_invalid_type(sample_schema):
    """Test validation with invalid data type."""
    data = {"name": "Bob", "age": "twenty"} # Age should be integer
    is_valid, error = validate_json(data, sample_schema)
    assert is_valid is False
    assert isinstance(error, ValidationError)
    assert "is not of type 'integer'" in error.message

def test_validate_json_missing_required(sample_schema):
    """Test validation with missing required field."""
    data = {"name": "Charlie"} # Age is missing
    is_valid, error = validate_json(data, sample_schema)
    assert is_valid is False
    assert isinstance(error, ValidationError)
    assert "'age' is a required property" in error.message

def test_validate_json_violates_minimum(sample_schema):
    """Test validation with data violating a constraint."""
    data = {"name": "David", "age": -5} # Age < 0
    is_valid, error = validate_json(data, sample_schema)
    assert is_valid is False
    assert isinstance(error, ValidationError)
    assert "is less than the minimum" in error.message