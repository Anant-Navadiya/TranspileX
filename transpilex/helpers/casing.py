import re


def to_pascal_case(s: str):
    # First split on _ - and spaces
    parts = re.split(r"[_\-\s]+", s)

    # For each part, split camelCase into separate words
    def split_camel_case(word):
        return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', word)

    words = []
    for part in parts:
        words.extend(split_camel_case(part))

    # Capitalize all parts and join
    return "".join(word.capitalize() for word in words if word)
