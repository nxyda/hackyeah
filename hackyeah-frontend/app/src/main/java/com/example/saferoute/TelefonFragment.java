package com.example.saferoute;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.google.android.material.floatingactionbutton.FloatingActionButton;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class TelefonFragment extends Fragment implements TextToSpeech.OnInitListener {

    private TextView tvCallTimer;
    private FloatingActionButton btnHangUp;
    private static final int REQUEST_CODE_SPEECH = 1001;

    private TextToSpeech textToSpeech;
    private Handler timerHandler = new Handler(Looper.getMainLooper());
    private Handler speechHandler = new Handler(Looper.getMainLooper());
    private int secondsPassed = 0;
    private boolean isCallActive = false;

    private Runnable timerRunnable = new Runnable() {
        @Override
        public void run() {
            if (isCallActive) {
                secondsPassed++;
                int minutes = secondsPassed / 60;
                int seconds = secondsPassed % 60;
                if (tvCallTimer != null) {
                    tvCallTimer.setText(String.format(Locale.getDefault(), "%02d:%02d", minutes, seconds));
                }
                timerHandler.postDelayed(this, 1000);
            }
        }
    };

    public TelefonFragment() {
    }

    @Override
    public View onCreateView(
            @NonNull LayoutInflater inflater,
            @Nullable ViewGroup container,
            @Nullable Bundle savedInstanceState
    ) {
        View bottomNav = requireActivity().findViewById(R.id.bottom_navigation);
        if (bottomNav != null) {
            bottomNav.setVisibility(View.GONE);
        }

        View view = inflater.inflate(
                R.layout.fragment_telefon,
                container,
                false
        );

        tvCallTimer = view.findViewById(R.id.tvCallTimer);
        btnHangUp = view.findViewById(R.id.btnHangUp);

        textToSpeech = new TextToSpeech(requireContext(), this);

        isCallActive = true;
        timerHandler.postDelayed(timerRunnable, 1000);

        pobierzTekstZGemini();

        if (btnHangUp != null) {
            btnHangUp.setOnClickListener(v -> {
                timerHandler.removeCallbacks(timerRunnable);
                isCallActive = false;

                if (tvCallTimer != null) {
                    tvCallTimer.setText("Połączenie zakończone");
                }

                btnHangUp.setEnabled(false);

                v.postDelayed(() -> {
                    if (bottomNav != null) {
                        bottomNav.setVisibility(View.VISIBLE);

                        if (bottomNav instanceof com.google.android.material.bottomnavigation.BottomNavigationView) {
                            ((com.google.android.material.bottomnavigation.BottomNavigationView) bottomNav)
                                    .setSelectedItemId(R.id.nav_map);
                        }
                    }

                    if (isAdded() && requireActivity() != null) {
                        requireActivity().getSupportFragmentManager()
                                .beginTransaction()
                                .replace(R.id.fragment_container, new MapaFragment())
                                .commit();
                    }
                }, 1500);
            });

        }

        return view;
    }

    @Override
    public void onInit(int status) {
        if (status == TextToSpeech.SUCCESS) {
            Locale polishLocale = new Locale("pl", "PL");
            int result = textToSpeech.setLanguage(polishLocale);

            if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {

                try {
                    if (textToSpeech.getVoices() != null) {
                        for (android.speech.tts.Voice voice : textToSpeech.getVoices()) {
                            if (voice.getLocale() != null && voice.getLocale().getLanguage().equals("pl")) {
                                String voiceName = voice.getName().toLowerCase();
                                if (voiceName.contains("male") || voiceName.contains("pl-pl-x-oda") || voiceName.contains("smb") || voiceName.contains("nf")) {
                                    textToSpeech.setVoice(voice);
                                    break;
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    Log.e("TTS", "Błąd przy ustawianiu głosu: " + e.getMessage());
                }

                textToSpeech.setPitch(0.7f);
                textToSpeech.setSpeechRate(0.95f);
            }
        }
    }

    private void uruchomNasluchMowy() {
        try {
            android.content.Intent intent = new android.content.Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, "pl-PL");
            intent.putExtra(android.speech.RecognizerIntent.EXTRA_PROMPT, "Powiedz coś do mamy...");

            startActivityForResult(intent, REQUEST_CODE_SPEECH);
        } catch (Exception e) {
            Log.e("Speech", "Błąd mikrofonu: " + e.getMessage());
            pobierzTekstZGeminiZKontekstem("Użytkownik nic nie powiedział, kontynuuj rozmowę troskliwie. Ponaglij maksymalnie jednym zdaniem.");
        }
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, @Nullable android.content.Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_CODE_SPEECH && resultCode == android.app.Activity.RESULT_OK && data != null) {
            java.util.ArrayList<String> results = data.getStringArrayListExtra(android.speech.RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                String coPowiedzialUzytkownik = results.get(0);

                pobierzTekstZGeminiZKontekstem("Użytkownik powiedział właśnie do telefonu: \"" + coPowiedzialUzytkownik + "\". Zareaguj na to troskliwie jako mama rozmawiająca z córką idącą nocą. Odpowiedz maksymalnie dwoma zdaniami");
            }
        } else {
            pobierzTekstZGeminiZKontekstem("Użytkownik nic nie powiedział, ponaglij go delikatnie. Maksymalnie jednym zdaniem.");
        }
    }

    private void pobierzTekstZGemini() {
        pobierzTekstZGeminiZKontekstem("Wygeneruj krótką (max. 2 zdania) ale realistyczną kwestię po polsku, którą mówi ktoś bliski (np. mama), kto rozmawia przez telefon z kimś idącym sama nocą po ulicy. Ma to brzmieć naturalnie, spokojnie ale z troską. Podaj sam tekst kwestii, bez cudzysłowów i dodatkowych wyjaśnień.");
    }

    private void pobierzTekstZGeminiZKontekstem(String promptDoWyslania) {
        new Thread(() -> {
            try {
                String apiKey = BuildConfig.GEMINI_API_KEY;
                String urlString = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=" + apiKey;

                URL url = new URL(urlString);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setDoOutput(true);

                JSONObject jsonBody = new JSONObject();
                JSONArray contentsArray = new JSONArray();
                JSONObject contentObj = new JSONObject();
                JSONArray partsArray = new JSONArray();
                JSONObject partObj = new JSONObject();

                partObj.put("text", promptDoWyslania);
                partsArray.put(partObj);
                contentObj.put("parts", partsArray);
                contentsArray.put(contentObj);
                jsonBody.put("contents", contentsArray);

                try (OutputStream os = conn.getOutputStream()) {
                    byte[] input = jsonBody.toString().getBytes(StandardCharsets.UTF_8);
                    os.write(input, 0, input.length);
                }

                int responseCode = conn.getResponseCode();
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                    StringBuilder response = new StringBuilder();
                    String responseLine;
                    while ((responseLine = br.readLine()) != null) {
                        response.append(responseLine.trim());
                    }

                    JSONObject jsonResponse = new JSONObject(response.toString());
                    String aiText = jsonResponse
                            .getJSONArray("candidates")
                            .getJSONObject(0)
                            .getJSONObject("content")
                            .getJSONArray("parts")
                            .getJSONObject(0)
                            .getString("text")
                            .trim();

                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> uruchomSymulacjeRozmowy(aiText));
                    }

                } else {
                    wyslijTekstAwaryjny();
                }
                conn.disconnect();

            } catch (Exception e) {
                Log.e("GeminiHTTP", "Błąd połączenia: " + e.getMessage());
                wyslijTekstAwaryjny();
            }
        }).start();
    }

    private void uruchomSymulacjeRozmowy(String kwestia) {
        if (!isCallActive) return;

        mowDoUzytkownika(kwestia);

        speechHandler.postDelayed(() -> {
            if (isCallActive) {
                uruchomNasluchMowy();
            }
        }, 8000);
    }

    private void wyslijTekstAwaryjny() {
        if (getActivity() != null) {
            getActivity().runOnUiThread(() ->
                    uruchomSymulacjeRozmowy("Halo? Tak, słyszę Cię. Idziesz już tą główną aleją? Już do Ciebie wychodzę.")
            );
        }
    }

    private void mowDoUzytkownika(String tekst) {
        if (textToSpeech != null && isCallActive) {
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                if (textToSpeech != null && isCallActive) {
                    textToSpeech.speak(tekst, TextToSpeech.QUEUE_FLUSH, null, "FakeCallSpeechID");
                }
            }, 200);
        }
    }

    private void stopCallAndClose() {
        isCallActive = false;
        timerHandler.removeCallbacks(timerRunnable);
        speechHandler.removeCallbacksAndMessages(null);

        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }

        if (getParentFragmentManager() != null) {
            getParentFragmentManager().popBackStack();
        }
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        stopCallAndClose();
    }
}