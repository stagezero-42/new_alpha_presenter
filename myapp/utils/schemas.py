# myapp/utils/schemas.py

"""
Defines the JSON schemas used for validation in the application.
"""

# Default text style values
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE = 48
DEFAULT_FONT_COLOR = "#FFFFFF"  # White
DEFAULT_BACKGROUND_COLOR = "#000000"  # Black
DEFAULT_BACKGROUND_ALPHA = 150  # ~60% opacity (0-255 scale)
DEFAULT_TEXT_ALIGN = "center" # horizontal: left, center, right
DEFAULT_TEXT_VERTICAL_ALIGN = "bottom" # top, middle, bottom
DEFAULT_FIT_TO_WIDTH = False

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
                        "default": 2.0
                    }
                },
                "required": ["text"],
                "additionalProperties": False
            },
            "default": []
        }
    },
    "required": ["name", "sentences"],
    "additionalProperties": False
}

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
                    "text_overlay": {
                        "type": ["object", "null"],
                        "properties": {
                            "paragraph_name": {"type": "string"},
                            "start_sentence": {"type": "integer", "minimum": 1},
                            "end_sentence": {
                                "oneOf": [
                                    {"type": "integer", "minimum": 1},
                                    {"type": "string", "pattern": "^all$"}
                                ]
                            },
                            "sentence_timing_enabled": {
                                "type": "boolean",
                                "default": False
                            },
                            "auto_advance_slide": {
                                "type": "boolean",
                                "default": False
                            },
                            "font_family": {
                                "type": "string",
                                "default": DEFAULT_FONT_FAMILY
                            },
                            "font_size": {
                                "type": "integer",
                                "minimum": 8,
                                "maximum": 200,
                                "default": DEFAULT_FONT_SIZE
                            },
                            "font_color": {
                                "type": "string",
                                "pattern": "^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
                                "default": DEFAULT_FONT_COLOR
                            },
                            "background_color": {
                                "type": "string",
                                "pattern": "^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
                                "default": DEFAULT_BACKGROUND_COLOR
                            },
                            "background_alpha": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 255,
                                "default": DEFAULT_BACKGROUND_ALPHA
                            },
                            "text_align": { # Horizontal alignment
                                "type": "string",
                                "enum": ["left", "center", "right"],
                                "default": DEFAULT_TEXT_ALIGN
                            },
                            "text_vertical_align": {
                                "type": "string",
                                "enum": ["top", "middle", "bottom"],
                                "default": DEFAULT_TEXT_VERTICAL_ALIGN
                            },
                            "fit_to_width": {
                                "type": "boolean",
                                "default": DEFAULT_FIT_TO_WIDTH
                            }
                            # Potentially add audio_sync_cues here later if text syncs to audio on this slide
                        },
                        "required": ["paragraph_name", "start_sentence", "end_sentence"],
                        "additionalProperties": False # Keep this strict for text_overlay
                    }
                    # Later, you might add an "audio_program_name" field here at the slide level
                },
                "required": ["layers", "duration", "loop_to_slide"],
                "additionalProperties": True # Allow other keys like audio_program_name at slide level
            },
            "default": []
        }
    },
    "required": ["slides"],
    "additionalProperties": True
}

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
            "additionalProperties": True # Allow other actions
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
        # You could add default audio paths here if needed
    },
    "additionalProperties": True # Allow future top-level settings
}

# --- NEW AUDIO SCHEMAS ---
AUDIO_TRACK_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "track_name": {"type": "string"}, # Unique identifier for this track's metadata
        "file_path": {"type": "string"},   # Relative path from 'assets/media/' or absolute
        "detected_duration_ms": {"type": ["integer", "null"], "minimum": 0} # Detected full duration
    },
    "required": ["track_name", "file_path"],
    "additionalProperties": False
}

AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "track_name": {"type": "string"}, # References a track_name from AUDIO_TRACK_METADATA_SCHEMA
        "play_order": {"type": "integer", "minimum": 0}, # For ordering within the program
        "user_start_time_ms": {"type": "integer", "minimum": 0, "default": 0},
        "user_end_time_ms": {"type": ["integer", "null"], "minimum": 0} # null means play to end of track
    },
    "required": ["track_name", "play_order"],
    "additionalProperties": False
}

AUDIO_PROGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string"},
        "tracks": {
            "type": "array",
            "items": AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA,
            "default": []
        },
        "loop_indefinitely": {"type": "boolean", "default": False},
        "loop_count": {"type": "integer", "minimum": 0, "default": 0} # 0 means no counted loop
    },
    "required": ["program_name", "tracks"],
    "additionalProperties": False
}
# --- END NEW AUDIO SCHEMAS ---