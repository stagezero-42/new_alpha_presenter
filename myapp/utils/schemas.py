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

# Default audio settings
DEFAULT_AUDIO_PROGRAM_VOLUME = 0.8 # 80% volume

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
                            "text_align": {
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
                        },
                        "required": ["paragraph_name", "start_sentence", "end_sentence"],
                        "additionalProperties": False
                    },
                    "audio_program_name": {
                        "type": ["string", "null"],
                        "default": None
                    },
                    "loop_audio_program": {
                        "type": "boolean",
                        "default": False
                    },
                    "audio_intro_delay_ms": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                        "default": 0
                    },
                    "audio_outro_duration_ms": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                        "default": 0
                    },
                    "audio_program_volume": { # NEW
                        "type": ["number", "null"],
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": DEFAULT_AUDIO_PROGRAM_VOLUME
                    }
                },
                "required": ["layers", "duration", "loop_to_slide"],
                "additionalProperties": True
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

AUDIO_TRACK_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "track_name": {"type": "string"},
        "file_path": {"type": "string"},
        "detected_duration_ms": {"type": ["integer", "null"], "minimum": 0}
    },
    "required": ["track_name", "file_path"],
    "additionalProperties": False
}

AUDIO_PROGRAM_TRACK_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "track_name": {"type": "string"},
        "play_order": {"type": "integer", "minimum": 0},
        "user_start_time_ms": {"type": "integer", "minimum": 0, "default": 0},
        "user_end_time_ms": {"type": ["integer", "null"], "minimum": 0}
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
        "loop_count": {"type": "integer", "minimum": 0, "default": 0}
    },
    "required": ["program_name", "tracks"],
    "additionalProperties": False
}