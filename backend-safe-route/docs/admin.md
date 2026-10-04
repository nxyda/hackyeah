# Panel administratora

Panel działa w tej samej aplikacji FastAPI pod adresem `/admin`. Do jego
uruchomienia potrzebujesz aktualnej bazy PostgreSQL/PostGIS, migracji, konta
administratora i osobnego sekretu do podpisywania sesji przeglądarki.

## Pierwsze uruchomienie

W katalogu projektu aktywuj środowisko i zainstaluj zależności:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Skonfiguruj w `.env` połączenie do bazy oraz dwa oddzielne sekrety:

- `JWT_SECRET_KEY` — do tokenów dostępu API;
- `ADMIN_SESSION_SECRET` — do sesji przeglądarki panelu.

Każdy z tych sekretów musi zawierać co najmniej **32 bajty**. Najprościej
wygenerować dwa różne, losowe klucze poleceniem:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Wynik ma 64 znaki ASCII (48 losowych bajtów). Wygeneruj klucz osobno dla obu
zmiennych, wklej je do `.env` i nie umieszczaj ich w repozytorium ani aplikacji
mobilnej. Nie udostępniaj ich użytkownikom.

Do lokalnego uruchomienia po HTTP ustaw:

```dotenv
ADMIN_COOKIE_SECURE=false
```

W środowisku produkcyjnym używaj HTTPS i `ADMIN_COOKIE_SECURE=true`. Panel jest
domyślnie wyłączony, jeśli `ADMIN_SESSION_SECRET` jest puste. Sekret krótszy
niż 32 bajty albo taki sam jak `JWT_SECRET_KEY` uniemożliwi uruchomienie
skonfigurowanego panelu. Po zmianie `.env` uruchom aplikację ponownie.

Następnie zastosuj wszystkie migracje:

```powershell
alembic upgrade head
```

Utwórz pierwszego administratora:

```powershell
python -m app.cli create-admin --email admin@example.com
```

Polecenie poprosi dwukrotnie o hasło (minimum 12 znaków); hasło nie jest
wpisywane jako argument ani zapisywane w historii poleceń. Jeżeli adres jeszcze
nie istnieje, polecenie utworzy konto. Jeżeli konto już istnieje, nada mu rolę
administratora, aktywuje je i ustawi podane hasło lokalne — używaj tego
ostrożnie, szczególnie dla kont logujących się wcześniej wyłącznie przez OAuth.

Uruchom aplikację:

```powershell
uvicorn app.main:app --reload
```

Otwórz <http://127.0.0.1:8000/admin>, zaloguj się adresem e-mail administratora
i ustawionym hasłem. Formularz logowania SQLAdmin nazywa pole e-mail polem
użytkownika — wpisz w nim pełny adres e-mail.

## Lokalizacje na mapie

W widoku dodawania, edycji i szczegółów rekordu z geometrią znajduje się mapa
OpenStreetMap. W formularzu kliknij mapę, aby ustawić punkt; marker można
przeciągnąć. Wartość jest synchronizowana z polem WKT, więc formularz zapisuje
ją standardowym mechanizmem SQLAdmin. Dla segmentów dróg klikaj kolejne punkty,
aby narysować linię; istniejące wierzchołki linii można przeciągać.
Nowe formularze punktowe domyślnie wskazują centrum Krakowa (50.0647, 19.9450),
a pole WKT otrzymuje odpowiadający mu punkt; mapy linii również zaczynają
widok od Krakowa. W szczegółach rekordu mapa jest tylko do podglądu.

Mapa formularza jest dostępna dla zgłoszeń, kamer, latarni, zdarzeń kryminalnych,
bezpiecznych miejsc i segmentów dróg. Korzysta z zewnętrznych kafelków
OpenStreetMap, dlatego przeglądarka musi mieć dostęp do internetu. Edycja
lokalizacji nie wymaga dodatkowego endpointu: zapisuje geometrię razem z
pozostałymi polami formularza.

## Co można zarządzać

Panel SQLAdmin udostępnia przeglądanie, dodawanie, edycję i usuwanie:

| Encja | Uwagi |
| --- | --- |
| Users | Hash hasła nie jest wyświetlany. Formularz ma pole `New password`: przy tworzeniu jest wymagane, przy edycji ustaw je tylko, gdy chcesz zmienić hasło. |
| OAuth identities | Powiązania kont z dostawcami Google i Facebook. |
| Reports | Zgłoszenia, ich status, liczba potwierdzeń i właściciel. |
| Report confirmations | Powiązanie zgłoszenia z użytkownikiem. |
| Cameras | Lokalizacja kamery. |
| Crime events | Zdarzenia kryminalne i ich lokalizacja; `severity` jest opcjonalnym polem liczbowym obsługującym wartości dziesiętne. |
| Road segments | Segmenty dróg i ich atrybuty; długość jest polem liczbowym, a odległość do bezpiecznego miejsca jest liczona na bieżąco, nie edytowana w panelu. |
| Safe places | Bezpieczne miejsca i ich lokalizacja. |
| Street lamps | Latarnie uliczne i ich lokalizacja. |
| Location shares | Historia tymczasowych udostępnień lokalizacji; widok tylko do odczytu, bez eksportu kodów. |

