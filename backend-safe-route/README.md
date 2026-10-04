# Safe Route Backend

Backend aplikacji mobilnej wyznaczającej bezpieczną trasę pieszą. Projekt
korzysta z FastAPI, SQLAlchemy, PostgreSQL/PostGIS oraz Supabase jako warstwy
bazy danych.

Najważniejsza zasada architektury jest prosta:

```text
HTTP request
    │
    ▼
FastAPI application
    │
    ▼
Router
    │
    ▼
Service
    │
    ▼
Repository
    │
    ▼
SQLAlchemy
    │
    ▼
Supabase / PostgreSQL + PostGIS
```

Repozytorium zawiera działający start aplikacji, konfigurację, `GET /health`,
klienta Mapbox, lokalny routing po grafie segmentów oraz niezależny moduł
scoringu. Endpoint routingu wykorzystuje Mapbox jako trasę bazową, pobiera
lokalny korytarz segmentów i generuje safety-aware kandydatów algorytmem
grafowym.

## Szybki start

Wymagany jest Python 3.12, Git oraz lokalny PostgreSQL z rozszerzeniem PostGIS.
Projekt nie wymaga Dockera.

```bash
git clone <adres-repozytorium>
cd backend-safe-route
python3.12 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Jeśli korzystamy z lokalnej bazy, migracje uruchamiamy przez Alembica:

```bash
createdb saferoute
psql saferoute -c "CREATE EXTENSION IF NOT EXISTS postgis;"
alembic upgrade head
```

Uruchomienie:

```bash
uvicorn app.main:app --reload
```

Adresy:

- API: <http://127.0.0.1:8000>
- Swagger: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- health check: <http://127.0.0.1:8000/health>

## Uruchomienie routingu i mapy demonstracyjnej

Algorytm routingu uruchamia się przez endpoint `POST /v1/route`. Serwis
wywołuje Mapbox, pobiera segmenty z bufora trasy z PostGIS, buduje lokalny
graf i uruchamia Dijkstrę dla wariantów szybkich oraz safety-aware.

Najprostszy sposób na wygenerowanie kompletnego przykładu wraz z mapą Krakowa:

1. Upewnij się, że `.env` zawiera `API_MODE=live`, działające dane bazy oraz
   `MAPBOX_SECRET_TOKEN`.
2. Uruchom API w pierwszym terminalu:

   ```bash
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

3. W drugim terminalu, z aktywnym tym samym środowiskiem, uruchom generator:

   ```bash
   python -m mock_visualization.generate_map
   ```

Generator:

- wysyła rzeczywisty request do `POST /v1/route`;
- korzysta z Mapboxa i lokalnego grafu Dijkstry;
- pobiera crime events, latarnie, kamery, safe places i aktywne reports
  z bieżącego korytarza;
- wylicza cechy bezpieczeństwa segmentów przestrzennie: oświetlenie,
  monitoring, zgłoszenia i odległość do safe place;
- zapisuje mapę do [mock_visualization/krakow_routes.html](./mock_visualization/krakow_routes.html).

Otwórz plik HTML w przeglądarce. Trasy można klikać: wybrana zostaje
podświetlona i przeniesiona na wierzch, a pozostałe są tymczasowo przygaszone.
Kliknięcie trasy otwiera też popup z dystansem, czasem przejścia i safety
score. Czerwone punkty oznaczają historyczne crime events; kliknięcie punktu
pokazuje jego kategorię, datę i severity.

### Jak dane wpływają na trasę

`RouteService` nie zakłada, że agregaty infrastruktury są zapisane w
`road_segments`. Po pobraniu korytarza z Mapboxa repozytoria PostGIS pobierają
punkty z metrycznym buforem, a serwis przypisuje je do segmentów przez indeks
przestrzenny:

- latarnie w promieniu 25 m wpływają na `lit_ratio`;
- kamery w promieniu 75 m wpływają na `surveillance_nearby`;
- aktywne i niewygasłe reports w promieniu 50 m wpływają na
  `reports_nearby`, z uwzględnieniem czasu wyjazdu;
- najbliższe safe place dostarcza `safe_place_distance_m`;
- crime events w promieniu 50 m dostarczają `crime_exposure` z zanikiem
  w czasie.

