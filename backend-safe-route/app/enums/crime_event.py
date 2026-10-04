from enum import Enum


class CrimeEventCategory(str, Enum):
    ASSAULT = "assault"
    ROBBERY = "robbery"
    HARASSMENT = "harassment"
    THEFT = "theft"
    VANDALISM = "vandalism"
    OTHER = "other"