Geometrie PostGIS są wpisywane jako WKT, ze współrzędnymi w kolejności
**długość, szerokość**:

```text
POINT(21.01 52.23)
LINESTRING(21.01 52.23, 21.02 52.24)
```

Widok **Location sharing** pokazuje aktywne udostępnienia, adres właściciela,
kod dostępu, ostatnią lokalizację i czas wygaśnięcia. Administrator może
natychmiast unieważnić udostępnienie; kod przestaje działać i może zostać
ponownie przydzielony. Formularz unieważnienia jest chroniony tokenem CSRF.
Zarządzanie kodami i lokalizacjami odbywa się wyłącznie w tym widoku — tworzenie,
edycja, usuwanie i eksport rekordów udostępnień są wyłączone, by nie omijać
reguł czasowych ani mechanizmu alokacji kodów. Historia pozostaje dostępna
w widoku **Location shares**.

Widok **Route planner** pozwala przetestować planowanie trasy pieszej bez
wywoływania klienta aplikacji: podaj początek, cel, czas wyjścia w formacie
ISO 8601 wraz z offsetem strefy czasowej (np. `2026-10-04T18:30+02:00`) oraz
wagę bezpieczeństwa od `0` do `1`. Panel korzysta z tego samego serwisu,
dostawcy tras, danych i scoringu co `POST /v1/route`; wyniki pokazuje jako
najszybszą, najbezpieczniejszą i alternatywne trasy na mapie. Podgląd nie
zapisuje trasy w bazie. Wymaga konfiguracji tokenu Mapbox, a formularz
obliczenia jest chroniony tokenem CSRF.

Nie usuwaj ręcznie rekordów z `Report confirmations` ani nie zmieniaj
bezpośrednio licznika potwierdzeń raportu: zwykły CRUD panelu nie aktualizuje
automatycznie drugiej tabeli i mógłby rozjechać licznik z potwierdzeniami.
Potwierdzanie wykonuj przez endpoint API
`POST /v1/reports/{report_id}/confirm`.

Ostatniego aktywnego administratora nie można zdegradować, dezaktywować ani
usunąć. Panel nie pozwala administratorowi usunąć własnego konta. Administrator
może zmieniać role pozostałych kont przez widok Users lub przez chronione API.

## API administracyjne

Panel przeglądarkowy używa sesji, natomiast endpointy administracyjne API
wymagają JWT administratora w nagłówku `Authorization: Bearer <token>`.
Token pobierzesz przez `POST /v1/auth/login`, używając e-maila i hasła konta
administratora.

| Metoda i ścieżka | Działanie |
| --- | --- |
| `GET /v1/admin/users` | Lista użytkowników bez hashy haseł. |
| `PATCH /v1/admin/users/{user_id}` | Zmienia `role`, `is_active`, `given_name` lub `family_name`. |
| `DELETE /v1/admin/users/{user_id}` | Usuwa konto oraz powiązane kaskadowo dane. |

Przykładowa zmiana zwykłego konta na administratora:

```json
{
  "role": "admin"
}
```

Hasło można ustawić w formularzu Users albo endpointem administratora:

```http
PUT /v1/admin/users/42/password
Authorization: Bearer <token-administratora>
Content-Type: application/json
```

```json
{
  "password": "nowe-bezpieczne-haslo"
}
```

Hasło musi mieć minimum 12 znaków. Serwer zapisuje wyłącznie hash Argon2;
wartość hasła nie pojawia się na liście użytkowników ani w odpowiedzi API.
Puste pole w edycji użytkownika pozostawia dotychczasowe hasło bez zmian.

Każde konto rejestrowane przez publiczny endpoint otrzymuje rolę `user`.
Odpowiedzi `401` oznaczają brak lub nieprawidłowy JWT, `403` — brak roli
administratora, a `409` — operację zablokowaną ze względów bezpieczeństwa,
np. próbę usunięcia ostatniego aktywnego administratora.

## Bezpieczeństwo

Panel daje bezpośredni dostęp do edycji danych, więc:

- nie wystawiaj go bezpośrednio do publicznej sieci; ogranicz `/admin` na
  reverse proxy lub przez VPN;
- używaj unikalnego `ADMIN_SESSION_SECRET` i HTTPS w produkcji;
- ogranicz częstotliwość prób logowania na reverse proxy;
- nadawaj rolę admin tylko zaufanym osobom i regularnie przeglądaj aktywne
  konta administratorów;
- nie edytuj ręcznie hashy haseł ani sekretów przez panel.
