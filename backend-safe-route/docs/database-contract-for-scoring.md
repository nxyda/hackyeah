# Kontrakt bazy danych dla routingu i scoringu

Ten dokument opisuje minimalny zakres bazy potrzebny do podłączenia
scoringu bezpieczeństwa tras. Jest przeznaczony dla osoby przygotowującej
modele SQLAlchemy, migracje oraz dane w PostgreSQL/PostGIS lub Supabase.

## Najważniejsza zasada

Nie zapisujemy na stałe tras z Mapboxa ani wyników scoringu.

Przepływ dla pojedynczego żądania będzie wyglądał tak:

```text
Mapbox zwraca trasę
        ↓
Repository dopasowuje road_segments
        ↓
Repository pobiera raporty, przestępstwa i dane infrastruktury
        ↓
Repository tworzy SegmentSafetyInput
        ↓
Scoring oblicza wynik
        ↓
API zwraca odpowiedź
```

## Tabele wymagane w MVP

Potrzebne są cztery tabele:

1. `road_segments` — fragmenty dróg i chodników;
2. `safe_places` — miejsca, w których użytkownik może uzyskać pomoc;
3. `reports` — bieżące zgłoszenia użytkowników;
4. `crime_events` — historyczne zdarzenia kryminalne.

Nie tworzymy na tym etapie tabel `routes`, `candidate_routes`,
`route_scores` ani `route_requests`.

Routing korzysta również z tabel `street_lamps` i `cameras`. Nie zapisujemy
agregatów oświetlenia ani monitoringu na stałe w `road_segments`; dla każdego
żądania pobieramy punkty z korytarza Mapboxa i wyliczamy cechy segmentów
dynamicznie. W praktyce oznacza to:

- latarnie w promieniu 25 m od segmentu wyznaczają `lit_ratio` (z nasyceniem
  do `1.0`);
- aktywna kamera w promieniu 75 m ustawia `surveillance_nearby`;
- aktywne, niewygasłe raporty w promieniu 50 m zwiększają `reports_nearby`;
- najbliższe safe place w korytarzu dostarcza `safe_place_distance_m`;
- crime events są filtrowane metrycznie w promieniu 50 m i wpływają na
  `crime_exposure`.
- `severity` crime eventu skaluje ekspozycję przed zanikiem czasowym;
- `confirmations` raportu zwiększa jego wpływ logarytmicznie, aby wiele
  potwierdzeń wzmacniało raport bez nieograniczonej dominacji.

Wszystkie odległości są liczone po transformacji do układu metrycznego
EPSG:2180 po stronie serwisu, a selekcja rekordów w korytarzu odbywa się
przez PostGIS i indeksy przestrzenne.

## Wspólne zasady geometrii

- Używamy rozszerzenia `postgis`.
- Geometrie przechowujemy w układzie `EPSG:4326`.
- Drogi mają typ `geometry(LineString, 4326)`.
- Miejsca, raporty i zdarzenia mają typ `geometry(Point, 4326)`.
- Każda kolumna geometryczna otrzymuje indeks GiST.
- Współrzędne punktów zapisujemy zawsze w kolejności `longitude latitude`.
- Bufory tras i obliczenia serwisu używają EPSG:2180, odpowiedniego dla
  polskiego obszaru działania aplikacji; nie używamy EPSG:3857 do odległości,
  bo jego skala zależy od szerokości geograficznej.
- Odległości liczymy przez `geography` albo odpowiedni układ metryczny,
  nigdy przez zwykłe `ST_Distance` na stopniach EPSG:4326.

Przykład:

```sql
ST_DWithin(
    road_segments.geom::geography,
    :route_geometry::geography,
    20
)
```

## 1. `road_segments`

Jeden rekord oznacza fragment drogi, chodnika lub ścieżki pomiędzy węzłami
grafu OSM. Najlepiej, aby segment kończył się również w miejscu skrzyżowania,
rozwidlenia albo zmiany istotnych właściwości drogi.

### Kolumny

