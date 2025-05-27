# myapp/utils/json_validator.py
import jsonschema
import logging  # Import logging

logger = logging.getLogger(__name__)  # Get logger for this module

def validate_json(data, schema, file_description="JSON data"):
    """
    Validates JSON data against a given schema.

    Args:
        data: The Python object (from json.load) to validate.
        schema (dict): The jsonschema definition.
        file_description (str): A description for error messages.

    Returns:
        tuple: A tuple containing (bool, Exception or None).
               (True, None) if validation succeeds.
               (False, ValidationError) if validation fails.
               (False, Exception) if an unexpected error occurs.
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        logger.debug(f"Validation successful for {file_description}.")
        return True, None
    except jsonschema.exceptions.ValidationError as e:
        path = "->".join(map(str, e.path))
        logger.warning(f"Validation Error in {file_description}: {e.message} (at path: {path})")
        return False, e
    except Exception as e:
        logger.error(f"An unexpected error occurred during validation of {file_description}: {e}", exc_info=True)
        return False, e