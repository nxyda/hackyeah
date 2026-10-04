from enum import Enum


class SafePlaceCategory(str, Enum):
    POLICE = "police"
    HOSPITAL = "hospital"
    FIRE_STATION = "fire_station"
    PHARMACY = "pharmacy"
    FUEL_STATION = "fuel_station"
    SHOP = "shop"
    PUBLIC_TRANSPORT = "public_transport"
    OTHER = "other"