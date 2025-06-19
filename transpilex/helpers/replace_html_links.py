import re

def replace_html_links(content: str, new_extension: str) -> str:
    """
    Replaces '.html' with the specified new_extension in href and action attributes.
    If new_extension is an empty string, it removes '.html' (except for index.html which becomes '/').
    """

    def replace_match(match):
        url = match.group(1)
        if new_extension == "":
            if url.endswith("index.html"):
                return "/"  # Convert index.html to /
            else:
                return url.replace(".html", "") # Remove .html for other files
        else:
            return url.replace(".html", new_extension)

    # Replace href
    content = re.sub(
        r"""(?<=href=['"])([^'"]+\.html)(?=['"])""",
        replace_match,
        content
    )

    # Replace action
    content = re.sub(
        r"""(?<=action=['"])([^'"]+\.html)(?=['"])""",
        replace_match,
        content
    )

    return content