def validate_input_data(dc_data, ac_data):
    """
    Simple validation of required dictionary contents.
    """
    if dc_data is None or ac_data is None:
        return False, "Missing data"
    return True, ""
