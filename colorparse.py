import re

class ColorFormatError(Exception):
    def __init__(self, input):
        self.message = "invalid color: " + input

class ColorValueError(Exception):
    def __init__(self, input):
        self.message = "RGBA value must be between 0 and 255: " + input

color_pattern = r'\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*(\d+)\s*)?\)\s*'

def parse(color_str):
    match = re.fullmatch(color_pattern, color_str)
    if match is None:
        raise ColorFormatError(color_str)
    rgba_list = list(match.group(1, 2, 3, 5))
    if rgba_list[3] is None:
        rgba_list.pop(-1)
    color = tuple(map(int, rgba_list))
    if max(color) > 255:
        raise ColorValueError(color_str)
    return color
