# myapp/text/text_parser.py
import re
import math
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def _parse_time_to_seconds(time_str, is_srt=True):
    """
    Parses a timestamp string (HH:MM:SS,ms or MM:SS.ms or SS.ms) into total seconds.
    For SRT, ms_separator is ',', for WebVTT it's typically '.'.
    """
    if is_srt:
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            logger.warning(f"Could not parse SRT timestamp: {time_str}")
            return 0.0
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 1000.0
    else:  # WebVTT like
        # Try HH:MM:SS.mmm
        match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})', time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / 1000.0
        # Try MM:SS.mmm
        match = re.match(r'(\d{2}):(\d{2})\.(\d{3})', time_str)
        if match:
            m, s, ms = map(int, match.groups())
            return m * 60 + s + ms / 1000.0
        # Try SS.mmm (less common but possible in some contexts)
        match = re.match(r'(\d{1,2})\.(\d{3})', time_str)
        if match:
            s, ms = map(int, match.groups())
            return s + ms / 1000.0

        logger.warning(f"Could not parse WebVTT timestamp: {time_str}")
        return 0.0


def _calculate_and_round_duration(start_seconds, end_seconds):
    """Calculates duration and rounds up to the nearest tenth of a second."""
    if end_seconds <= start_seconds:
        return 0.1  # Minimum duration if end is before or at start
    duration = end_seconds - start_seconds
    return math.ceil(duration * 10) / 10.0


def parse_srt(content: str) -> list:
    """Parses SRT content into a list of sentence dicts."""
    sentences = []
    # Regex to capture number, timestamps, and text
    # Allows for multi-line text
    pattern = re.compile(
        r'(\d+)\s*'  # Sequence number
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*'  # Timestamps
        r'([\s\S]*?)(?=\n\n\d+\s|\n\n\n\d+\s*$|\Z)',  # Text block, looking ahead for next number or end of string
        re.MULTILINE
    )
    for match in pattern.finditer(content):
        try:
            # seq_num = match.group(1).strip() # Not used in output paragraph
            start_time_str = match.group(2).strip()
            end_time_str = match.group(3).strip()
            text = match.group(4).strip().replace('\r\n', '\n')  # Normalize line endings

            if not text:  # Skip if text is empty after stripping
                continue

            start_seconds = _parse_time_to_seconds(start_time_str, is_srt=True)
            end_seconds = _parse_time_to_seconds(end_time_str, is_srt=True)
            duration = _calculate_and_round_duration(start_seconds, end_seconds)

            sentences.append({"text": text, "delay_seconds": duration})
        except Exception as e:
            logger.error(f"Error parsing SRT block: {match.group(0)[:50]}... - {e}")
            continue
    if not sentences and content.strip():  # Fallback for slightly malformed SRT or simple timed text
        logger.info("SRT pattern found no matches, trying simpler line-by-line for timed text if any.")
        lines = content.strip().split('\n')
        time_line_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', line)
                if time_match:
                    time_line_idx = i
                    start_time_str = time_match.group(1).strip()
                    end_time_str = time_match.group(2).strip()
                    text_lines = []
                    # Collect text from subsequent lines until a blank line or another timestamp
                    for j in range(i + 1, len(lines)):
                        if not lines[j].strip() or "-->" in lines[j] or re.match(r'^\d+$', lines[j].strip()):
                            break
                        text_lines.append(lines[j].strip())

                    text = "\n".join(text_lines)
                    if text:
                        start_seconds = _parse_time_to_seconds(start_time_str, is_srt=True)
                        end_seconds = _parse_time_to_seconds(end_time_str, is_srt=True)
                        duration = _calculate_and_round_duration(start_seconds, end_seconds)
                        sentences.append({"text": text, "delay_seconds": duration})

    return sentences


