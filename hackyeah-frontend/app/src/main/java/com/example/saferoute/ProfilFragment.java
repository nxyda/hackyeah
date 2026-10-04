package com.example.saferoute;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.InputType;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import java.util.ArrayList;
import java.util.List;

public class ProfilFragment extends Fragment {

    public static final String PREFS_NAME = "SafeRoutePrefs";
    public static final String KEY_NICK = "user_nick";
    public static final String KEY_PHONE = "user_phone";
    public static final String KEY_IS_VERIFIED = "is_phone_verified";

    public static final String[] KEY_SOS_NUMS = {
            "sos_num_1", "sos_num_2", "sos_num_3", "sos_num_4", "sos_num_5"
    };
    public static final String KEY_SOS_MSG = "sos_msg";

    // Pamięć RAM dla kontaktów
    private List<String> currentContacts = new ArrayList<>();

    // Tablice widoków
    private View[] sosRows;
    private EditText[] sosFields;

    public ProfilFragment() { }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_profil, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        SharedPreferences prefs = requireActivity().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        // Znajdowanie widoków profilu
        TextView tvPhoneStatus = view.findViewById(R.id.tv_phone_status);
        TextView tvTrustScore = view.findViewById(R.id.tv_trust_score);
        TextView tvTrustBreakdown = view.findViewById(R.id.tv_trust_breakdown);
        tvTrustScore.setText(String.valueOf(TrustScore.getScore(requireContext())));
        tvTrustBreakdown.setText(
                TrustScore.getReportsCreated(requireContext()) + " zgłoszeń  |  "
                        + TrustScore.getLikes(requireContext()) + " polubień  |  "
                        + TrustScore.getDislikes(requireContext()) + " oznaczeń"
        );
        EditText etNick = view.findViewById(R.id.et_nickname);
        EditText etPhone = view.findViewById(R.id.et_phone);
        Button btnVerifyPhone = view.findViewById(R.id.btn_verify_phone);
        EditText etSosMessage = view.findViewById(R.id.et_sos_message);
        Button btnAddSos = view.findViewById(R.id.btn_add_sos);
        Button btnSaveProfile = view.findViewById(R.id.btn_save_profile);

        sosRows = new View[]{
                view.findViewById(R.id.row_sos_1), view.findViewById(R.id.row_sos_2),
                view.findViewById(R.id.row_sos_3), view.findViewById(R.id.row_sos_4),
                view.findViewById(R.id.row_sos_5)
        };

        sosFields = new EditText[]{
                view.findViewById(R.id.et_sos_contact_1), view.findViewById(R.id.et_sos_contact_2),
                view.findViewById(R.id.et_sos_contact_3), view.findViewById(R.id.et_sos_contact_4),
                view.findViewById(R.id.et_sos_contact_5)
        };

        Button[] delButtons = new Button[]{
                view.findViewById(R.id.btn_del_sos_1), view.findViewById(R.id.btn_del_sos_2),
                view.findViewById(R.id.btn_del_sos_3), view.findViewById(R.id.btn_del_sos_4),
                view.findViewById(R.id.btn_del_sos_5)
        };

        // 1. WCZYTANIE PROFILU I MOJEGO NUMERU
        etNick.setText(prefs.getString(KEY_NICK, ""));

        // Zapisz mockowany numer jeśli to pierwsze uruchomienie (żeby nie było pusto)
        String myPhone = prefs.getString(KEY_PHONE, "");
        if (myPhone.isEmpty()) {
            myPhone = "+48 500 600 700";
            prefs.edit().putString(KEY_PHONE, myPhone).apply();
        }
        etPhone.setText(myPhone);

        if (prefs.getBoolean(KEY_IS_VERIFIED, false)) {
            tvPhoneStatus.setText("✅ Zweryfikowany");
            tvPhoneStatus.setTextColor(0xFF4CAF50);
            btnVerifyPhone.setVisibility(View.GONE);
        }

        // 2. WCZYTANIE KONTAKTÓW SOS (Z RAM)
        currentContacts.clear();
        for(int i = 0; i < 5; i++) {
            String num = prefs.getString(KEY_SOS_NUMS[i], "");
            if(!num.isEmpty()) {
                currentContacts.add(num);
            }
        }
        if(currentContacts.isEmpty()) currentContacts.add(""); // Zawsze min. 1 pole
        refreshSosUI(btnAddSos);

