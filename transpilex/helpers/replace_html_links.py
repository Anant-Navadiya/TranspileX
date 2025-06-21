import re


def replace_html_links(content: str, new_extension: str) -> str:
    """
    Replaces '.html' with the specified new_extension in href and action attributes.
    If new_extension is an empty string, it removes '.html' (except for index.html which becomes '/').
    Adds a leading '/' ONLY to URLs that originally had a '.html' extension and are being modified.
    URLs starting with http://, https://, //, or / will NOT be modified (unless they are a /path/to/file.html that needs extension change).
    """

    def replace_match(match):
        original_url = match.group(1)

        # 1. Handle absolute or already root-relative URLs first:
        # If the URL already starts with these, return it as is, regardless of .html
        if original_url.startswith(('http://', 'https://', '//', '/')):
            # Special case: If it's a root-relative path AND ends with .html
            # we should still process its extension, but maintain its leading slash.
            if original_url.endswith(".html"):
                temp_url_without_html = original_url.replace(".html", "")
                if new_extension == "":
                    return temp_url_without_html if not temp_url_without_html.endswith("/index") else "/"
                else:
                    return temp_url_without_html + new_extension
            else:
                return original_url  # Don't modify if it's already /path/to/file and no .html

        # 2. Process truly relative URLs (e.g., "auth-sign-in", "products-grid.html")
        # Check if the original URL ends with .html
        if original_url.endswith(".html"):
            # This is a URL that will have its extension changed/removed, so we add '/'
            temp_url_without_html = original_url.replace(".html", "")

            # Decide what the final path should be (with or without /index)
            if new_extension == "":
                # For clean URLs, /index.html becomes /, others become /path
                processed_url_segment = temp_url_without_html if not temp_url_without_html.endswith("index") else ""
                final_url = "/" + processed_url_segment  # Add leading slash
                if final_url == "//":  # Handle cases where index.html becomes just "/"
                    final_url = "/"
                return final_url
            else:
                # For new extension, add leading slash and new extension
                return "/" + temp_url_without_html + new_extension
        else:
            # If the URL does NOT end with .html (e.g., "auth-sign-in"),
            # and it's not absolute, we return it as is (no leading slash added)
            # as no extension change is happening.
            return original_url

    # Regex remains broad to capture all potential links
    content = re.sub(
        r"""(?<=href=['"])([^'"]+)(?=['"])""",
        replace_match,
        content
    )

    content = re.sub(
        r"""(?<=action=['"])([^'"]+)(?=['"])""",
        replace_match,
        content
    )

    return content