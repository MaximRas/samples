import re


class Color:
    """
    Class to compare colors
    Example: 'rgba(12, 15, 188, 1) and 'rgb(12, 15, 188)'
    Second color has no alpha channel so both strings aren't equal
    """
    def __init__(self, string):
        self._string = string
        prefix, colors = re.findall(r"(rgb\w?)\((.+)\)", string)[0]
        self.r, self.g, self.b, *self.a = [float(clr.strip()) for clr in colors.split(",")]
        self.a = self.a or None

    def __hash__(self):
        return hash(f"{self.r}+{self.g}+{self.b}")

    def __str__(self):
        return self._string

    def __eq__(self, color):
        return self.r == color.r and self.g == color.g and self.b == color.b