| Kolumna | Typ | NULL | Znaczenie |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | nie | Wewnętrzny identyfikator segmentu |
| `osm_way_id` | `BIGINT UNIQUE` | nie | Unikalny identyfikator drogi z OpenStreetMap |
| `geom` | `geometry(LineString, 4326)` | nie | Geometria segmentu |
| `length_m` | `DOUBLE PRECISION` | nie | Długość segmentu w metrach |
| `road_type` | `TEXT` | nie | Typ drogi, np. `footway`, `path`, `residential` |
| `is_tunnel` | `BOOLEAN` | nie | Czy segment prowadzi przez tunel |
| `is_footway` | `BOOLEAN` | tak | Czy segment jest chodnikiem/ścieżką pieszą |
| `source` | `TEXT` | tak | Źródło lub wersja importu danych |
| `source_updated_at` | `TIMESTAMPTZ` | tak | Czas ostatniej aktualizacji danych |

### Zasady

- `is_footway = NULL` oznacza brak pewności co do typu drogi.
- `length_m` powinno być dodatnie.
- Długość należy liczyć w metrach, np. przez `ST_Length(geom::geography)`.
- Odległość do najbliższego safe place repository liczy dynamicznie w metrach
  i zwraca jako `dist_to_safe_place_m` w `RoadSegmentDTO`; nie jest cache'owana
  w `road_segments`.
- Latarnie i kamery przechowują wyłącznie własne lokalizacje. Nie utrwalają
  agregatów `lit_ratio` ani `surveillance_nearby` w rekordzie segmentu.

### Indeksy

```sql
CREATE INDEX road_segments_geom_gist
    ON road_segments USING GIST (geom);

CREATE UNIQUE INDEX road_segments_osm_way_id_idx
    ON road_segments (osm_way_id);
```

## 2. `safe_places`

Punkty, w których użytkownik może uzyskać pomoc albo znaleźć się w miejscu
z większą obecnością ludzi.

### Kolumny

| Kolumna | Typ | NULL | Znaczenie |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | nie | Identyfikator miejsca |
| `osm_id` | `BIGINT UNIQUE` | tak | Opcjonalny, unikalny identyfikator obiektu z OpenStreetMap |
| `category` | `TEXT` | nie | Kategoria miejsca |
| `name` | `TEXT` | nie | Nazwa miejsca |
| `geom` | `geometry(Point, 4326)` | nie | Lokalizacja |
| `opening_hours_raw` | `TEXT` | tak | Oryginalne godziny otwarcia |
| `is_24_7` | `BOOLEAN` | nie | Czy miejsce działa całą dobę |
| `source` | `TEXT` | tak | Źródło danych |
| `source_updated_at` | `TIMESTAMPTZ` | tak | Czas aktualizacji |

### Zalecane kategorie

```text
police
hospital
fire_station
pharmacy
fuel_station
shop
public_transport
other
```

### Indeks

```sql
CREATE INDEX safe_places_geom_gist
    ON safe_places USING GIST (geom);
```

Repository powinno móc znaleźć najbliższe miejsce, najlepiej z uwzględnieniem
czasu `departure_time` oraz `is_24_7` / `opening_hours_raw`. Obecny routing
używa bezpiecznych miejsc z korytarza i pola `is_24_7`; pełne parsowanie
`opening_hours_raw` obsługuje podstawowe zakresy dni i godzin, np.
`Mo-Fr 08:00-16:00`; bardziej złożone reguły OSM pozostają osobnym zadaniem.

## 3. `reports`

Bieżące zgłoszenia użytkowników. Raporty nie są tym samym co historyczne,
potwierdzone zdarzenia kryminalne.

### Kolumny

| Kolumna | Typ | NULL | Znaczenie |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | nie | Identyfikator zgłoszenia |
| `category` | `TEXT` | nie | Kategoria zgłoszenia |
| `geom` | `geometry(Point, 4326)` | nie | Lokalizacja |
| `created_at` | `TIMESTAMPTZ` | nie | Czas utworzenia |
| `expires_at` | `TIMESTAMPTZ` | tak | Czas wygaśnięcia |
| `status` | `TEXT` | nie | Np. `active`, `resolved`, `expired`, `rejected` |
| `confirmations` | `INTEGER` | nie | Liczba potwierdzeń |

### Zalecane kategorie

```text
danger
harassment
poor_lighting
blocked_path
suspicious_activity
other
```