def parse_webvtt(content: str) -> list:
    """Parses WebVTT content into a list of sentence dicts."""
    sentences = []
    # Remove WEBVTT header and NOTE lines
    lines = content.splitlines()
    processed_lines = []
    in_header = True
    for line in lines:
        if in_header and line.strip() == "WEBVTT":
            continue
        if in_header and not line.strip():  # Empty line after WEBVTT header
            in_header = False
            continue
        if line.strip().startswith("NOTE"):
            continue
        if not line.strip() and not processed_lines:  # Skip leading empty lines after header
            continue
        processed_lines.append(line)

    content_body = "\n".join(processed_lines).strip()

    # Regex for WebVTT cues (number optional, various timestamp formats)
    # Handles optional cue identifiers before timestamps
    pattern = re.compile(
        r'(?:.*\n)?'  # Optional cue identifier line
        r'(\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}:\d{2}\.\d{3})(?:[^\S\n].*)?\s*'  # Timestamps with optional settings
        r'([\s\S]*?)(?=\n\n(?:.*\n)?(?:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}:\d{2}\.\d{3})\s*-->|\Z)',  # Text block
        re.MULTILINE
    )

    for match in pattern.finditer(content_body):
        try:
            start_time_str = match.group(1).strip()
            end_time_str = match.group(2).strip()
            text = match.group(3).strip().replace('\r\n', '\n')

            if not text: continue

            start_seconds = _parse_time_to_seconds(start_time_str, is_srt=False)
            end_seconds = _parse_time_to_seconds(end_time_str, is_srt=False)
            duration = _calculate_and_round_duration(start_seconds, end_seconds)

            sentences.append({"text": text, "delay_seconds": duration})
        except Exception as e:
            logger.error(f"Error parsing WebVTT block: {match.group(0)[:50]}... - {e}")
            continue

    # Fallback if no blocks were found (e.g. malformed or just timestamped lines)
    if not sentences and "-->" in content_body:
        current_text_block = []
        start_seconds, end_seconds = 0, 0
        for line in content_body.splitlines():
            line_strip = line.strip()
            if "-->" in line_strip:  # Timestamp line
                if current_text_block:  # Process previous block
                    duration = _calculate_and_round_duration(start_seconds, end_seconds)
                    sentences.append({"text": "\n".join(current_text_block).strip(), "delay_seconds": duration})
                    current_text_block = []

                ts_parts = line_strip.split("-->")
                if len(ts_parts) == 2:
                    start_time_str = ts_parts[0].strip().split(" ")[-1]  # Take last part if settings exist
                    end_time_str = ts_parts[1].strip().split(" ")[0]  # Take first part if settings exist
                    start_seconds = _parse_time_to_seconds(start_time_str, is_srt=False)
                    end_seconds = _parse_time_to_seconds(end_time_str, is_srt=False)
            elif line_strip:  # Text line
                current_text_block.append(line_strip)

        if current_text_block:  # Process final block
            duration = _calculate_and_round_duration(start_seconds, end_seconds)
            sentences.append({"text": "\n".join(current_text_block).strip(), "delay_seconds": duration})

    return sentences


def parse_tsv(content: str) -> list:
    """Parses TSV content (start_ms, end_ms, text) into a list of sentence dicts."""
    sentences = []
    lines = content.strip().splitlines()

    if not lines:
        return sentences

    # Skip header if present (simple check for "start", "end", "text")
    header_line = lines[0].lower()
    if "start" in header_line and "end" in header_line and "text" in header_line:
        lines = lines[1:]

    for i, line in enumerate(lines):
        parts = line.split('\t')
        if len(parts) >= 3:
            try:
                start_ms_str, end_ms_str = parts[0], parts[1]
                text = "\t".join(parts[2:]).strip()  # Join remaining parts for text, in case text has tabs

                if not text: continue

                start_ms = int(start_ms_str)
                end_ms = int(end_ms_str)

                start_seconds = start_ms / 1000.0
                end_seconds = end_ms / 1000.0

                duration = _calculate_and_round_duration(start_seconds, end_seconds)
                sentences.append({"text": text, "delay_seconds": duration})
            except ValueError:
                logger.warning(f"Skipping invalid TSV line {i + 1}: {line[:50]}... (Non-integer time values)")
            except Exception as e:
                logger.error(f"Error parsing TSV line {i + 1}: {line[:50]}... - {e}")
        else:
            logger.warning(f"Skipping malformed TSV line {i + 1} (not enough columns): {line[:50]}...")

    return sentences


def parse_plain_text(content: str) -> list:
    """Parses a block of plain text into sentences.
    Sentences are split by non-empty lines. Default duration is 0.0s.
    """
    sentences = []
    lines = content.strip().splitlines()
    current_sentence_lines = []
    default_duration = 0.0  # Default for plain text, user to adjust

    for line in lines:
        stripped_line = line.strip()
        if stripped_line:
            # Each non-empty line is a new sentence for this simple parser
            sentences.append({"text": stripped_line, "delay_seconds": default_duration})
        # If you wanted to group by blank lines:
        # if stripped_line:
        #     current_sentence_lines.append(stripped_line)
        # elif current_sentence_lines:
        #     sentences.append({"text": "\n".join(current_sentence_lines), "delay_seconds": default_duration})
        #     current_sentence_lines = []

    # if current_sentence_lines: # Add any remaining sentence
    #     sentences.append({"text": "\n".join(current_sentence_lines), "delay_seconds": default_duration})

    return sentences