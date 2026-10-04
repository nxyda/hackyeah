# Safe Route — uruchomienie backendu i aplikacji

Projekt ma dwa osobne moduły: `backend-safe-route` (API FastAPI i PostgreSQL
z PostGIS) oraz `hackyeah-frontend` (aplikacja Android). Najpierw uruchom
backend, a potem aplikację. Android korzysta z `API_BASE_URL`, więc nie trzeba
zmieniać adresu API w kodzie.

## Wymagania

- Windows 10/11 i PowerShell.
- Python 3.12. Sprawdź zainstalowane wersje poleceniem `py -0p`.
- Docker Desktop uruchomiony z Docker Compose.
- Android Studio, Android SDK Platform 36 i JDK 17 skonfigurowane dla Gradle.
- Konto Mapbox i dwa tokeny:
  - **publiczny access token** (`pk...`) do mapy i wyszukiwania w aplikacji;
  - **sekretny downloads token** (`sk...`) z zakresem `DOWNLOADS:READ`
    do pobierania zależności SDK Mapbox przez Gradle;
  - **sekretny Directions token** dla backendu (zwykle można użyć downloads
    tokenu, jeśli ma także uprawnienie Directions API).

Sekrety nie trafiają do repozytorium. Nie umieszczaj tokenów `sk...` w aplikacji
ani nie udostępniaj ich. Token `pk...` będzie zawarty w aplikacji; ogranicz jego
dostępne uprawnienia w panelu Mapbox.

## 1. Uruchom backend

Otwórz **pierwszy** terminal PowerShell w głównym katalogu repozytorium, tam,
gdzie znajduje się ten README. Uruchom lokalną bazę PostGIS:

```powershell
docker compose up -d --wait database
docker compose ps
```

Przy pierwszym uruchomieniu Docker pobierze obraz bazy. Poczekaj, aż stan
kontenera będzie `healthy`.

Przygotuj backend i jego środowisko Python:

```powershell
Set-Location .\backend-safe-route
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Jeśli `py -3.12` nie działa, zainstaluj Python 3.12 i ponownie otwórz terminal.
Jeśli PowerShell blokuje aktywację venv, pomiń aktywację i używaj
poniższych poleceń do instalacji zależności z katalogu `backend-safe-route`:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Otwórz `backend-safe-route\.env` i sprawdź lokalne ustawienia bazy:

```dotenv
DB_USER=safe_route
DB_PASSWORD=safe_route_dev
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=safe_route
DB_SSL=false
```

Ustaw `MAPBOX_SECRET_TOKEN` na sekret, który ma dostęp do Directions API.
Zostaw `API_MODE=live`. Zapisz plik `.env`; nie commituj go. Pozostałe zmienne
możesz zostawić puste do lokalnego uruchomienia podstawowego API.

Wykonaj migracje bazy, a potem uruchom serwer. Jeśli aktywowałeś venv:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Jeśli nie aktywowałeś venv, użyj zamiast tego:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
```

Pozostaw ten terminal otwarty. Sprawdź w przeglądarce
<http://127.0.0.1:8000/health> — poprawna odpowiedź zawiera
`"status":"ok"`. Dokumentacja API jest pod <http://127.0.0.1:8000/docs>.
Lokalna baza jest pusta; warstwy kamer, latarni, bezpiecznych miejsc i zdarzeń
pozostaną puste, dopóki nie zaimportujesz danych. Planowanie trasy wymaga
poprawnego `MAPBOX_SECRET_TOKEN`.

## 2. Skonfiguruj i uruchom Androida

W Android Studio otwórz folder `hackyeah-frontend` jako projekt. Jeśli pojawi
się prośba o zainstalowanie Android SDK Platform 36, zaakceptuj ją. Dla tego
projektu wybierz **JDK 17** jako Gradle JDK:
`File > Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK`.
Wybierz zainstalowany JDK 17 albo pobierz go z selektora. JDK 25/26 może
powodować błąd wersji podczas konfiguracji Gradle.

Android Studio utworzy plik `hackyeah-frontend\local.properties` z lokalizacją
Android SDK (`sdk.dir`). **Nie zastępuj tego pliku przykładowym** — dopisz do
niego trzy wpisy z `hackyeah-frontend\local.properties.example`:

```properties
MAPBOX_ACCESS_TOKEN=pk.twoj_publiczny_token
MAPBOX_DOWNLOADS_TOKEN=sk.twoj_token_zakresu_DOWNLOADS_READ
API_BASE_URL=http://10.0.2.2:8000/
```

W `MAPBOX_DOWNLOADS_TOKEN` wpisz sekret Mapbox z zakresem pobierania SDK.
Gradle używa go do uwierzytelnienia repozytorium Maven; nie jest osadzany w
aplikacji. `MAPBOX_ACCESS_TOKEN` to publiczny token Mapbox wymagany w aplikacji.
Po zapisaniu pliku w Android Studio wybierz **Sync Project with Gradle Files**.

Uruchom emulator Androida z poziomu **Device Manager**. Gdy emulator działa,
kliknij **Run** (`app`). Możesz też z drugiego terminala, w katalogu głównym
repozytorium, zbudować i zainstalować aplikację na uruchomionym emulatorze:

```powershell
.\hackyeah-frontend\gradlew.bat -p .\hackyeah-frontend :app:installDebug
```

`10.0.2.2` to specjalny adres emulatora Androida prowadzący do `localhost`
komputera. Zostaw backend uruchomiony w pierwszym terminalu. W aplikacji
żądania API powinny teraz trafiać do tego lokalnego serwera.

## Połączenie z fizycznym telefonem

Telefon i komputer muszą być w tej samej sieci Wi-Fi. Odczytaj IPv4 komputera
poleceniem `ipconfig` i dopisz do `local.properties`, używając adresu z
aktywnej karty Wi-Fi, np.:

```properties
API_BASE_URL=http://192.168.1.20:8000/
```

Adres musi wskazywać na komputer, na którym działa backend, i kończyć się `/`.
Backend uruchamiamy z `--host 0.0.0.0`, żeby był osiągalny z sieci lokalnej.
Jeśli telefon nie może połączyć się z API, zezwól aplikacji Python na
połączenia przychodzące w Zaporze Windows dla sieci prywatnej oraz upewnij się,
że port `8000` nie jest blokowany. Po każdej zmianie `API_BASE_URL` wykonaj
ponownie Gradle Sync i przebuduj aplikację.

## Zatrzymywanie

Zatrzymaj backend przez `Ctrl+C` w jego terminalu. Bazę zatrzymaj z katalogu
głównego projektu:

```powershell
docker compose down
```

Dane bazy pozostają zachowane w wolumenie Dockera. Nie dodawaj `-v`, jeśli
chcesz je zachować.