W scoringu uwzględniamy tylko raporty spełniające:

```sql
status = 'active'
AND (expires_at IS NULL OR expires_at > :departure_time)
```

### Indeksy

```sql
CREATE INDEX reports_geom_gist
    ON reports USING GIST (geom);

CREATE INDEX reports_status_idx
    ON reports (status);

CREATE INDEX reports_created_at_idx
    ON reports (created_at);
```

`confirmations` powinno mieć wartość domyślną `0` i nie może być ujemne.

`ReportRepository.get_active_in_corridor()` dodatkowo wymaga
`created_at <= departure_time` oraz traktuje `expires_at = NULL` jako brak
terminu wygaśnięcia. Dzięki temu przyszłe lub już wygasłe zgłoszenia nie
wpływają na Dijkstrę.

## 5. `street_lamps` i `cameras`

Obie tabele przechowują punktowe dane z OpenStreetMap:

| Tabela | Geometria | Użycie w routingu |
| --- | --- | --- |
| `street_lamps` | `location geometry(Point, 4326)` | obecność latarni i `lit_ratio` |
| `cameras` | `location geometry(Point, 4326)` | `surveillance_nearby` |

Kolumna nazywa się `location`, a nie `geom`, dlatego repozytoria muszą
obsługiwać ją jawnie. Każda tabela powinna mieć indeks GiST na tej kolumnie.
Brak rekordów nie jest błędem: odpowiada neutralnej wartości scoringu, a nie
automatycznie trasie maksymalnie niebezpiecznej.

Routing zachowuje zarówno kompatybilny sygnał logiczny
`surveillance_nearby`, jak i `camera_count`. Scoring używa liczby kamer
z nasyceniem przy trzech kamerach, dzięki czemu jedna i kilka kamer nie są
traktowane identycznie.

## 7. Cechy drogi

`road_type` wpływa na osobny komponent scoringu, a typy `steps`/`stairway`
obniżają komponent schodów. Do czasu dodania kolumn OSM `access` i `surface`
wartość dostępu jest wyłącznie konserwatywną heurystyką opartą o typ drogi;
nie zastępuje to prawdziwych tagów OSM.

Migracja Alembic dodaje opcjonalne kolumny:

```text
surface, smoothness, incline, lit, foot, access, crossing, highway
```

Brak wartości pozostaje jawny (`NULL`) i daje neutralny komponent oraz niższe
`data_coverage`, zamiast udawać, że droga ma najlepsze parametry.

## 6. `crime_events`

Historyczne, zanonimizowane zdarzenia kryminalne. Dane służą do obliczenia
`crime_exposure`; nie zwracamy pojedynczych zdarzeń w publicznym API.

### Kolumny

| Kolumna | Typ | NULL | Znaczenie |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL` | nie | Identyfikator zdarzenia |
| `category` | `TEXT` | nie | Kategoria zdarzenia |
| `geom` | `geometry(Point, 4326)` | nie | Przybliżona lokalizacja zdarzenia |
| `occurred_at` | `TIMESTAMPTZ` | nie | Czas zdarzenia |
| `source` | `TEXT` | nie | Źródło danych |
| `severity` | `DOUBLE PRECISION` | tak | Opcjonalna dodatkowa waga powagi |

### Zalecane kategorie

Muszą odpowiadać konfiguracji w `app/scoring.yaml`:

```text
assault
robbery
harassment
theft
vandalism
other
```

### Indeksy

```sql
CREATE INDEX crime_events_geom_gist
    ON crime_events USING GIST (geom);

CREATE INDEX crime_events_occurred_at_idx
    ON crime_events (occurred_at);

CREATE INDEX crime_events_category_idx
    ON crime_events (category);
