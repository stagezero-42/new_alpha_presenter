# myapp/utils/json_validator.py
import jsonschema

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
        print(f"Validation successful for {file_description}.")
        return True, None
    except jsonschema.exceptions.ValidationError as e:
        path = "->".join(map(str, e.path))
        print(f"Validation Error in {file_description}: {e.message} (at path: {path})")
        return False, e
    except Exception as e:
        print(f"An unexpected error occurred during validation of {file_description}: {e}")
        return False, e