import re


def clean_relative_asset_paths(content: str) -> str:
    """
    Cleans up <script src="..."> and <link href="..."> paths:
    - Removes leading 'assets/', '../assets/', '..assets/' etc. from local paths
    - Does NOT modify URLs containing 'assets/' in the middle (like external CDNs)
    """

    def clean_match(match):
        attr = match.group(1)
        path = match.group(2).strip()

        # Skip if it contains :// or starts like cdn.domain.com
        if re.match(r'^(?:[a-z]+:)?//|^[\w.-]+\.\w+/', path):
            return match.group(0)

        # Clean if path starts with relative asset path
        cleaned = re.sub(r'^(\.{0,2}/)*assets', '', path)
        return f'{attr}="{cleaned}"'

    # Clean both href="..." and src="..."
    return re.sub(r'\b(src|href)\s*=\s*["\']([^"\']+)["\']', clean_match, content)
