package com.example.saferoute;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;

import com.mapbox.geojson.Point;
import com.mapbox.maps.CameraOptions;
import com.mapbox.maps.MapView;
import com.mapbox.maps.Style;
import com.mapbox.maps.plugin.animation.CameraAnimationsUtils;
import com.mapbox.maps.plugin.animation.MapAnimationOptions;
import com.mapbox.bindgen.Expected;
import com.mapbox.bindgen.Value;

import java.util.Random;

public class UdostepnianieFragment extends Fragment {

    // Stan aplikacji
    private boolean isBroadcasting = false;
    private boolean isTracking = false;
    private String currentSessionCode = "";
    private boolean isFirstReceive = true;

    // Pętle w tle
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable broadcastRunnable;
    private Runnable trackingRunnable;

    // Mapa dla śledzącego
    private MapView mapViewReceiver;

    // --- SYMULATOR BAZY DANYCH (Ochrona przed awarią na hackathonie) ---
    private static String dbMockCode = "";
    private static double dbMockLat = 0.0;
    private static double dbMockLng = 0.0;
    private static long dbMockLastUpdate = 0;
    // -------------------------------------------------------------------

    public UdostepnianieFragment() { }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_udostepnianie, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        // --- WIDOKI NADAJNIKA ---
        TextView tvBroadcastStatus = view.findViewById(R.id.tv_broadcast_status);
        TextView tvShareCode = view.findViewById(R.id.tv_share_code);
        Button btnStartBroadcast = view.findViewById(R.id.btn_start_broadcast);
        Button btnStopBroadcast = view.findViewById(R.id.btn_stop_broadcast);

        // --- WIDOKI ODBIORNIKA ---
        EditText etReceiveCode = view.findViewById(R.id.et_receive_code);
        Button btnStartTracking = view.findViewById(R.id.btn_start_tracking);
        Button btnStopTracking = view.findViewById(R.id.btn_stop_tracking);
        LinearLayout panelLiveData = view.findViewById(R.id.panel_live_data);
        TextView tvLiveStatus = view.findViewById(R.id.tv_live_status);
        
        mapViewReceiver = view.findViewById(R.id.mapView_receiver);
        mapViewReceiver.getMapboxMap().loadStyleUri(Style.MAPBOX_STREETS);

        // Naprawa gestów - zabraniamy głównemu ekranowi przechwytywać dotyk, gdy operujemy na mapie
        mapViewReceiver.setOnTouchListener((v, event) -> {
            v.getParent().requestDisallowInterceptTouchEvent(true);
            return false;
        });

        // ==========================================
        // 1. LOGIKA NADAJNIKA (Udostępnianie trasy)
        // ==========================================

        broadcastRunnable = new Runnable() {
            @Override
            public void run() {
                if (isBroadcasting) {
                    sendLocationToDatabase(currentSessionCode);
                    handler.postDelayed(this, 5000); // Wykonuj co 5 sekund
                }
            }
        };

        btnStartBroadcast.setOnClickListener(v -> {
            currentSessionCode = String.format("%04d", new Random().nextInt(10000));

            isBroadcasting = true;
            tvShareCode.setText("TWÓJ KOD: " + currentSessionCode);
            tvShareCode.setVisibility(View.VISIBLE);
            tvBroadcastStatus.setText("🟢 Nadawanie na żywo włączone");
            tvBroadcastStatus.setTextColor(0xFF4CAF50);

            btnStartBroadcast.setVisibility(View.GONE);
            btnStopBroadcast.setVisibility(View.VISIBLE);

            // Odpalenie pętli nadającej w tle
            handler.post(broadcastRunnable);

            String shareMessage = "Cześć! Śledź moją trasę na żywo w aplikacji SafeRoute. Mój kod sesji to: " + currentSessionCode;
            Intent sendIntent = new Intent(Intent.ACTION_SEND);
            sendIntent.putExtra(Intent.EXTRA_TEXT, shareMessage);
            sendIntent.setType("text/plain");
            startActivity(Intent.createChooser(sendIntent, "Wyślij kod sesji do..."));
        });