```

### Prywatność

Tabela nie może przechowywać danych osobowych, opisów ofiar ani informacji
pozwalających zidentyfikować konkretną osobę. Lokalizacja może być
zagregowana lub niedokładna, jeśli wymaga tego źródło danych.

## Dane przekazywane do scoringu

Repository powinno zamienić rekordy z bazy na następujący kontrakt Python:

```python
SegmentSafetyInput(
    length_m=120.0,
    lit_ratio=0.8,
    reports_nearby=1,
    tunnel_m=0.0,
    safe_place_distance_m=180.0,
    is_footway=True,
    surveillance_nearby=None,
    crime_exposure=0.7,
)
```

Scoring nie powinien wiedzieć:

- z której tabeli pochodzi wartość;
- czy dane pochodzą z OSM, CSV czy Supabase;
- jak zbudowano zapytanie PostGIS;
- jak działa SQLAlchemy.

### Mapowanie danych

| Dane scoringu | Źródło |
| --- | --- |
| `length_m` | `road_segments.length_m` |
| `tunnel_m` | `road_segments.length_m`, jeśli `is_tunnel = true`, w przeciwnym razie `0` |
| `is_footway` | `road_segments.is_footway` |
| `lit_ratio` | metryka scoringu; nie jest przechowywana ani obecnie wyliczana przez repository |
| `surveillance_nearby` | metryka scoringu; nie jest przechowywana ani obecnie wyliczana przez repository |
| `safe_place_distance_m` | najbliższy `safe_places`, liczony na bieżąco przez repository |
| `reports_nearby` | aktywne `reports` w ustalonym promieniu |
| `crime_exposure` | ważone `crime_events` w ustalonym promieniu |

## Zapytania, które repository musi obsłużyć

### Segmenty blisko trasy

Wersja MVP może użyć bufora 20 metrów:

```sql
SELECT
    rs.*,
    ST_Distance(
        rs.geom::geography,
        :route_geometry::geography
    ) AS distance_to_route_m
FROM road_segments AS rs
WHERE ST_DWithin(
    rs.geom::geography,
    :route_geometry::geography,
    :match_radius_m
)
ORDER BY distance_to_route_m;
```

Później trzeba dodać dokładniejsze sortowanie po pozycji segmentu na trasie.

### Aktywne raporty

```sql
SELECT COUNT(*) AS reports_nearby
FROM reports
WHERE status = 'active'
  AND (expires_at IS NULL OR expires_at > :departure_time)
  AND ST_DWithin(
      geom::geography,
      :segment_geometry::geography,
      :report_radius_m
  );
```

### Historyczne zdarzenia

```sql
SELECT category, occurred_at, severity
FROM crime_events
WHERE occurred_at <= :departure_time
  AND ST_DWithin(
      geom::geography,
      :segment_geometry::geography,
      :crime_radius_m
  );
```

Następnie repository przekazuje zdarzenia do funkcji scoringu, która stosuje
wagi kategorii i zanik w czasie.

### Najbliższe safe place

```sql
SELECT
    id,
    category,
    name,
    ST_Distance(
        geom::geography,
        :segment_geometry::geography
    ) AS distance_m
FROM safe_places
ORDER BY geom <-> :segment_geometry
LIMIT 1;
```

Zapytanie powinno później uwzględniać dostępność miejsca w czasie przejścia.

## Uzgodnienia do potwierdzenia przed implementacją

- promień dopasowania segmentu do trasy: proponowane `20 m`;
- promień raportów: proponowane `50 m`;
- promień historycznych zdarzeń: proponowane `100 m` w dzień i `150 m` w nocy;
- sposób anonimizacji lokalizacji przestępstw;
- lista źródeł i format importu danych kryminalnych;
- czy `is_footway` ma być `NULL`, gdy OSM nie daje pewnej informacji.

## Definition of Done dla warstwy bazy

- [ ] Istnieją cztery tabele i migracja numerowana.
- [ ] Wszystkie geometrie mają SRID `4326`.
- [ ] Wszystkie geometrie mają indeksy GiST.
- [ ] Brak danych jest zapisywany jako `NULL`, a nie jako sztuczne `0`.
- [ ] `road_segments.length_m` jest przechowywane w metrach.
- [ ] Raporty można filtrować po statusie i wygaśnięciu.
- [ ] Zdarzenia kryminalne można filtrować po kategorii, czasie i odległości.
- [ ] Repository może zwrócić `RoadSegmentDTO` z odległością wyliczaną dla
  bieżących danych; mapowanie na `SegmentSafetyInput` należy do warstwy
  przygotowującej dane do scoringu.
- [ ] Do repozytorium nie trafiają sekrety ani dane osobowe.
