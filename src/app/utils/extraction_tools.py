import re

def extract_form_id(slug):
    """
    Extracts form ID from the slug.

    Args:
        slug (str): Slug string containing form ID.

    Returns:
        str: Form ID or None.
    """
    match = re.search(r'/(\d+)', slug)
    return match.group(1) if match else None