        btnStopBroadcast.setOnClickListener(v -> {
            isBroadcasting = false;
            handler.removeCallbacks(broadcastRunnable);

            tvShareCode.setVisibility(View.GONE);
            tvBroadcastStatus.setText("🔴 Nie nadajesz sygnału");
            tvBroadcastStatus.setTextColor(0xFFF44336);

            btnStopBroadcast.setVisibility(View.GONE);
            btnStartBroadcast.setVisibility(View.VISIBLE);
            Toast.makeText(getContext(), "Zakończono nadawanie lokalizacji.", Toast.LENGTH_SHORT).show();
            
            // TODO: SUPABASE - Tutaj możesz opcjonalnie wywołać DELETE FROM live_sessions WHERE code = currentSessionCode
        });


        // ==========================================
        // 2. LOGIKA ODBIORNIKA (Śledzenie bliskiego)
        // ==========================================

        trackingRunnable = new Runnable() {
            @Override
            public void run() {
                if (isTracking) {
                    fetchLocationFromDatabase(etReceiveCode.getText().toString(), tvLiveStatus);
                    handler.postDelayed(this, 5000); // Odbieraj co 5 sekund
                }
            }
        };

        btnStartTracking.setOnClickListener(v -> {
            String code = etReceiveCode.getText().toString().trim();
            if (code.length() != 4) {
                Toast.makeText(getContext(), "Wpisz poprawny 4-cyfrowy kod!", Toast.LENGTH_SHORT).show();
                return;
            }

            isTracking = true;
            isFirstReceive = true; // Przy każdym nowym połączeniu chcemy zacząć od zooma 16.0
            etReceiveCode.setEnabled(false);
            btnStartTracking.setVisibility(View.GONE);
            btnStopTracking.setVisibility(View.VISIBLE);
            panelLiveData.setVisibility(View.VISIBLE);
            tvLiveStatus.setText("Status: Oczekiwanie na sygnał...");
            tvLiveStatus.setTextColor(0xFF2196F3);

            // Odpalenie pętli odbierającej w tle
            handler.post(trackingRunnable);
            Toast.makeText(getContext(), "Połączono! Nasłuchiwanie bazy danych...", Toast.LENGTH_SHORT).show();
        });

