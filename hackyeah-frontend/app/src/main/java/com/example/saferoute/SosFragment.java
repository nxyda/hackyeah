package com.example.saferoute;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

public class SosFragment extends Fragment {

    public SosFragment() {
        // Required empty public constructor
    }

    @Nullable
    @Override
    public View onCreateView(
            @NonNull LayoutInflater inflater,
            @Nullable ViewGroup container,
            @Nullable Bundle savedInstanceState
    ) {
        // UWAGA: Zmieniono z fragment_profil na fragment_sos
        return inflater.inflate(
                R.layout.fragment_sos,
                container,
                false
        );
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        View btnSos = view.findViewById(R.id.id_przycisku_sos);

        SosManager sosManager = new SosManager(requireContext(), new SosManager.SosCallback() {
            @Override
            public void onRouteToSafeHavenRequested() {
                if (getActivity() instanceof MainActivity) {
                    com.google.android.material.bottomnavigation.BottomNavigationView bottomNav =
                            getActivity().findViewById(R.id.bottom_navigation);
                    if (bottomNav != null) {
                        bottomNav.setSelectedItemId(R.id.nav_map);
                    }
                }
            }
        });

        if (btnSos != null) {
            sosManager.attachToButton(btnSos);
        }
    }
}