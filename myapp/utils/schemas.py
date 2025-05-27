# myapp/utils/schemas.py

"""
Defines the JSON schemas used for validation in the application.
"""

# Schema for playlist files (playlist.json)
PLAYLIST_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "layers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": []
                    },
                    "duration": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0
                    },
                    "loop_to_slide": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0
                    }
                    # Add future slide properties here
                },
                "required": ["layers", "duration", "loop_to_slide"],
                "additionalProperties": True # Allow for future additions
            },
            "default": []
        }
    },
    "required": ["slides"],
    "additionalProperties": True # Allow for future top-level additions
}

# Schema for settings file (settings.json)
# This schema is intentionally a bit lenient because the SettingsManager
# merges loaded data with defaults and handles missing keys gracefully.
# We mainly want to catch major structural errors or incorrect types.
SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "current_playlist_path": {
            "type": ["string", "null"]
        },
        "keybindings": {
            "type": "object",
            "properties": {
                "next": {"type": "array", "items": {"type": "string"}},
                "prev": {"type": "array", "items": {"type": "string"}},
                "go": {"type": "array", "items": {"type": "string"}},
                "clear": {"type": "array", "items": {"type": "string"}},
                "quit": {"type": "array", "items": {"type": "string"}},
                "load": {"type": "array", "items": {"type": "string"}},
                "edit": {"type": "array", "items": {"type": "string"}}
            },
            "additionalProperties": True
        },
        # --- NEW LOGGING SETTINGS ---
        "log_level": {
            "type": "string",
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "default": "INFO"
        },
        "log_to_file": {
            "type": "boolean",
            "default": False
        },
        "log_file_path": {
            "type": "string",
            "default": "alphapresenter.log"
        }
        # --- END NEW LOGGING SETTINGS ---
    },
    "additionalProperties": True
}