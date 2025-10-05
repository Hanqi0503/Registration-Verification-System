def process_file_uploads(data, key):
    """
    Processes file uploads and returns the URLs as a list.

    Args:
        data (dict): Dict containing request data.
        key (str): Key to look for file uploads.

    Returns:
        list: List of file upload URLs.
    """
    file_upload_urls = []
    if key in data:
        file_uploads = data[key]
        if isinstance(file_uploads, list):
            file_upload_urls = file_uploads
    return file_upload_urls