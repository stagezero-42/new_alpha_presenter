# myapp/utils/schemas.py

"""
Defines the JSON schemas used for validation in the application.
"""

# --- NEW SCHEMA ---
# Schema for individual paragraph files (e.g., my_paragraph.json)
PARAGRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "delay_seconds": {
                        "type": "number",
                        "minimum": 0,
                        "default": 0.0
                    }
                },
                "required": ["text", "delay_seconds"],
                "additionalProperties": False # Keep sentences strict
            },
            "default": []
        }
    },
    "required": ["name", "sentences"],
    "additionalProperties": False # Keep paragraphs strict
}
# --- END NEW SCHEMA ---

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
                    },
                    # --- NEW TEXT_OVERLAY FIELD ---
                    "text_overlay": {
                        "type": ["object", "null"], # Can be an object or null
                        "properties": {
                            "paragraph_name": {"type": "string"},
                            "start_sentence": {"type": "integer", "minimum": 1},
                            "end_sentence": {
                                "oneOf": [
                                    {"type": "integer", "minimum": 1},
                                    {"type": "string", "pattern": "^all$"}
                                ]
                            }
                        },
                        "required": ["paragraph_name", "start_sentence", "end_sentence"],
                        "additionalProperties": False
                    }
                    # --- END NEW TEXT_OVERLAY FIELD ---
                },
                "required": ["layers", "duration", "loop_to_slide"],
                "additionalProperties": True # Allow for future additions like text_overlay
            },
            "default": []
        }
    },
    "required": ["slides"],
    "additionalProperties": True # Allow for future top-level additions
}

# Schema for settings file (settings.json)
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
    },
    "additionalProperties": True
}