        etSosMessage.setText(prefs.getString(KEY_SOS_MSG, "POMOCY! Uzyto przycisku SOS w SafeRoute."));

        // 3. LOGIKA DODAWANIA I USUWANIA NUMERÓW SOS
        btnAddSos.setOnClickListener(v -> {
            saveInputToRAM(); // Zapisz to co wpisano zanim przeładujemy widok
            if (currentContacts.size() < 5) {
                currentContacts.add("");
                refreshSosUI(btnAddSos);
            }
        });

        for(int i = 0; i < 5; i++) {
            final int index = i;
            delButtons[i].setOnClickListener(v -> {
                saveInputToRAM();
                if (index < currentContacts.size()) {
                    currentContacts.remove(index); // Usuń i przesuń resztę w górę
                }
                if (currentContacts.isEmpty()) currentContacts.add(""); // Nie pozwól usunąć wszystkich
                refreshSosUI(btnAddSos);
            });
        }

        // 4. WERYFIKACJA KODEM 1234
        btnVerifyPhone.setOnClickListener(v -> {
            AlertDialog.Builder builder = new AlertDialog.Builder(requireContext());
            builder.setTitle("Weryfikacja SMS");
            builder.setMessage("Wpisz 4-cyfrowy kod, który wysłaliśmy na Twój numer (wpisz: 1234).");

            final EditText input = new EditText(requireContext());
            input.setInputType(InputType.TYPE_CLASS_NUMBER);
            builder.setView(input);

            builder.setPositiveButton("Zatwierdź", (dialog, which) -> {
                if ("1234".equals(input.getText().toString())) {
                    prefs.edit().putBoolean(KEY_IS_VERIFIED, true).apply();
                    tvPhoneStatus.setText("✅ Zweryfikowany");
                    tvPhoneStatus.setTextColor(0xFF4CAF50);
                    btnVerifyPhone.setVisibility(View.GONE);
                    Toast.makeText(getContext(), "Sukces! Numer zweryfikowany.", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(getContext(), "❌ Błędny kod! Spróbuj ponownie.", Toast.LENGTH_LONG).show();
                }
            });
            builder.setNegativeButton("Anuluj", (dialog, which) -> dialog.cancel());
            builder.show();
        });

        // 5. ZAPISYWANIE CAŁOŚCI
        btnSaveProfile.setOnClickListener(v -> {
            saveInputToRAM();
            SharedPreferences.Editor editor = prefs.edit();
            editor.putString(KEY_NICK, etNick.getText().toString().trim());

            // Czyszczenie starych i zapis nowych SOS
            for (int i = 0; i < 5; i++) {
                if (i < currentContacts.size()) {
                    editor.putString(KEY_SOS_NUMS[i], currentContacts.get(i));
                } else {
                    editor.putString(KEY_SOS_NUMS[i], "");
                }
            }
            editor.putString(KEY_SOS_MSG, etSosMessage.getText().toString().trim());
            editor.apply();

            Toast.makeText(getContext(), "Zapisano profil i " + currentContacts.size() + " numerów SOS!", Toast.LENGTH_SHORT).show();
        });
    }

    // Pomocnicza: Zrzuca zawartość widocznych pól EditText do listy w RAM
    private void saveInputToRAM() {
        for(int i = 0; i < currentContacts.size(); i++) {
            currentContacts.set(i, sosFields[i].getText().toString().trim());
        }
    }

    // Pomocnicza: Rysuje na nowo pola na podstawie listy w RAM
    private void refreshSosUI(Button btnAddSos) {
        for(int i = 0; i < 5; i++) {
            if (i < currentContacts.size()) {
                sosRows[i].setVisibility(View.VISIBLE);
                sosFields[i].setText(currentContacts.get(i));
            } else {
                sosRows[i].setVisibility(View.GONE);
                sosFields[i].setText("");
            }
        }
        btnAddSos.setVisibility(currentContacts.size() < 5 ? View.VISIBLE : View.GONE);
    }
}