Brak danych jest obsługiwany neutralnie. Dokładne parsowanie
`opening_hours_raw` dla safe places nie jest jeszcze częścią MVP.

### Testowe reports

Do lokalnych testów można wygenerować powtarzalny zestaw aktywnych zgłoszeń
wokół trasy Dworzec Główny–Kościół Mariacki:

```bash
# tylko podgląd, bez zapisu
.venv/bin/python -m scripts.generate_random_reports --count 20 --seed 20261004

# zapis do bazy dla pierwszego aktywnego użytkownika
.venv/bin/python -m scripts.generate_random_reports \
  --count 20 --seed 20261004 --apply
```

Generator nie usuwa istniejących zgłoszeń. Ten sam seed tworzy ten sam układ
punktów, ale `created_at` i `expires_at` są liczone względem chwili
uruchomienia.

Przydatne polecenia:

```bash
# sprawdzenie samego endpointu bez wizualizacji
curl -X POST http://127.0.0.1:8000/v1/route \
  -H 'content-type: application/json' \
  -d '{
    "start": {"lat": 50.0687, "lon": 19.9450},
    "end": {"lat": 50.06143, "lon": 19.93658},
    "departure_time": "2026-10-03T20:18:00+02:00",
    "safety_weight": 1.0,
    "profile": "walking"
  }'

# wygenerowanie mapy po zmianie danych lub kodu
python -m mock_visualization.generate_map
```

Domyślne punkty demonstracyjne generatora są zdefiniowane w
`mock_visualization/generate_map.py`. Można je zmienić w stałej `REQUEST`, aby
sprawdzać inne fragmenty Krakowa. Generator jest narzędziem developerskim i
nie jest częścią produkcyjnego klienta mobilnego.

## Konfiguracja

Konfiguracja jest ładowana przez `pydantic-settings` z pliku `.env`.
Bezpieczny szablon znajduje się w [.env.example](./.env.example).

| Zmienna | Znaczenie |
| --- | --- |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | Parametry połączenia z PostgreSQL albo Supabase |
| `DB_SSL` | Wymaga SSL dla połączenia z bazą (domyślnie `true`; lokalny PostgreSQL: `false`) |
| `MAPBOX_SECRET_TOKEN` | Sekretny token Mapbox; nie commitować |
| `JWT_SECRET_KEY` | Tajny klucz JWT, co najmniej 32 bajty; wygenerować osobno dla każdego środowiska |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Czas życia tokenu dostępu (domyślnie 15 minut) |
| `JWT_ISSUER` | Identyfikator wystawcy tokenów JWT |
| `ADMIN_SESSION_SECRET` | Osobny klucz sesji panelu admina, minimum 32 bajty; bez niego panel webowy jest wyłączony |
| `ADMIN_COOKIE_SECURE` | Wymusza Secure cookie panelu; ustaw `false` wyłącznie lokalnie bez HTTPS |
| `GOOGLE_CLIENT_ID` | Client ID aplikacji OAuth Google; wymagany dla logowania Google |
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | Dane aplikacji Meta; wymagane dla logowania Facebook |
| `FACEBOOK_GRAPH_API_VERSION` | Wersja Graph API używana do weryfikacji tokenu |
| `API_MODE` | `mock` podczas developmentu albo `live` dla integracji |
| `LOG_LEVEL` | Poziom logowania: `CRITICAL`, `ERROR`, `WARNING`, `INFO` lub `DEBUG` (domyślnie `INFO`) |

