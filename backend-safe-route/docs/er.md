# Model danych

## `road_segments`

Segmenty dróg pochodzące z OSM; `osm_way_id` jest unikalny, więc jeden rekord
odpowiada jednemu OSM way. `geom` jest linią w EPSG:4326. Dane o
oświetleniu, monitoringu i odległości do bezpiecznego miejsca nie są
przechowywane jako agregaty w tabeli; odległość do safe place jest liczona
przez repository i zwracana w DTO.

## `safe_places`

Punkty miejsc zwiększających poczucie bezpieczeństwa, z kategorią, nazwą i
informacją o dostępności całodobowej. `geom` jest punktem w WGS84
(EPSG:4326), objętym indeksem GiST. `osm_id` przechowuje opcjonalny, unikalny
identyfikator obiektu z OpenStreetMap. `opening_hours_raw` zachowuje
nieprzetworzony tekst godzin otwarcia ze źródła; może być pusty i nie jest
obecnie parsowany. Kategorie to `police`, `hospital`, `fire_station`,
`pharmacy`, `fuel_station`, `shop`, `public_transport` oraz `other`.

Publiczny, tylko do odczytu interfejs HTTP udostępnia
`GET /v1/safe-places/{safe_place_id}` oraz
`GET /v1/safe-places/nearby?lat=...&lon=...&radius_m=...`. Współrzędne
wyszukiwania są podawane jako szerokość `lat` i długość `lon`; promień jest
wyrażony w metrach, domyślnie wynosi 1000 m i może mieć maksymalnie 50 000 m.
Lista jest sortowana według odległości i każdy jej element zawiera `distance_m`;
szczegóły pojedynczego miejsca zawierają współrzędne `latitude` i `longitude`,
ale nie odległość. Oba endpointy są publiczne i nie wymagają JWT. Szczegółowy
kontrakt parametrów, odpowiedzi i błędów opisuje [specyfikacja OpenAPI](./openapi.yaml).

## `reports`

Punkty zgłoszeń użytkowników z cyklem życia, statusem i liczbą potwierdzeń.

## `users`

Konta użytkowników. `email` jest unikalny; `given_name` i `family_name` są
opcjonalne. `password_hash` zawiera hash Argon2 kont lokalnych i jest `NULL`
dla kont utworzonych wyłącznie przez logowanie społecznościowe.

## `user_identities`

Powiązanie konta z tożsamością OAuth. Para (`provider`, `provider_user_id`)
jest unikalna; konto może być powiązane z Google i Facebookiem. Usunięcie
użytkownika usuwa jego tożsamości.

## `cameras`

Kamery monitoringu z lokalizacją `location` zapisaną jako punkt geometryczny
WGS84 (`POINT`, SRID 4326). Indeks GiST umożliwia wyszukiwanie przestrzenne.

## `street_lamps`

Latarnie uliczne z lokalizacją `location` zapisaną jako punkt geometryczny
WGS84 (`POINT`, SRID 4326). Indeks GiST umożliwia wyszukiwanie przestrzenne.

Wszystkie geometrie mają indeksy GiST.
