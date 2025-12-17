from gunz_utils.enums import BaseStrEnum

class Color(BaseStrEnum):
    __ALIASES__ = {"dark": "dark_blue"}
    DARK_BLUE = "dark_blue"

print(f"Members: {list(Color)}")
try:
    print(f"Aliases: {Color.__ALIASES__}")
except AttributeError:
    print("Aliases not found")