        btnStopTracking.setOnClickListener(v -> {
            isTracking = false;
            handler.removeCallbacks(trackingRunnable);

            etReceiveCode.setEnabled(true);
            etReceiveCode.setText("");
            panelLiveData.setVisibility(View.GONE);
            btnStopTracking.setVisibility(View.GONE);
            btnStartTracking.setVisibility(View.VISIBLE);
            Toast.makeText(getContext(), "Śledzenie zakończone.", Toast.LENGTH_SHORT).show();
        });
    }

    // ==========================================
    // METODY BAZODANOWE
    // ==========================================

    private void sendLocationToDatabase(String sessionCode) {
        double currentLat = 50.06143;
        double currentLng = 19.93658;

        if (ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            LocationManager locationManager = (LocationManager) requireContext().getSystemService(Context.LOCATION_SERVICE);
            if (locationManager != null) {
                Location loc = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                if (loc == null) loc = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                if (loc != null) {
                    currentLat = loc.getLatitude();
                    currentLng = loc.getLongitude();
                }
            }
        }

        // --- SYMULATOR BAZY ---
        dbMockCode = sessionCode;
        dbMockLat = currentLat;
        dbMockLng = currentLng;
        dbMockLastUpdate = System.currentTimeMillis();

        // TODO: SUPABASE - Tutaj wstawiasz faktyczny kod wysyłający:
        // INSERT INTO live_sessions (code, lat, lng, last_update) VALUES (sessionCode, currentLat, currentLng, NOW())
        // ON CONFLICT (code) DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng, last_update = NOW();

        Log.d("SafeRoute_Live", "NADAJĘ do bazy -> Kod: " + sessionCode + " | Poz: " + currentLat + ", " + currentLng);
    }

    private void fetchLocationFromDatabase(String sessionCode, TextView tvStatus) {
        // --- SYMULATOR BAZY ---
        // Zamiast uderzać do Supabase, sprawdzamy naszą statyczną zmienną
        String dbCode = dbMockCode;
        double lat = dbMockLat;
        double lng = dbMockLng;
        long lastUpdateMs = dbMockLastUpdate; // Czas w milisekundach (epoch)

        // TODO: SUPABASE - Tutaj wstawiasz pobieranie danych:
        // SELECT lat, lng, EXTRACT(EPOCH FROM last_update) * 1000 AS last_update_ms FROM live_sessions WHERE code = sessionCode;
        // Pobrane dane przypisz do zmiennych wyżej.

        if (!sessionCode.equals(dbCode) || lastUpdateMs == 0) {
            tvStatus.setText("Status: Nie znaleziono aktywnej sesji.");
            tvStatus.setTextColor(0xFFF44336);
            return;
        }

        long currentTime = System.currentTimeMillis();
        long timeDifference = currentTime - lastUpdateMs;

        // SPRAWDZAMY CZY MINĘŁO PONAD 20 SEKUND OD OSTATNIEJ AKTUALIZACJI
        if (timeDifference > 20000) {
            tvStatus.setText("Status: Sygnał utracony (Zakończono udostępnianie)");
            tvStatus.setTextColor(0xFFF44336); // Czerwony
            // Tu można dodać wyszarzanie mapy
        } else {
            tvStatus.setText("Status: Odbieranie na żywo 🟢");
            tvStatus.setTextColor(0xFF4CAF50); // Zielony

            if (mapViewReceiver != null) {
                Point newLocation = Point.fromLngLat(lng, lat);

                // Budujemy opcje kamery (zawsze aktualizujemy sam środek)
                CameraOptions.Builder cameraBuilder = new CameraOptions.Builder().center(newLocation);
                
                // Wymuszamy przybliżenie 16.0 TYLKO przy pierwszej odebranej lokalizacji
                if (isFirstReceive) {
                    cameraBuilder.zoom(16.0);
                    isFirstReceive = false;
                }

                // Płynne "sunięcie" kamery (nie nadpisuje zooma, jeśli użytkownik sam go zmienił)
                CameraAnimationsUtils.getCamera(mapViewReceiver).easeTo(
                        cameraBuilder.build(),
                        new MapAnimationOptions.Builder().duration(2000).build(),
                        null 
                );

                // Rysowanie i aktualizacja niebieskiej kropki znajomego na mapie
                updateTrackedUserMarker(lat, lng);
            }
        }
        
        Log.d("SafeRoute_Live", "ODBIERAM z bazy -> Diff: " + (timeDifference/1000) + "s");
    }

    // ==========================================
    // RYSOWANIE KROPKI ŚLEDZONEJ OSOBY
    // ==========================================
    private void updateTrackedUserMarker(double lat, double lng) {
        if (mapViewReceiver == null) return;

        mapViewReceiver.getMapboxMap().getStyle(style -> {
            // Usuwamy starą pozycję, by narysować znacznik w nowym miejscu
            try {
                style.removeStyleLayer("tracked-user-layer");
                style.removeStyleSource("tracked-user-source");
            } catch (Exception ignored) { }

            // Generujemy koordynaty w locie
            String sourceJson = "{\"type\":\"geojson\",\"data\":{\"type\":\"Feature\",\"geometry\":{\"type\":\"Point\",\"coordinates\":[" + lng + "," + lat + "]}}}";

            Expected<String, Value> sourceExpected = Value.fromJson(sourceJson);
            if (!sourceExpected.isError()) {
                style.addStyleSource("tracked-user-source", sourceExpected.getValue());
            }

            // Stylizujemy kropkę na niebiesko, podobnie jak lokalizację w Google Maps
            String layerJson = "{"
                    + "\"id\":\"tracked-user-layer\","
                    + "\"type\":\"circle\","
                    + "\"source\":\"tracked-user-source\","
                    + "\"paint\":{"
                    + "\"circle-radius\":10,"
                    + "\"circle-color\":\"#2196F3\","
                    + "\"circle-stroke-color\":\"#FFFFFF\","
                    + "\"circle-stroke-width\":3"
                    + "}"
                    + "}";

            Expected<String, Value> layerExpected = Value.fromJson(layerJson);
            if (!layerExpected.isError()) {
                style.addStyleLayer(layerExpected.getValue(), null);
            }
        });
    }

    // ==========================================
    // CYKL ŻYCIA MAPY MAPBOX
    // ==========================================

    @Override
    public void onStart() {
        super.onStart();
        if (mapViewReceiver != null) mapViewReceiver.onStart();
    }

    @Override
    public void onStop() {
        super.onStop();
        if (mapViewReceiver != null) mapViewReceiver.onStop();
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (mapViewReceiver != null) mapViewReceiver.onDestroy();
        isBroadcasting = false;
        isTracking = false;
        handler.removeCallbacksAndMessages(null);
    }
    
    @Override
    public void onLowMemory() {
        super.onLowMemory();
        if (mapViewReceiver != null) mapViewReceiver.onLowMemory();
    }
}