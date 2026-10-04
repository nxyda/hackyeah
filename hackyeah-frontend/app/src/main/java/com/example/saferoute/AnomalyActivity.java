package com.example.saferoute;

import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class AnomalyActivity extends AppCompatActivity {

    private CountDownTimer countDownTimer;
    private TextView tvCountdown;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_anomaly);

        tvCountdown = findViewById(R.id.tv_countdown);
        Button btnSafe = findViewById(R.id.btn_im_safe);
        TextView tvTitle = findViewById(R.id.tv_anomaly_title);

        // Odbierz informację, co dokładnie się stało (Bieg czy Postój)
        String reason = getIntent().getStringExtra("REASON");
        if (reason != null) {
            tvTitle.setText(reason);
        }

        startVibrationAlert();

        // 30 sekund na reakcję
        countDownTimer = new CountDownTimer(30000, 1000) {
            @Override
            public void onTick(long millisUntilFinished) {
                tvCountdown.setText(String.valueOf(millisUntilFinished / 1000));
            }

            @Override
            public void onFinish() {
                tvCountdown.setText("0");
                triggerAutomaticSOS();
            }
        }.start();

        // Jeśli kliknie, że jest bezpieczna:
        btnSafe.setOnClickListener(v -> {
            countDownTimer.cancel();
            
            // --- DODANE: Natychmiastowe usuwanie powiadomienia z paska ---
            android.app.NotificationManager manager = (android.app.NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.cancel(999);
            }
            // -------------------------------------------------------------

            Toast.makeText(this, "Alarm odwołany. Kontynuuj bezpiecznie.", Toast.LENGTH_SHORT).show();
            finish(); // Zamyka ten czerwony ekran i wraca do mapy
        });
    }

    private void triggerAutomaticSOS() {
        Toast.makeText(this, "Brak odpowiedzi! WYSYŁAM SOS!", Toast.LENGTH_LONG).show();

        // Wywołujemy Waszego gotowego SosManagera z pustym callbackiem
        SosManager sosManager = new SosManager(this, () -> {});
        sosManager.triggerSosActions();

        finish(); // Zamykamy ekran po wysłaniu
    }

    private void startVibrationAlert() {
        Vibrator vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        if (vibrator != null && vibrator.hasVibrator()) {
            long[] pattern = {0, 500, 500, 500, 500}; // Agresywna, przerywana wibracja
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(2000, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(pattern, -1);
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (countDownTimer != null) {
            countDownTimer.cancel();
        }
    }
}