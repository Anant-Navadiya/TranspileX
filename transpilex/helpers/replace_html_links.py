import re

def replace_html_links(content: str, new_extension: str) -> str:
    """
    Replaces `.html` with `.php` in href and action attributes.
    Useful for converting HTML projects to PHP.
    """

    def replace_match(match):
        url = match.group(1)
        if new_extension == "":
            return "/" if url.endswith("index.html") else url  # skip others
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
