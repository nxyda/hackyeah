package com.example.saferoute;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.os.Build;
import android.util.Log;

import androidx.core.app.NotificationCompat;

public class AnomalyDetector implements SensorEventListener {

    private final Context context;

    // Flaga określająca, czy użytkownik jest aktualnie prowadzony po trasie
    private boolean isNavigationActive = false;
    
    // Zmienne do detekcji postoju (GPS)
    private Location anchorLocation = null;
    private long anchorTime = 0;
    
    private boolean isAnomalyActive = false;

    // Ustawienia Postoju (Hackathonowe 15 sekund)
    private static final long MAX_STOP_TIME_MS = 15000; 
    private static final float GPS_WANDER_TOLERANCE_METERS = 40.0f;

    // Czujniki (Detekcja biegu)
    private SensorManager sensorManager;
    private Sensor accelerometer;
    private int shakeCount = 0;
    private long lastShakeTime = 0;
    private static final double SHAKE_THRESHOLD = 20; // Siła wstrząsu (zmień w dół, jeśli za ciężko wywołać)

    public AnomalyDetector(Context context) {
        this.context = context;
        createNotificationChannel();
        initSensors();
    }

    private void initSensors() {
        sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        if (sensorManager != null) {
            // Używamy LINEAR_ACCELERATION, bo ignoruje stałe przyciąganie ziemskie
            accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION);
            if (accelerometer != null) {
                sensorManager.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_UI);
            }
        }
    }

    // ==========================================
    // 1. WYKRYWANIE POSTOJU (Na podstawie GPS)
    // ==========================================
    public void processNewLocation(Location location) {
        if (isAnomalyActive) return;
        if (!isNavigationActive) return; // Zignoruj GPS, jeśli nawigacja jest wyłączona

        // Jeśli dokładność GPS jest dramatyczna (np. > 60m błędu w budynku), ignorujemy odczyt
        if (location.getAccuracy() > 60.0f) return;

        long currentTime = System.currentTimeMillis();

        if (anchorLocation == null) {
            anchorLocation = location;
            anchorTime = currentTime;
        } else {
            // Jeśli użytkownik odszedł na więcej niż 40 metrów, resetujemy stoper
            if (location.distanceTo(anchorLocation) > GPS_WANDER_TOLERANCE_METERS) {
                anchorLocation = location;
                anchorTime = currentTime;
            } else {
                // Użytkownik znajduje się w jednym miejscu
                long timeStopped = currentTime - anchorTime;
                if (timeStopped > MAX_STOP_TIME_MS) {
                    triggerAnomaly("WYKRYTO DŁUGI POSTÓJ!");
                }
            }
        }
    }

    // ==========================================
    // 2. WYKRYWANIE BIEGU (Na podstawie Czujnika)
    // ==========================================
    @Override
    public void onSensorChanged(SensorEvent event) {
        if (isAnomalyActive) return;
        if (!isNavigationActive) return; // Zignoruj czujniki ruchu, jeśli nawigacja jest wyłączona

        if (event.sensor.getType() == Sensor.TYPE_LINEAR_ACCELERATION) {
            float x = event.values[0];
            float y = event.values[1];
            float z = event.values[2];

            // Obliczanie całkowitej siły ruchu (wypadkowa z 3 osi)
            double magnitude = Math.sqrt(x * x + y * y + z * z);

            if (magnitude > SHAKE_THRESHOLD) {
                long currentTime = System.currentTimeMillis();
                
                // Zliczamy wstrząsy, żeby pojedyncze stuknięcie nie wywołało alarmu
                if (currentTime - lastShakeTime < 1000) {
                    shakeCount++;
                } else {
                    shakeCount = 1; // Reset, jeśli minęło za dużo czasu między wstrząsami
                }
                lastShakeTime = currentTime;

                // Jeśli w krótkim czasie było kilka silnych wstrząsów (imitacja biegu)
                if (shakeCount >= 7) { 
                    shakeCount = 0;
                    triggerAnomaly("WYKRYTO NAGŁY BIEG!");
                }
            }
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // Niepotrzebne
    }

    // ==========================================
    // WSPÓLNA AKCJA ALARMOWA
    // ==========================================
    private void triggerAnomaly(String reason) {
        isAnomalyActive = true;
        anchorLocation = null; // Reset kotwicy GPS

        Intent intent = new Intent(context, AnomalyActivity.class);
        intent.putExtra("REASON", reason);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        PendingIntent pendingIntent = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, "SAFEROUTE_CHANNEL")
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle("Bezpieczeństwo na trasie")
                .setContentText(reason + " Kliknij, aby potwierdzić bezpieczeństwo!")
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setFullScreenIntent(pendingIntent, true)
                .setAutoCancel(true);

        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(999, builder.build()); 
        }

        context.startActivity(intent);

        // Odblokuj ponowne sprawdzanie anomalii po 15 sekundach
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> isAnomalyActive = false, 15000);
    }

    public void setNavigationActive(boolean active) {
        this.isNavigationActive = active;
        // Gdy nawigacja zostaje wyłączona, upewnijmy się, że stoper postoju się zresetuje
        if (!active) {
            anchorLocation = null;
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel("SAFEROUTE_CHANNEL", "Alarmy SafeRoute", NotificationManager.IMPORTANCE_HIGH);
            channel.enableVibration(true);
            channel.setVibrationPattern(new long[]{0, 500, 200, 500});
            
            NotificationManager manager = context.getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
}