Klucz JWT można wygenerować poleceniem `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Klucz panelu wygeneruj niezależnie: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Ustawienia są walidowane przy starcie przez `pydantic-settings`; port bazy
musi mieścić się w zakresie 1–65535, a sekrety są maskowane w reprezentacji
obiektu konfiguracji.
Logi aplikacji zawierają metodę, szablon ścieżki, status, czas odpowiedzi i
identyfikator żądania (`X-Request-ID`), ale nie query string, współrzędne ani
poświadczenia. Nieobsłużone wyjątki są logowane wraz z identyfikatorem żądania
i typem błędu, bez treści mogącej zawierać dane wejściowe. Logger klienta HTTP
jest ograniczony tak, by nie ujawniać URL-i z tokenami.
Endpoint `POST /v1/auth/login` przyjmuje JSON
`{"email": "...", "password": "..."}` i zwraca krótko żyjący token Bearer.
Hasła są weryfikowane jako hashe Argon2;
odpowiedź błędu logowania nie ujawnia, czy konto istnieje. W produkcji wymagaj
HTTPS i ograniczaj częstotliwość prób logowania na bramie API.

`POST /v1/auth/register` tworzy konto przez e-mail i hasło (minimum 12 znaków);
`given_name` i `family_name` są opcjonalne. Endpoint zwraca token JWT oraz
podstawowy profil użytkownika. Logowanie społecznościowe działa przez
`POST /v1/auth/oauth/google` z tokenem ID Google albo
`POST /v1/auth/oauth/facebook` z tokenem dostępu Facebooka, w obu przypadkach
w polu `credential`. Token przekazany przez aplikację jest weryfikowany przez
serwer bezpośrednio u danego dostawcy. Klucze OAuth pozostają wyłącznie na
serwerze; aplikacja mobilna używa własnych publicznych ustawień klienta OAuth.
Dla Google aplikacja mobilna musi pobrać token ID z audience równym skonfigurowanemu
`GOOGLE_CLIENT_ID` (zwykle web client ID przekazany SDK jako `serverClientId`);
token Facebooka musi pochodzić z aplikacji o `FACEBOOK_APP_ID`.
Nazwę i e-mail pobieramy z potwierdzonego profilu dostawcy. Dla Facebooka konto
musi udostępniać adres e-mail. Istniejące konto z tym samym adresem nie jest
automatycznie łączone — użytkownik musi zalogować się dotychczasową metodą.

## Udostępnianie bieżącej lokalizacji

Udostępnianie wymaga tokenu Bearer. Użytkownik rozpoczyna sesję, podając
lokalizację i czas udostępniania (od 1 sekundy do 24 godzin). API zwraca
czterocyfrowy kod. W trakcie sesji aplikacja może wysyłać zmiany lokalizacji;
odbiorca odczytuje zawsze jej najnowszą zapisaną wartość. Kod wygasa razem
z sesją, a właściciel może ją wcześniej zakończyć. Na konto może przypadać
jedna aktywna sesja udostępniania.

| Metoda i ścieżka | Działanie |
| --- | --- |
| `POST /v1/location-shares` | Rozpoczyna sesję (`lat`, `lon`, `duration_seconds`) i zwraca kod |
| `GET /v1/location-shares/current` | Zwraca własny kod i bieżącą lokalizację |
| `PUT /v1/location-shares/current/location` | Aktualizuje własną lokalizację |
| `GET /v1/location-shares/{code}` | Odczytuje lokalizację udostępnioną kodem; bez uprawnień do zapisu |
| `DELETE /v1/location-shares/current` | Natychmiast unieważnia własny kod |

Każde żądanie wymaga nagłówka `Authorization: Bearer <token>`. Przykład
utworzenia sesji:

```json
{
  "lat": 50.0614,
  "lon": 19.9366,
  "duration_seconds": 1800
}
```

Kod ma tylko 4 cyfry, dlatego endpoint odczytu jest dostępny wyłącznie dla
zalogowanych kont; w produkcji należy dodatkowo ograniczyć częstotliwość prób
na bramie API i zawsze używać HTTPS.

Przed wdrożeniem zastosuj migracje poleceniem `alembic upgrade head`.
Konta OAuth są przechowywane w `user_identities`, a konto utworzone wyłącznie
przez dostawcę społecznościowego nie ma hasła lokalnego. Migracji nie można
cofnąć, gdy takie konta istnieją; downgrade jawnie odmówi działania zamiast
usuwać konta lub nadawać im puste hasła.

## Panel administracyjny

Szczegółowa instrukcja uruchomienia, konfiguracji sekretu, tworzenia administratora
i korzystania z panelu znajduje się w [dokumentacji panelu](./docs/admin.md).

Konta mają role `user` i `admin`; nowe rejestracje dostają zawsze rolę `user`.
Po migracji utwórz pierwszego administratora poleceniem
`python -m app.cli create-admin --email admin@example.com`. Hasło jest pobierane
interaktywnie, nie trafia do historii poleceń; dla istniejącego konta polecenie
ustawi hasło lokalne i nada rolę administratora.

Skonfiguruj `ADMIN_SESSION_SECRET` (inny niż `JWT_SECRET_KEY`) i otwórz
<http://127.0.0.1:8000/admin>. Panel SQLAdmin zapewnia CRUD tabel użytkowników,
tożsamości OAuth, zgłoszeń i potwierdzeń, kamer, latarni, zdarzeń kryminalnych,
segmentów dróg oraz bezpiecznych miejsc. Geometrie edytuje się w WKT, np.
`POINT(21.01 52.23)` albo `LINESTRING(21.01 52.23, 21.02 52.24)`.
Formularze tworzenia i edycji encji przestrzennych oraz ich podgląd szczegółów
zawierają mapę do wybierania i oglądania lokalizacji; szczegóły opisuje
[dokumentacja panelu](./docs/admin.md).
Widok `Location sharing` pozwala monitorować aktywne udostępnienia lokalizacji
i natychmiast je unieważniać; ich historia jest dostępna tylko do odczytu.
Widok `Route planner` wyznacza testową trasę tak samo jak API, pokazuje
porównanie wariantów i mapę, bez zapisywania wyników.
`ADMIN_COOKIE_SECURE=false` jest przeznaczone wyłącznie do lokalnego HTTP;
wdrożenie produkcyjne wymaga HTTPS i bezpiecznych ciasteczek. Ogranicz dostęp
do `/admin` na reverse proxy i włącz tam rate limiting logowania.

API administracyjne `GET /v1/admin/users`, `PATCH /v1/admin/users/{user_id}` i
`DELETE /v1/admin/users/{user_id}` wymaga Bearer JWT administratora. Nie zwraca
hashy haseł i nie pozwala wyłączyć, zdegradować ani usunąć ostatniego aktywnego
administratora. Panel jest domyślnie wyłączony, jeśli nie ustawiono silnego
`ADMIN_SESSION_SECRET`; endpointy wymagające roli admin nadal korzystają z JWT.

### Bezpieczne miejsca

Publiczne endpointy `GET /v1/safe-places/nearby` i
`GET /v1/safe-places/{safe_place_id}` udostępniają bezpieczne miejsca wyłącznie
do odczytu i nie wymagają tokenu. Wyszukiwanie okolicy wymaga współrzędnych
`lat` (szerokość) i `lon` (długość) w WGS84; opcjonalne `radius_m` określa
promień w metrach (domyślnie 1000, zakres `(0, 50000]`). Wyniki są sortowane
od najbliższego, a brak wyników zwraca `[]`.

```bash
curl "http://127.0.0.1:8000/v1/safe-places/nearby?lat=50.06143&lon=19.93658&radius_m=1500"
curl "http://127.0.0.1:8000/v1/safe-places/17"
```

Każdy element zawiera `id`, `category`, `name`, `opening_hours_raw`,
`is_24_7`, `latitude` i `longitude`; odpowiedź wyszukiwania dodaje
`distance_m`. Kategorie to `police`, `hospital`, `fire_station`, `pharmacy`,
`fuel_station`, `shop`, `public_transport` i `other`. Surowy zapis godzin
otwarcia może być pusty i nie jest interpretowany — `is_24_7` jest osobną
flagą. Nieistniejący identyfikator zwraca `404`, a niepoprawne parametry
zapytania `422`. Pełny kontrakt, przykłady odpowiedzi i schematy znajdują się
w [specyfikacji OpenAPI](./docs/openapi.yaml); kolumny tabeli i ich
przeznaczenie opisuje [model danych](./docs/er.md).

Zgłoszenia wymagają nagłówka `Authorization: Bearer <access_token>`. Dostępne
operacje to `GET /v1/reports`, `POST /v1/reports`,
`PATCH /v1/reports/{report_id}` i `DELETE /v1/reports/{report_id}`. Lista,
edycja i usuwanie obejmują wyłącznie zgłoszenia zalogowanego użytkownika; cudze
lub nieistniejące zgłoszenie zwraca `404`.
Tworzenie przyjmuje np. `{"category":"danger","lat":52.23,"lon":21.01}`;
edycja przyjmuje kategorię i/lub oba współrzędne `lat` i `lon`.

Publiczne dane przestrzenne są dostępne bez logowania w endpointach:

- `GET /v1/safe-places/nearby?lat=...&lon=...&radius_m=...` oraz
 `GET /v1/safe-places/{id}`;
- `GET /v1/cameras/nearby?lat=...&lon=...&radius_m=...` oraz
 `GET /v1/cameras/{id}`;
- `GET /v1/street-lamps/nearby?lat=...&lon=...&radius_m=...` oraz
 `GET /v1/street-lamps/{id}`;
- `GET /v1/crime-events/nearby?lat=...&lon=...&radius_m=...` oraz
 `GET /v1/crime-events/{id}`.

Zapytanie `crime-events/nearby` przyjmuje dodatkowo opcjonalne filtry
`occurred_after` i `occurred_before` w formacie ISO 8601. Odpowiedzi
przestrzenne zawierają `latitude`, `longitude` i `distance_m` dla wariantu
`nearby`; zdarzenia historyczne zawierają również kategorię, czas, źródło i
opcjonalny `severity`. Domyślny promień wynosi 1000 m, a maksymalny 50 000 m.

Supabase udostępnia bazę PostgreSQL, dlatego aplikacja łączy się z nim przez
parametry `DB_*`. Kod aplikacji nie powinien korzystać bezpośrednio z klienta
Supabase ani wykonywać surowych zapytań w routerach.

## Struktura projektu

```text
backend-safe-route/
├── app/
│   ├── api/v1/
│   │   ├── auth_router.py        # rejestracja i logowanie lokalne/OAuth
│   │   ├── dependencies.py       # bieżący użytkownik i walidacja JWT
│   │   ├── report_router.py      # endpointy zgłoszeń
│   │   └── router.py             # rejestracja routerów v1
│   ├── security.py               # podpisywanie i weryfikacja JWT
│   ├── database/
│   │   ├── base.py               # baza deklaratywna SQLAlchemy
│   │   └── session.py            # engine, sessionmaker, dependency
│   ├── models/
│   │   ├── road_segment.py       # tabela road_segments
│   │   ├── safe_place.py         # tabela safe_places
│   │   ├── report.py             # tabela reports
│   │   ├── crime_event.py        # historia zdarzeń
│   │   ├── user.py               # użytkownicy
│   │   ├── user_identity.py      # zewnętrzne tożsamości OAuth
│   │   ├── camera.py             # kamery i ich lokalizacje
│   │   └── street_lamp.py        # latarnie i ich lokalizacje
│   ├── repositories/
│   │   ├── route_repository.py   # zapytania danych tras
│   │   ├── report_repository.py  # zapytania danych zgłoszeń
│   │   ├── user_repository.py    # odczyt użytkownika po e-mailu
│   │   ├── camera_repository.py  # odczyt i zapis kamer
│   │   └── street_lamp_repository.py # odczyt i zapis latarni
│   ├── schemas/
│   │   ├── auth.py               # kontrakt logowania i tokenu
│   │   ├── report.py             # kontrakt zgłoszeń
│   │   ├── road_segment.py       # DTO segmentu z bieżącą odległością do safe place
│   │   └── route.py              # kontrakt POST /v1/route
│   ├── services/
│   │   ├── auth_service.py       # rejestracja i wydawanie JWT
│   │   ├── oauth_provider_service.py # weryfikacja tokenów Google i Facebook
│   │   ├── route_service.py       # przypadek użycia routingu
│   │   └── report_service.py      # przypadek użycia zgłoszeń
│   ├── config.py                  # ustawienia z .env
│   ├── main.py                    # obiekt FastAPI i health check
│   └── scoring.yaml               # przyszłe wagi day/night
├── data-pipeline/                 # przygotowanie danych OSM
├── mock_visualization/            # mapa HTML tras i crime events
│   ├── generate_map.py            # request live + generowanie mapy
│   └── krakow_routes.html         # wygenerowany artefakt lokalny
├── docs/                          # OpenAPI i opis tabel
├── scripts/                       # narzędzia developerskie
├── alembic/
│   ├── env.py                     # konfiguracja migracji
│   └── versions/                  # numerowane migracje schematu
├── tests/                         # testy
├── requirements.txt
└── README.md
```

## Co trafia do którego miejsca?

### `app/api/v1/*_router.py` — Router

Router jest warstwą HTTP. Odpowiada za:

1. przyjęcie requestu;
2. walidację przez model Pydantic;
3. utworzenie lub otrzymanie serwisu;
4. zwrócenie modelu odpowiedzi i właściwego statusu HTTP.

Router **nie** powinien zawierać SQL, obliczeń scoringu, wywołań Mapbox ani
reguł biznesowych. Nazwy plików mają końcówkę `_router.py`, żeby od razu było
jasne, że są to endpointy.

`app/api/v1/router.py` agreguje routery wersji v1, a `app/main.py` dołącza
całe API jednym wywołaniem. Zależności HTTP związane z tą wersją API,
na przykład weryfikacja bieżącego użytkownika, znajdują się obok routerów
w `app/api/v1/dependencies.py`. `app/security.py` obsługuje podpisywanie
i weryfikację JWT niezależnie od warstwy HTTP.

### `app/services/*_service.py` — Service

Service opisuje przypadek użycia, czyli co aplikacja ma zrobić z requestem.
`RouteService` będzie koordynował pobranie danych, Mapbox, map matching,
scoring i przygotowanie odpowiedzi. `ReportService` będzie obsługiwał reguły
zgłoszeń.

Service może korzystać z repository, ale nie powinien znać szczegółów tabel,
łączenia z bazą ani składni SQL. Tutaj trafiają decyzje biznesowe.

`RouteService` łączy Mapbox, korytarz segmentów, lokalny graf i scoring. Dla
jednego requestu buduje warianty fastest, safety-aware i safest, a następnie
ocenia je wspólnym modułem scoringu.

### `app/routing/` — lokalny graf

`routing/local_graph.py` buduje lokalny graf z końców segmentów
`road_segments`. Koszt krawędzi bazuje na czasie przejścia i karze za ryzyko.
Algorytm generuje kolejne kandydatury z karą za użycie segmentów poprzednich
tras. Graf jest ograniczony do bufora 3 km wokół trasy Mapboxa.

### `app/repositories/*_repository.py` — Repository

Repository jest jedynym miejscem, które pobiera i zapisuje dane aplikacji.
Korzysta z sesji SQLAlchemy i modeli z `app/models/`.

Tutaj trafiają:

- zapytania przestrzenne PostGIS;
- filtrowanie raportów;
- odczyt segmentów i bezpiecznych miejsc;
- mapowanie rekordów bazy na dane używane przez service.

Repository nie powinno decydować, która trasa jest „najbezpieczniejsza”.

### `app/database/` — SQLAlchemy

`database/session.py` definiuje async engine, `sessionmaker` oraz zależność, która
udostępni sesję podczas requestu. `database/base.py` zawiera wspólną bazę
deklaratywną modeli.

To jest techniczny adapter do PostgreSQL/Supabase. Nie umieszczamy tu logiki
tras ani kodu HTTP.

### `app/models/` — modele bazy

Każdy plik `*_model.py` opisuje jedną tabelę SQLAlchemy. Modele powinny
odzwierciedlać migracje w `alembic/versions/`. Zmiana kolumny wymaga zmiany
modelu, migracji i dokumentacji ERD.

### `app/schemas/` — modele API

Schematy Pydantic opisują requesty i response'y publicznego API. Nie są tym
samym co modele SQLAlchemy. Schemat API może łączyć dane z kilku tabel i nie
powinien ujawniać szczegółów bazy.

### `data-pipeline/`

Skrypty importu i przygotowania danych OSM. Pipeline zapisuje dane do tabel
przez ustalony kontrakt bazy, ale nie jest częścią obsługi requestu HTTP.

### `alembic/`

Alembic jest jedynym mechanizmem migracji w projekcie. Nową zmianę tworzymy
poleceniem:

```bash
alembic revision -m "describe schema change"
```

Następnie uruchamiamy ją lokalnie:

```bash
alembic upgrade head
```

Nie zmieniamy migracji, która trafiła już na wspólną gałąź. Supabase jest
wyłącznie hostowaną bazą PostgreSQL/PostGIS — schemat aplikacji wersjonujemy
w Alembicu.

### `docs/`

`docs/openapi.yaml` opisuje kontrakt API, a `docs/er.md` opisuje tabele i
relacje. Dokumentację aktualizujemy w tym samym PR co zmianę kodu; w razie
rozbieżności z działającą aplikacją kontrakt należy uzgodnić z routerami i
schematami Pydantic.

## Przykładowy przepływ requestu

Dla `POST /v1/route` przepływ będzie następujący:

1. `route_router.py` odbiera `RouteRequest`;
2. `RouteService.calculate_route()` koordynuje przypadek użycia;
3. `RouteRepository.find_route_data()` pobiera segmenty, raporty i bezpieczne
   miejsca;
4. repository wykonuje zapytania przez SQLAlchemy;
5. SQLAlchemy komunikuje się z PostgreSQL w Supabase;
6. service oblicza wynik i zwraca `RouteResponse`;
7. router serializuje odpowiedź HTTP.

## Baza i migracje

Pierwsza migracja tworzy:

- `road_segments` — segmenty dróg i ich geometrie LineString, z odległością do
  najbliższego bezpiecznego miejsca obliczaną dynamicznie;
- `street_lamps` — latarnie uliczne i geometrie Point;
- `safe_places` — bezpieczne miejsca i geometrie Point;
- `reports` — zgłoszenia użytkowników;
- indeksy GiST dla geometrii.

Przed PR-em z migracją uruchom `alembic upgrade head`, sprawdź ją na lokalnej
bazie i zaktualizuj [docs/er.md](./docs/er.md).

## Testy

```bash
pytest
pytest tests/test_health.py -q
python -m compileall -q app scripts data-pipeline tests
git diff --check
```

`pytest` raportuje również coverage aplikacji. Testy PostGIS wymagają
dedykowanej lokalnej bazy, uruchamianej przez `docker-compose.test.yml`;
instrukcje konfiguracji, seedowania, resetowania oraz raportu HTML są w
[docs/testing.md](./docs/testing.md). Testy nie używają bazy z `.env`, a ruch
sieciowy poza loopback jest blokowany.

Nowy service lub repository powinien dostać testy dla typowego przypadku,
walidacji danych i błędu. Testy routerów powinny sprawdzać kontrakt HTTP, a
testy repository mogą korzystać z osobnej testowej bazy lub kontrolowanej
sesji.

## Kontrola wersji i praca zespołowa

Pracujemy na krótkich branchach tworzonych z aktualnego `main`:

```text
feature/route-service
feature/report-repository
feature/sqlalchemy-models
fix/route-validation
docs/architecture-readme
```

Commity powinny być małe i opisowe:

```text
feat: add route repository template
fix: validate route coordinates
docs: describe repository layer
test: cover route service
chore: update dependencies
```

Przed otwarciem PR:

- uruchom `pytest`;
- uruchom `git diff --check`;
- opisz zakres zmiany i sposób testowania;
- wskaż zmiany API, konfiguracji lub migracji;
- nie dodawaj `.env`, `venv/`, `.venv/`, tokenów ani dumpów bazy.

Jedna gałąź powinna odpowiadać jednemu tematowi. Nie mieszamy implementacji
scoringu z przypadkowym formatowaniem całego projektu.

## Zasady bezpieczeństwa

- Sekrety trzymamy wyłącznie w `.env` lub menedżerze sekretów CI.
- Nie logujemy tokenu Mapbox ani pełnego `DATABASE_URL`.
- Dane użytkownika walidujemy przez Pydantic.
- Zapytania budujemy przez SQLAlchemy i parametry, nie przez konkatenację.
- Routery nie dostają bezpośredniego dostępu do silnika bazy.
- Każda zmiana kontraktu lub danych wymaga testu i aktualizacji dokumentacji.
