package com.example.saferoute;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.telephony.SmsManager;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Toast;

import androidx.core.content.ContextCompat;

public class SosManager {

    private final Context context;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable sosRunnable;
    private boolean isSosTriggered = false;

    public interface SosCallback {
        void onRouteToSafeHavenRequested();
    }
    private SosCallback callback;

    public SosManager(Context context, SosCallback callback) {
        this.context = context;
        this.callback = callback;
    }

    public void attachToButton(View sosButton) {
        sosButton.setOnTouchListener((v, event) -> {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    isSosTriggered = false;
                    vibrate(100);

                    sosRunnable = () -> {
                        isSosTriggered = true;
                        triggerSosActions();
                    };
                    handler.postDelayed(sosRunnable, 3000);
                    return true;

                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (!isSosTriggered && sosRunnable != null) {
                        handler.removeCallbacks(sosRunnable);
                        Toast.makeText(context, "Anulowano SOS", Toast.LENGTH_SHORT).show();
                    }
                    return true;
            }
            return false;
        });
    }

    public void triggerSosActions() {
        vibrate(1000);
        Toast.makeText(context, "SOS AKTYWOWANE!", Toast.LENGTH_LONG).show();

        startBlackBoxRecording();

        notifyEmergencyContacts();

        if (callback != null) {
            callback.onRouteToSafeHavenRequested();
        }

        makeEmergencyCall("514157266");
    }

    private void makeEmergencyCall(String phoneNumber) {
        // Zmiana na ACTION_CALL - wymusza natychmiastowe połączenie bez otwierania dialera
        Intent intent = new Intent(Intent.ACTION_CALL);
        intent.setData(Uri.parse("tel:" + phoneNumber));
        try {
            context.startActivity(intent);
        } catch (SecurityException e) {
            // Aplikacja zcrashuje, jeśli nie dodasz uprawnień CALL_PHONE w Manifeście
            Toast.makeText(context, "Brak uprawnień do dzwonienia!", Toast.LENGTH_SHORT).show();
        }
    }

    private void startBlackBoxRecording() {
        Toast.makeText(context, "Czarna Skrzynka: Nagrywanie i stream do chmury", Toast.LENGTH_SHORT).show();
    }

    private void notifyEmergencyContacts() {
        android.content.SharedPreferences prefs = context.getSharedPreferences("SafeRoutePrefs", Context.MODE_PRIVATE);
        
        // 1. Pobranie dynamicznej lokalizacji
        String locationLink = "https://maps.google.com/?q=50.06143,19.93658"; // Domyślna (fallback)
        
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            LocationManager locationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
            if (locationManager != null) {
                // Próbujemy pobrać z GPS
                Location location = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                // Jeśli GPS jeszcze nie złapał, próbujemy z sieci komórkowej/WiFi
                if (location == null) {
                    location = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                }
                
                // Jeśli udało się pobrać, podmieniamy link
                if (location != null) {
                    locationLink = "https://maps.google.com/?q=" + location.getLatitude() + "," + location.getLongitude();
                }
            }
        }

        // 2. Budowanie wiadomości
        String baseMsg = prefs.getString("sos_msg", "POMOCY! Uzyto SOS.");
        String finalMessage = baseMsg + " " + locationLink;

        // 3. Wysyłanie SMS do wszystkich zapisanych numerów
        try {
            android.telephony.SmsManager smsManager = android.telephony.SmsManager.getDefault();
            
            int sentCount = 0;
            for (int i = 1; i <= 5; i++) {
                String number = prefs.getString("sos_num_" + i, "");
                if (!number.isEmpty()) {
                    smsManager.sendTextMessage(number, null, finalMessage, null, null);
                    sentCount++;
                }
            }
            
            if (sentCount > 0) {
                Toast.makeText(context, "Wysłano SMS ratunkowy z lokalizacją do " + sentCount + " kontaktów!", Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) {
            Toast.makeText(context, "Błąd wysyłania SMS.", Toast.LENGTH_LONG).show();
            e.printStackTrace();
        }
    }

    // Naprawiony błąd z wibracjami (kompatybilność ze starszymi Androidami)
    private void vibrate(long milliseconds) {
        Vibrator vibrator = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
        if (vibrator != null && vibrator.hasVibrator()) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(milliseconds, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(milliseconds); // Dla starszych wersji Androida
            }
        }
    }
}