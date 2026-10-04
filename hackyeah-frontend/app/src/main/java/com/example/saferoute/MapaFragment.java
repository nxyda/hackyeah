package com.example.saferoute;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import com.mapbox.geojson.Point;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.fragment.app.Fragment;
import android.location.Location;
import android.location.Address;
import android.location.Geocoder;
import android.os.Handler;
import android.os.Looper;

import com.mapbox.bindgen.Expected;
import com.mapbox.bindgen.Value;
import com.mapbox.geojson.LineString;
import com.mapbox.geojson.Point;
import com.mapbox.maps.CameraOptions;
import com.mapbox.maps.MapView;
import com.mapbox.maps.Style;
import com.mapbox.maps.plugin.Plugin;
import com.mapbox.maps.plugin.annotation.AnnotationConfig;
import com.mapbox.maps.plugin.annotation.AnnotationPlugin;
import com.mapbox.maps.plugin.annotation.generated.PointAnnotation;
import com.mapbox.maps.plugin.annotation.generated.PointAnnotationManager;
import com.mapbox.maps.plugin.annotation.generated.PointAnnotationOptions;
import com.mapbox.maps.plugin.annotation.AnnotationType;
import com.mapbox.maps.plugin.gestures.GesturesPlugin;
import com.mapbox.maps.plugin.gestures.GesturesUtils;
import com.mapbox.maps.plugin.gestures.OnMapClickListener;
import com.mapbox.maps.plugin.locationcomponent.LocationComponentPlugin;
import com.mapbox.maps.plugin.locationcomponent.OnIndicatorPositionChangedListener;
import com.mapbox.maps.RenderedQueryGeometry;
import com.mapbox.maps.RenderedQueryOptions;
import com.mapbox.maps.QueriedRenderedFeature;
import com.mapbox.geojson.Point;
import com.mapbox.maps.plugin.locationcomponent.OnIndicatorBearingChangedListener;
import androidx.activity.OnBackPressedCallback;
import com.mapbox.maps.plugin.LocationPuck2D;
import androidx.core.content.ContextCompat;
import com.mapbox.maps.ImageHolder;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import android.os.Vibrator;
import android.os.VibrationEffect;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;

import com.example.saferoute.api.ApiService;
import com.example.saferoute.api.Camera;
import com.example.saferoute.api.CrimeEvent;
import com.example.saferoute.api.RetrofitClient;
import com.example.saferoute.api.SafePlace;
import com.example.saferoute.api.StreetLamp;
import com.example.saferoute.api.RouteRequest;
import com.example.saferoute.api.RouteResponse;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

import androidx.core.content.ContextCompat;

public class MapaFragment extends Fragment {

    private static class NavigationStep {

        String instruction;
        int distanceMeters;
        String maneuver;

        Point maneuverPoint;

        NavigationStep(
                String instruction,
                int distanceMeters,
                String maneuver,
                Point maneuverPoint
        ) {
            this.instruction = instruction;
            this.distanceMeters = distanceMeters;
            this.maneuver = maneuver;
            this.maneuverPoint = maneuverPoint;
        }
    }

    // =========================================================
    // MAPA
    // =========================================================

    private MapView mapView;

    private LocationComponentPlugin locationComponent;

    private GesturesPlugin gesturesPlugin;


    private AnomalyDetector anomalyDetector;

    // =========================================================
    // WYSZUKIWANIE
    // =========================================================

    private EditText searchDestination;
    private Button searchButton;
    private ImageButton btnSavedPlaces;

    // =========================================================
    // TRASY
    // =========================================================

    private Button safeRouteButton;
    private Button fastRouteButton;
    private Button balancedRouteButton;
    private Button startNavigationButton;
    private View routeInfoPanel;
    private View routeOptionsPanel;

    // =========================================================
    // ZGŁOSZENIE
    // =========================================================

    private Button addReportButton;

    private Button layersButton;
    private Button layerClose;
    private LinearLayout layersPanel;

    private Button layerLighting;
    private Button layerSafePoints;
    private Button layerCameras;
    private Button layerHistorical;
    private Button layerUserReports;


    // =========================================================
    // LOKALIZACJA
    // =========================================================

    private ImageButton locationButton;

    private Point currentLocation;

    private boolean firstLocationReceived = false;

    private boolean locationListenerAdded = false;

    private boolean isNavigating = false;
    private Button btnExitNavigation;

    // Nasłuchiwacz kompasu - obraca mapę z telefonem
    private final OnIndicatorBearingChangedListener onIndicatorBearingChangedListener = bearing -> {
        if (mapView != null && isNavigating) {
            // "Zatrzaskujemy" kamerę na aktualnym obrocie, bez dotykania ustawień Mapboxa!
            mapView.getMapboxMap().setCamera(
                    new CameraOptions.Builder().bearing(bearing).build()
            );
        }
    };

    private static final int LOCATION_PERMISSION_REQUEST_CODE = 1001;

    // =========================================================
    // TEKSTY UI
    // =========================================================

    private TextView startPoint;
    private TextView destinationPoint;
    private TextView routeDetails;
    private TextView safetyStatus;

    private LinearLayout navigationStepsPanel;

    // =========================================================
    // PANEL INFORMACJI O ZGŁOSZENIU
    // =========================================================

    private LinearLayout reportInfoPanel;

    private TextView reportInfoCategory;
    private TextView reportInfoTime;
    private TextView reportInfoId;
    private TextView reportInfoConfirmations;

    private Button reportInfoConfirm;
    private Button reportInfoInvalid;
    private Button reportInfoClose;

    private TextView navigationRouteSummary;

    // =========================================================
    // TESTOWY CEL
    // =========================================================

    private Point destinationLocation;

    private RouteResponse currentRouteResponse;
    private RouteResponse.RouteOption selectedRoute;
    private String selectedRouteName;
    private ExecutorService geocoderExecutor;
    private Call<RouteResponse> routeCall;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private int routeSearchGeneration = 0;
    private final Runnable reportExpiryCleanup = new Runnable() {
        @Override
        public void run() {
            if (!isAdded() || mapView == null) {
                return;
            }
            int previousSize = reports.size();
            reports.removeIf(MapaFragment.this::isLocallyExpired);
            if (reports.size() != previousSize) {
                updateReportMarkers();
            }
            mainHandler.postDelayed(this, 30_000L);
        }
    };

    // =========================================================
    // TRASA
    // =========================================================

    private static final String ROUTE_SOURCE_ID =
            "test-route-source";

    private static final String ROUTE_LAYER_ID =
            "test-route-layer";

    // =========================================================
    // ZGŁOSZENIA
    // =========================================================

    private static final String REPORT_SOURCE_ID =
            "reports-source";

    private static final String REPORT_LAYER_ID =
            "reports-layer";

    private static final String STREET_LAMPS_SOURCE_ID =
            "street-lamps-source";

    private static final String STREET_LAMPS_LAYER_ID =
            "street-lamps-heatmap";

    private static final double CITY_LAYERS_RADIUS_METERS = 1000.0;
    private static final int MAX_POINT_ANNOTATIONS = 2000;
    private static final int MAX_HEATMAP_POINTS = 12000;

    private final List<Report> reports =
            new ArrayList<>();

    private LinearLayout navigationCurrentStep;
    private LinearLayout navigationAllSteps;

    private TextView navigationCurrentIcon;
    private TextView navigationCurrentInstruction;
    private TextView navigationCurrentDistance;
    private TextView navigationExpandIcon;

    private boolean navigationExpanded = false;

    private List<NavigationStep> currentNavigationSteps =
            new ArrayList<>();

    private int currentNavigationStepIndex = 0;

    private boolean navigationVibrationTriggered = false;

    private static final double VIBRATION_DISTANCE_METERS = 30.0;

    private Report selectedReportForFeedback;
    private static final String REPORT_PREFS = "SafeRouteReportPrefs";
    private static final long REPORT_EXPIRY_MS = 60L * 60L * 1000L;

    private boolean lightingLayerEnabled = true;

    private boolean safePointsLayerEnabled = true;
    private PointAnnotationManager safePointAnnotationManager;

    private LinearLayout safePointInfoPanel;

    private TextView safePointInfoTitle;
    private TextView safePointInfoName;
    private TextView safePointInfoCategory;
    private TextView safePointInfoHours;
    private TextView safePointInfo247;

    private Button safePointInfoClose;

    private Map<String, SafePoint> safePointMap =
            new HashMap<>();

    private Map<String, SafePlace> apiSafePlaceMap =
            new HashMap<>();

    private boolean camerasLayerEnabled = true;
    private PointAnnotationManager cameraAnnotationManager;

    private PointAnnotationManager crimeEventAnnotationManager;
    private Map<String, CrimeEvent> crimeEventMap =
            new HashMap<>();

    private boolean userReportsLayerEnabled = true;

    private PointAnnotationManager historicalThreatAnnotationManager;

    private Map<String, HistoricalThreat> historicalThreatMap =
            new HashMap<>();

    private boolean historicalThreatsLayerEnabled = true;

    private LinearLayout historicalThreatInfoPanel;

    private TextView historicalThreatInfoCategory;
    private TextView historicalThreatInfoDate;
    private TextView historicalThreatInfoSeverity;
    private TextView historicalThreatInfoScore;

    private Button historicalThreatInfoClose;

    private boolean cityEventsLayerEnabled = true;

    private PointAnnotationManager cityEventAnnotationManager;

    private Map<String, CityEvent> cityEventMap = new HashMap<>();

    private LinearLayout cityEventInfoPanel;
    private TextView cityEventInfoTitle;
    private TextView cityEventInfoCategory;
    private TextView cityEventInfoDescription;
    private TextView cityEventInfoDate;
    private TextView cityEventInfoRisk;
    private Button cityEventInfoClose;

    private static class CityEvent {

        String title;
        String description;
        String category;

        String startsAt;
        String endsAt;

        double latitude;
        double longitude;

        double radiusMeters;
        double riskIncrease;

        CityEvent(
                String title,
                String description,
                String category,
                String startsAt,
                String endsAt,
                double latitude,
                double longitude,
                double radiusMeters,
                double riskIncrease
        ) {
            this.title = title;
            this.description = description;
            this.category = category;
            this.startsAt = startsAt;
            this.endsAt = endsAt;
            this.latitude = latitude;
            this.longitude = longitude;
            this.radiusMeters = radiusMeters;
            this.riskIncrease = riskIncrease;
        }
    }


    private static class HistoricalThreat {

        String category;
        String occuredAt;
        double severity;
        double latitude;
        double longitude;

        HistoricalThreat(
                String category,
                String occuredAt,
                double severity,
                double latitude,
                double longitude
        ) {
            this.category = category;
            this.occuredAt = occuredAt;
            this.severity = severity;
            this.latitude = latitude;
            this.longitude = longitude;
        }
    }


    // =========================================================
    // MODEL ZGŁOSZENIA
    // =========================================================

    private static class Report {

        String id;

        double latitude;
        double longitude;

        String category;

        String createdAt;
        String expiresAt;
        int confirmations;

        Report(
                String id,
                double latitude,
                double longitude,
                String category,
                String createdAt,
                String expiresAt,
                int confirmations
        ) {

            this.id = id;

            this.latitude = latitude;

            this.longitude = longitude;

            this.category = category;

            this.createdAt = createdAt;
            this.expiresAt = expiresAt;
            this.confirmations = confirmations;
        }
    }

    // =========================================================
    // API SAFE PLACES
    // =========================================================
    private void loadNearbySafePlaces(Point point) {

        ApiService apiService = RetrofitClient.getApiService();

        Call<List<SafePlace>> call = apiService.getNearbySafePlaces(
                point.longitude(),
                point.latitude(),
                CITY_LAYERS_RADIUS_METERS
        );

        call.enqueue(new Callback<List<SafePlace>>() {

            @Override
            public void onResponse(
                    Call<List<SafePlace>> call,
                    Response<List<SafePlace>> response
            ) {
                if (response.isSuccessful() && response.body() != null) {

                    List<SafePlace> places = response.body();
                    System.out.println(
                            "Safe places z API: " + places.size()
                    );

                    updateSafePointMarkers(places);

                } else {
                    System.out.println("Błąd API: " + response.code());
                }
            }

            @Override
            public void onFailure(
                    Call<List<SafePlace>> call,
                    Throwable t
            ) {
                System.out.println("Błąd połączenia z API: " + t.getMessage());
            }
        });
    }

    private void loadNearbyCameras(Point point) {

        ApiService apiService = RetrofitClient.getApiService();

        Call<List<Camera>> call = apiService.getNearbyCameras(
                point.longitude(),
                point.latitude(),
                CITY_LAYERS_RADIUS_METERS
        );

        call.enqueue(new Callback<List<Camera>>() {

            @Override
            public void onResponse(
                    Call<List<Camera>> call,
                    Response<List<Camera>> response
            ) {
                if (response.isSuccessful() && response.body() != null) {
                    System.out.println(
                            "Kamery z API: " + response.body().size()
                    );
                    updateCameraMarkers(response.body());
                } else {
                    System.out.println("Błąd API kamer: " + response.code());
                }
            }

            @Override
            public void onFailure(
                    Call<List<Camera>> call,
                    Throwable t
            ) {
                System.out.println("Błąd połączenia z API kamer: " + t.getMessage());
            }
        });
    }

    private void loadNearbyStreetLamps(Point point) {

        ApiService apiService = RetrofitClient.getApiService();

        Call<List<StreetLamp>> call = apiService.getNearbyStreetLamps(
                point.longitude(),
                point.latitude(),
                CITY_LAYERS_RADIUS_METERS
        );

        call.enqueue(new Callback<List<StreetLamp>>() {

            @Override
            public void onResponse(
                    Call<List<StreetLamp>> call,
                    Response<List<StreetLamp>> response
            ) {
                if (response.isSuccessful() && response.body() != null) {
                    System.out.println(
                            "Latarnie z API: " + response.body().size()
                    );
                    updateStreetLampMarkers(response.body());
                } else {
                    System.out.println(
                            "Błąd API latarni: " + response.code()
                    );
                }
            }

            @Override
            public void onFailure(
                    Call<List<StreetLamp>> call,
                    Throwable t
            ) {
                System.out.println(
                        "Błąd połączenia z API latarni: " + t.getMessage()
                );
            }
        });
    }

    private void loadNearbyCrimeEvents(Point point) {

        ApiService apiService = RetrofitClient.getApiService();

        Call<List<CrimeEvent>> call = apiService.getNearbyCrimeEvents(
                point.longitude(),
                point.latitude(),
                CITY_LAYERS_RADIUS_METERS,
                null,
                null
        );

        call.enqueue(new Callback<List<CrimeEvent>>() {

            @Override
            public void onResponse(
                    Call<List<CrimeEvent>> call,
                    Response<List<CrimeEvent>> response
            ) {
                if (response.isSuccessful() && response.body() != null) {
                    System.out.println(
                            "Crime events z API: " + response.body().size()
                    );
                    updateCrimeEventMarkers(response.body());
                } else {
                    System.out.println(
                            "Błąd API crime events: " + response.code()
                    );
                }
            }

            @Override
            public void onFailure(
                    Call<List<CrimeEvent>> call,
                    Throwable t
            ) {
                System.out.println(
                        "Błąd połączenia z API crime events: " + t.getMessage()
                );
            }
        });
    }

    // =========================================================
    // LISTENER GPS
    // =========================================================

    private final OnIndicatorPositionChangedListener onIndicatorPositionChangedListener = new OnIndicatorPositionChangedListener() {
        @Override
        public void onIndicatorPositionChanged(Point point) {
            currentLocation = point;
            updateNavigationProgress(point);
            
            if (anomalyDetector != null) {
                Location androidLoc = new Location("Mapbox");
                androidLoc.setLatitude(point.latitude());
                androidLoc.setLongitude(point.longitude());
                anomalyDetector.processNewLocation(androidLoc);
            }

            if (mapView != null) {
                if (isNavigating) {
                    // Kamera "goni" kropkę podczas nawigacji 3D
                    mapView.getMapboxMap().setCamera(
                            new CameraOptions.Builder().center(point).build()
                    );
                } else if (!firstLocationReceived) {
                    // Pierwsze odpalenie aplikacji (centrowanie mapy)
                    firstLocationReceived = true;

                    loadNearbySafePlaces(point);
                    loadNearbyCameras(point);
                    loadNearbyStreetLamps(point);
                    loadNearbyCrimeEvents(point);

                    mapView.getMapboxMap().setCamera(
                            new CameraOptions.Builder().center(point).zoom(14.0).build()
                    );
                }
            }
        }
    };

    // =========================================================
    // CLICK NA MAPIE
    // =========================================================

    private final OnMapClickListener
            onMapClickListener =
            point -> {

                if (mapView == null) {
                    return false;
                }

                RenderedQueryGeometry geometry =
                        new RenderedQueryGeometry(
                                mapView
                                        .getMapboxMap()
                                        .pixelForCoordinate(point)
                        );

                RenderedQueryOptions options =
                        new RenderedQueryOptions(
                                Arrays.asList(
                                        REPORT_LAYER_ID
                                ),
                                null
                        );

                mapView
                        .getMapboxMap()
                        .queryRenderedFeatures(
                                geometry,
                                options,
                                expected -> {

                                    if (expected == null
                                            || !expected.isValue()) {
                                        showNearbyReportAt(point);
                                        return;
                                    }

                                    List<QueriedRenderedFeature>
                                            features =
                                            expected.getValue();

                                    if (features == null
                                            || features.isEmpty()) {
                                        showNearbyReportAt(point);
                                        return;
                                    }

                                    QueriedRenderedFeature
                                            queriedFeature =
                                            features.get(0);

                                    if (queriedFeature == null
                                            || queriedFeature
                                            .getQueriedFeature()
                                            == null) {
                                        showNearbyReportAt(point);
                                        return;
                                    }

                                    com.mapbox.geojson.Feature
                                            feature =
                                            queriedFeature
                                                    .getQueriedFeature()
                                                    .getFeature();

                                    if (feature == null) {
                                        showNearbyReportAt(point);
                                        return;
                                    }

                                    String reportId =
                                            feature.getStringProperty(
                                                    "id"
                                            );

                                    for (Report report : reports) {
                                        if (report.id.equals(reportId)) {
                                            showReportInfo(report);
                                            return;
                                        }
                                    }
                                    showNearbyReportAt(point);
                                }
                        );

                return true;
            };

    private void showNearbyReportAt(Point tappedPoint) {
        Report nearestReport = null;
        float nearestDistance = 40f;
        for (Report report : reports) {
            float[] distance = new float[1];
            Location.distanceBetween(
                    tappedPoint.latitude(),
                    tappedPoint.longitude(),
                    report.latitude,
                    report.longitude,
                    distance
            );
            if (distance[0] <= nearestDistance) {
                nearestDistance = distance[0];
                nearestReport = report;
            }
        }
        if (nearestReport != null) {
            showReportInfo(nearestReport);
        }
    }

    // =========================================================
    // ON CREATE VIEW
    // =========================================================

    @Nullable
    @Override
    public View onCreateView(
            @NonNull LayoutInflater inflater,
            @Nullable ViewGroup container,
            @Nullable Bundle savedInstanceState
    ) {

        View view =
                inflater.inflate(
                        R.layout.fragment_mapa,
                        container,
                        false
                );

        geocoderExecutor = Executors.newSingleThreadExecutor();
        anomalyDetector = new AnomalyDetector(requireContext());

        // =====================================================
        // MAPA
        // =====================================================

        mapView =
                view.findViewById(
                        R.id.mapView
                );
        navigationStepsPanel =
                view.findViewById(R.id.navigation_steps_panel);

        // =====================================================
        // LOCATION COMPONENT
        // =====================================================

        locationComponent =
                mapView.getPlugin(
                        Plugin.MAPBOX_LOCATION_COMPONENT_PLUGIN_ID
                );

        // =====================================================
        // GESTURES
        // =====================================================

        gesturesPlugin =
                GesturesUtils.getGestures(
                        mapView
                );

        gesturesPlugin.addOnMapClickListener(
                onMapClickListener
        );

        // =====================================================
        // WYSZUKIWANIE
        // =====================================================

        searchDestination =
                view.findViewById(
                        R.id.search_destination
                );

        searchButton =
                view.findViewById(
                        R.id.search_button
                );

        btnSavedPlaces = view.findViewById(R.id.btn_saved_places);
        btnSavedPlaces.setOnClickListener(v -> showSavedPlacesMenu());

        // =====================================================
        // LOKALIZACJA
        // =====================================================

        locationButton =
                view.findViewById(
                        R.id.location_button
                );

        // =====================================================
        // ZGŁOSZENIE
        // =====================================================

        addReportButton =
                view.findViewById(
                        R.id.add_report_button
                );

        layersButton =
                view.findViewById(
                        R.id.layers_button
                );

        layerClose =
                view.findViewById(
                        R.id.layer_close);

        layersPanel =
                view.findViewById(
                        R.id.layers_panel
                );

        layerLighting =
                view.findViewById(
                        R.id.layer_lighting
                );

        layerSafePoints =
                view.findViewById(
                        R.id.layer_safe_points
                );

        layerCameras =
                view.findViewById(
                        R.id.layer_cameras
                );

        layerHistorical =
                view.findViewById(
                        R.id.layer_historical
                );

        historicalThreatInfoPanel =
                view.findViewById(R.id.historical_threat_info_panel);

        historicalThreatInfoCategory =
                view.findViewById(R.id.historical_threat_info_category);

        historicalThreatInfoDate =
                view.findViewById(R.id.historical_threat_info_date);

        historicalThreatInfoSeverity =
                view.findViewById(R.id.historical_threat_info_severity);

        historicalThreatInfoScore =
                view.findViewById(R.id.historical_threat_info_score);

        historicalThreatInfoClose =
                view.findViewById(R.id.historical_threat_info_close);

        historicalThreatInfoClose.setOnClickListener(
                v -> historicalThreatInfoPanel.setVisibility(View.GONE)
        );

        layerUserReports =
                view.findViewById(
                        R.id.layer_user_reports
                );

        layersButton.setOnClickListener(v -> {

            if (layersPanel.getVisibility() == View.VISIBLE) {

                layersPanel.setVisibility(
                        View.GONE
                );

            } else {

                layersPanel.setVisibility(
                        View.VISIBLE
                );
            }
        });

        layerClose.setOnClickListener(v -> {
            layersPanel.setVisibility(View.GONE);
        });

        navigationStepsPanel =
                view.findViewById(
                        R.id.navigation_steps_panel
                );

        navigationCurrentStep =
                view.findViewById(
                        R.id.navigation_current_step
                );


        navigationAllSteps =
                view.findViewById(
                        R.id.navigation_all_steps
                );

        navigationCurrentIcon =
                view.findViewById(
                        R.id.navigation_current_icon
                );

        navigationCurrentInstruction =
                view.findViewById(
                        R.id.navigation_current_instruction
                );

        navigationCurrentDistance =
                view.findViewById(
                        R.id.navigation_current_distance
                );

        navigationExpandIcon =
                view.findViewById(
                        R.id.navigation_expand_icon
                );

        navigationCurrentStep.setOnClickListener(v -> {

            navigationExpanded =
                    !navigationExpanded;

            updateNavigationPanel();
        });

        navigationRouteSummary =
                view.findViewById(
                        R.id.navigation_route_summary
                );

        btnExitNavigation = view.findViewById(R.id.btn_exit_navigation);
        btnExitNavigation.setOnClickListener(v -> exitNavigationMode());

        // =====================================================
        // TRASY
        // =====================================================

        safeRouteButton =
                view.findViewById(
                        R.id.safe_route_button
                );

        fastRouteButton =
                view.findViewById(
                        R.id.fast_route_button
                );

        balancedRouteButton =
                view.findViewById(
                        R.id.balanced_route_button
                );

        startNavigationButton =
                view.findViewById(R.id.start_navigation_button);
        startNavigationButton.setOnClickListener(v -> startNavigationForSelectedRoute());
        routeInfoPanel = view.findViewById(R.id.route_info_panel);
        routeOptionsPanel = view.findViewById(R.id.route_options_panel);

        // =====================================================
        // INFORMACJE O TRASIE
        // =====================================================

        startPoint =
                view.findViewById(
                        R.id.start_point
                );

        destinationPoint =
                view.findViewById(
                        R.id.destination_point
                );

        routeDetails =
                view.findViewById(
                        R.id.route_details
                );

        safetyStatus =
                view.findViewById(
                        R.id.safety_status
                );

        // =====================================================
        // PANEL ZGŁOSZENIA
        // =====================================================

        reportInfoPanel =
                view.findViewById(
                        R.id.report_info_panel
                );

        reportInfoCategory =
                view.findViewById(
                        R.id.report_info_category
                );

        reportInfoTime =
                view.findViewById(
                        R.id.report_info_time
                );

        reportInfoId =
                view.findViewById(
                        R.id.report_info_id
                );

        reportInfoConfirmations =
                view.findViewById(
                        R.id.report_info_confirmations
                );

        reportInfoConfirm =
                view.findViewById(
                        R.id.report_info_confirm
                );

        reportInfoInvalid =
                view.findViewById(
                        R.id.report_info_invalid
                );

        reportInfoClose =
                view.findViewById(
                        R.id.report_info_close
                );

        safePointInfoPanel =
                view.findViewById(
                        R.id.safe_point_info_panel
                );

        safePointInfoTitle =
                view.findViewById(
                        R.id.safe_point_info_title
                );

        safePointInfoName =
                view.findViewById(
                        R.id.safe_point_info_name
                );

        safePointInfoCategory =
                view.findViewById(
                        R.id.safe_point_info_category
                );

        safePointInfoHours =
                view.findViewById(
                        R.id.safe_point_info_hours
                );

        safePointInfo247 =
                view.findViewById(
                        R.id.safe_point_info_247
                );

        safePointInfoClose =
                view.findViewById(
                        R.id.safe_point_info_close
                );

        cityEventInfoPanel =
                view.findViewById(R.id.city_event_info_panel);

        cityEventInfoTitle =
                view.findViewById(R.id.city_event_info_title);

        cityEventInfoCategory =
                view.findViewById(R.id.city_event_info_category);

        cityEventInfoDescription =
                view.findViewById(R.id.city_event_info_description);

        cityEventInfoDate =
                view.findViewById(R.id.city_event_info_date);

        cityEventInfoRisk =
                view.findViewById(R.id.city_event_info_risk);

        cityEventInfoClose =
                view.findViewById(R.id.city_event_info_close);

        cityEventInfoClose.setOnClickListener(
                v -> cityEventInfoPanel.setVisibility(View.GONE)
        );

        safePointInfoClose.setOnClickListener(
                v -> safePointInfoPanel.setVisibility(
                        View.GONE
                )
        );

        reportInfoConfirm.setOnClickListener(v -> {
            if (selectedReportForFeedback != null) {
                saveReportReaction(selectedReportForFeedback, "like");
            }
        });

        reportInfoInvalid.setOnClickListener(v -> {
            if (selectedReportForFeedback != null) {
                saveReportReaction(selectedReportForFeedback, "dislike");
            }
        });

        reportInfoPanel.setVisibility(
                View.GONE
        );

        Button layerCityEvents =
                view.findViewById(
                        R.id.layer_city_events
                );

        // =====================================================
        // MAPBOX STYLE
        // =====================================================

        mapView
                .getMapboxMap()
                .loadStyleUri(
                        Style.MAPBOX_STREETS,
                        style -> {

                            // ---------------------------------
                            // GPS
                            // ---------------------------------

                            if (ActivityCompat.checkSelfPermission(
                                    requireContext(),
                                    Manifest.permission
                                            .ACCESS_FINE_LOCATION
                            ) == PackageManager.PERMISSION_GRANTED
                                    || ActivityCompat.checkSelfPermission(
                                    requireContext(),
                                    Manifest.permission
                                            .ACCESS_COARSE_LOCATION
                            ) == PackageManager.PERMISSION_GRANTED) {

                                enableLocation();

                            } else {

                                requestLocationPermission();
                            }

                            // ---------------------------------
                            // ZGŁOSZENIA
                            // ---------------------------------

                            updateReportMarkers();

                            updateCityEventMarkers();
                        }
                );

        // =====================================================
        // SZUKANIE
        // =====================================================

        searchButton.setOnClickListener(v -> {

            String destination =
                    searchDestination
                            .getText()
                            .toString()
                            .trim();

            if (destination.isEmpty()) {

                Toast.makeText(
                        requireContext(),
                        "Wpisz miejsce docelowe.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            if (currentLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Czekam na Twoją lokalizację.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            destinationPoint.setText(
                    "🏁 Cel: " + destination
            );
            geocodeAndCreateRoute(destination);
        });

        // =====================================================
        // MOJA LOKALIZACJA
        // =====================================================

        locationButton.setOnClickListener(v -> {

            if (currentLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Czekam na lokalizację.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            mapView.getMapboxMap().setCamera(
                    new CameraOptions.Builder()
                            .center(currentLocation)
                            .zoom(15.0)
                            .build()
            );
        });

        // =====================================================
        // DODAJ ZGŁOSZENIE
        // =====================================================

        addReportButton.setOnClickListener(v -> {

            if (currentLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Czekam na Twoją lokalizację.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            showReportCategoryDialog();
        });

        // =====================================================
        // ZAMKNIJ INFO
        // =====================================================

        reportInfoClose.setOnClickListener(
                v -> hideReportInfo()
        );

        // =====================================================
        // NAJBEZPIECZNIEJSZA
        // =====================================================

        safeRouteButton.setOnClickListener(v -> {

            if (currentLocation == null
                    || destinationLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Najpierw ustaw cel.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            drawSafeRoute();
        });

        // =====================================================
        // NAJSZYBSZA
        // =====================================================

        fastRouteButton.setOnClickListener(v -> {

            if (currentLocation == null
                    || destinationLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Najpierw ustaw cel.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            drawFastRoute();
        });

        // =====================================================
        // ZBALANSOWANA
        // =====================================================

        balancedRouteButton.setOnClickListener(v -> {

            if (currentLocation == null
                    || destinationLocation == null) {

                Toast.makeText(
                        requireContext(),
                        "Najpierw ustaw cel.",
                        Toast.LENGTH_SHORT
                ).show();

                return;
            }

            drawBalancedRoute();
        });

        setupLayerButton(
                layerLighting,
                "💡",
                "💡",
                () -> {
                    lightingLayerEnabled =
                            (boolean) layerLighting.getTag();

                    updateStreetLampLayerVisibility();
                }
        );

        setupLayerButton(
                layerSafePoints,
                "🛡",
                "🛡",
                () -> {

                    safePointsLayerEnabled =
                            (boolean) layerSafePoints.getTag();

                    updateSafePointLayerVisibility();
                }
        );

        setupLayerButton(
                layerCameras,
                "📷",
                "📷",
                () -> {

                    camerasLayerEnabled =
                            (boolean) layerCameras.getTag();

                    updateCameraLayerVisibility();
                }
        );

        setupLayerButton(
                layerHistorical,
                "🕰",
                "🕰",
                () -> {

                    historicalThreatsLayerEnabled =
                            (boolean) layerHistorical.getTag();

                    updateHistoricalThreatLayerVisibility();
                }
        );

        setupLayerButton(
                layerUserReports,
                "🚨",
                "🚨",
                () -> {

                    userReportsLayerEnabled =
                            (boolean) layerUserReports.getTag();

                    updateReportLayerVisibility();
                }
        );

        setupLayerButton(
                layerCityEvents,
                "🏟",
                "🏟",
                () -> {

                    cityEventsLayerEnabled =
                            (boolean) layerCityEvents.getTag();

                    updateCityEventLayerVisibility();
                }
        );

        requireActivity().getOnBackPressedDispatcher().addCallback(getViewLifecycleOwner(), new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (isNavigating) {
                    exitNavigationMode();
                } else if (layersPanel != null && layersPanel.getVisibility() == View.VISIBLE) {
                    layersPanel.setVisibility(View.GONE);
                } else if (reportInfoPanel != null && reportInfoPanel.getVisibility() == View.VISIBLE) {
                    reportInfoPanel.setVisibility(View.GONE);
                } else {
                    setEnabled(false);
                    requireActivity().onBackPressed();
                }
            }
        });

        mainHandler.removeCallbacks(reportExpiryCleanup);
        mainHandler.postDelayed(reportExpiryCleanup, 30_000L);

        return view;
    }

    // =========================================================
    // DIALOG KATEGORII
    // =========================================================

    private void showReportCategoryDialog() {
        String[] categoryValues = {
                "danger", "harassment", "poor_lighting",
                "blocked_path", "suspicious_activity", "other"
        };
        String[] categoryLabels = {
                "Niebezpieczeństwo", "Nękanie", "Słabe oświetlenie",
                "Zablokowana droga", "Podejrzana aktywność", "Inne"
        };
        String[] categoryIcons = {"⚠️", "🛑", "💡", "🚧", "👀", "📍"};

        int padding = dp(20);
        LinearLayout content = new LinearLayout(requireContext());
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(padding, padding, padding, dp(12));
        content.setBackground(roundedBackground("#1E1E1E", dp(20)));

        TextView title = new TextView(requireContext());
        title.setText("Dodaj zgłoszenie");
        title.setTextColor(android.graphics.Color.WHITE);
        title.setTextSize(21);
        title.setTypeface(null, Typeface.BOLD);
        content.addView(title);

        TextView subtitle = new TextView(requireContext());
        subtitle.setText("Wybierz, co dzieje się w tej okolicy");
        subtitle.setTextColor(android.graphics.Color.parseColor("#BDBDBD"));
        subtitle.setTextSize(14);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        subtitleParams.topMargin = dp(6);
        subtitleParams.bottomMargin = dp(14);
        content.addView(subtitle, subtitleParams);

        LinearLayout categories = new LinearLayout(requireContext());
        categories.setOrientation(LinearLayout.VERTICAL);
        int[] selectedCategory = {0};
        List<View> categoryRows = new ArrayList<>();
        List<TextView> selectionMarks = new ArrayList<>();

        for (int i = 0; i < categoryLabels.length; i++) {
            final int index = i;
            LinearLayout row = new LinearLayout(requireContext());
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(12), 0, dp(12), 0);
            row.setMinimumHeight(dp(50));

            TextView icon = new TextView(requireContext());
            icon.setText(categoryIcons[i]);
            icon.setTextSize(19);
            icon.setGravity(Gravity.CENTER);
            row.addView(icon, new LinearLayout.LayoutParams(dp(34), dp(42)));

            TextView label = new TextView(requireContext());
            label.setText(categoryLabels[i]);
            label.setTextColor(android.graphics.Color.WHITE);
            label.setTextSize(15);
            LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(
                    0,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    1
            );
            labelParams.leftMargin = dp(8);
            row.addView(label, labelParams);

            TextView mark = new TextView(requireContext());
            mark.setText("✓");
            mark.setTextColor(android.graphics.Color.parseColor("#FF028D"));
            mark.setTextSize(17);
            mark.setTypeface(null, Typeface.BOLD);
            mark.setGravity(Gravity.CENTER);
            row.addView(mark, new LinearLayout.LayoutParams(dp(28), dp(42)));

            categoryRows.add(row);
            selectionMarks.add(mark);
            row.setOnClickListener(v -> {
                selectedCategory[0] = index;
                updateReportCategorySelection(categoryRows, selectionMarks, selectedCategory[0]);
            });
            LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    dp(50)
            );
            if (i > 0) {
                rowParams.topMargin = dp(5);
            }
            categories.addView(row, rowParams);
        }
        updateReportCategorySelection(categoryRows, selectionMarks, selectedCategory[0]);
        content.addView(categories);

        LinearLayout actions = new LinearLayout(requireContext());
        actions.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        actions.setPadding(0, dp(12), 0, 0);

        Button cancel = new Button(requireContext());
        cancel.setText("Anuluj");
        cancel.setTextColor(android.graphics.Color.parseColor("#BDBDBD"));
        cancel.setAllCaps(false);
        cancel.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        actions.addView(cancel);

        Button submit = new Button(requireContext());
        submit.setText("Dodaj zgłoszenie");
        submit.setTextColor(android.graphics.Color.WHITE);
        submit.setTextSize(14);
        submit.setTypeface(null, Typeface.BOLD);
        submit.setAllCaps(false);
        submit.setPadding(dp(14), 0, dp(14), 0);
        submit.setBackground(roundedBackground("#FF028D", dp(12)));
        LinearLayout.LayoutParams submitParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(46)
        );
        submitParams.leftMargin = dp(8);
        actions.addView(submit, submitParams);
        content.addView(actions);

        AlertDialog dialog = new AlertDialog.Builder(requireContext()).create();
        cancel.setOnClickListener(v -> dialog.dismiss());
        submit.setOnClickListener(v -> {
            dialog.dismiss();
            addReport(categoryValues[selectedCategory[0]]);
        });
        dialog.setView(content);
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(
                    new android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT)
            );
            dialog.getWindow().setLayout(
                    Math.min(dp(380), getResources().getDisplayMetrics().widthPixels - dp(32)),
                    ViewGroup.LayoutParams.WRAP_CONTENT
            );
        }
    }

    private void updateReportCategorySelection(
            List<View> rows,
            List<TextView> marks,
            int selectedIndex
    ) {
        for (int i = 0; i < rows.size(); i++) {
            boolean selected = i == selectedIndex;
            rows.get(i).setBackground(roundedBackground(
                    selected ? "#472b40" : "#292929",
                    dp(12)
            ));
            marks.get(i).setVisibility(selected ? View.VISIBLE : View.INVISIBLE);
        }
    }

    private android.graphics.drawable.GradientDrawable roundedBackground(
            String color,
            int radius
    ) {
        android.graphics.drawable.GradientDrawable background =
                new android.graphics.drawable.GradientDrawable();
        background.setColor(android.graphics.Color.parseColor(color));
        background.setCornerRadius(radius);
        return background;
    }

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    // =========================================================
    // DODAJ ZGŁOSZENIE
    // =========================================================

    private void addReport(
            String category
    ) {

        if (currentLocation == null) {

            Toast.makeText(
                    requireContext(),
                    "Brak aktualnej lokalizacji.",
                    Toast.LENGTH_SHORT
            ).show();

            return;
        }

        SimpleDateFormat format = new SimpleDateFormat(
                "dd.MM.yyyy, HH:mm",
                Locale.US
        );
        format.setTimeZone(java.util.TimeZone.getTimeZone("Europe/Warsaw"));
        Report report = new Report(
                UUID.randomUUID().toString(),
                currentLocation.latitude(),
                currentLocation.longitude(),
                category,
                format.format(new Date()),
                null,
                0
        );
        reports.add(report);
        TrustScore.recordReportCreated(requireContext());
        updateReportMarkers();
        Toast.makeText(
                requireContext(),
                "Dodano zgłoszenie na tym urządzeniu.",
                Toast.LENGTH_SHORT
        ).show();
    }

    private boolean isLocallyExpired(Report report) {
        if (report.confirmations > 0) {
            return false;
        }
        long expiresAt = parseApiTime(report.expiresAt);
        if (expiresAt > 0) {
            return expiresAt <= System.currentTimeMillis();
        }
        long createdAt = parseApiTime(report.createdAt);
        return createdAt > 0
                && System.currentTimeMillis() - createdAt >= REPORT_EXPIRY_MS;
    }

    private long parseApiTime(String value) {
        if (value == null || value.length() < 19) {
            return -1;
        }
        try {
            SimpleDateFormat format = new SimpleDateFormat(
                    "yyyy-MM-dd'T'HH:mm:ss",
                    Locale.US
            );
            format.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
            return format.parse(value.substring(0, 19)).getTime();
        } catch (java.text.ParseException exception) {
            return -1;
        }
    }

    private SharedPreferences reportPreferences() {
        return requireContext().getSharedPreferences(REPORT_PREFS, Context.MODE_PRIVATE);
    }

    private String reactionKey(String reportId) {
        return "reaction_" + reportId;
    }

    private void saveReportReaction(Report report, String reaction) {
        if (!isAdded() || report == null) {
            return;
        }
        if (reportPreferences().contains(reactionKey(report.id))) {
            Toast.makeText(
                    requireContext(),
                    "Na to zgłoszenie można zareagować tylko raz.",
                    Toast.LENGTH_SHORT
            ).show();
            return;
        }
        if (isLocallyExpired(report) && report.confirmations <= 0) {
            Toast.makeText(requireContext(), "To zgłoszenie wygasło po godzinie bez potwierdzeń.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!TrustScore.recordReaction(requireContext(), report.id, reaction)) {
            Toast.makeText(
                    requireContext(),
                    "Na to zgłoszenie można zareagować tylko raz.",
                    Toast.LENGTH_SHORT
            ).show();
            return;
        }
        if ("like".equals(reaction)) {
            report.confirmations++;
        }
        showReportInfo(report);
        updateReportMarkers();
        Toast.makeText(
                requireContext(),
                "Reakcja zapisana na tym urządzeniu.",
                Toast.LENGTH_SHORT
        ).show();
    }

    // =========================================================
    // MARKERY ZGŁOSZEŃ
    // =========================================================

    private void updateReportMarkers() {

        if (mapView == null) {
            return;
        }
        reports.removeIf(this::isLocallyExpired);

        mapView.getMapboxMap().getStyle(
                style -> {

                    // -----------------------------------------
                    // USUŃ STARĄ WARSTWĘ
                    // -----------------------------------------

                    try {

                        style.removeStyleLayer(
                                REPORT_LAYER_ID
                        );

                    } catch (Exception ignored) {
                    }

                    // -----------------------------------------
                    // USUŃ STARE ŹRÓDŁO
                    // -----------------------------------------

                    try {

                        style.removeStyleSource(
                                REPORT_SOURCE_ID
                        );

                    } catch (Exception ignored) {
                    }

                    // -----------------------------------------
                    // BRAK ZGŁOSZEŃ
                    // -----------------------------------------

                    if (reports.isEmpty()) {
                        return;
                    }

                    // -----------------------------------------
                    // GEOJSON FEATURES
                    // -----------------------------------------

                    StringBuilder features =
                            new StringBuilder();

                    features.append("[");

                    for (int i = 0;
                         i < reports.size();
                         i++) {

                        Report report =
                                reports.get(i);

                        if (i > 0) {
                            features.append(",");
                        }

                        features.append("{");

                        features.append(
                                "\"type\":\"Feature\","
                        );

                        features.append(
                                "\"properties\":{"
                        );

                        features.append(
                                "\"id\":\""
                        );

                        features.append(
                                escapeJson(
                                        report.id
                                )
                        );

                        features.append(
                                "\","
                        );

                        features.append(
                                "\"category\":\""
                        );

                        features.append(
                                escapeJson(
                                        report.category
                                )
                        );

                        features.append(
                                "\","
                        );

                        features.append(
                                "\"created_at\":\""
                        );

                        features.append(
                                escapeJson(
                                        report.createdAt
                                )
                        );

                        features.append(
                                "\""
                        );

                        features.append(
                                "},"
                        );

                        features.append(
                                "\"geometry\":{"
                        );

                        features.append(
                                "\"type\":\"Point\","
                        );

                        features.append(
                                "\"coordinates\":["
                        );

                        features.append(
                                report.longitude
                        );

                        features.append(",");
                        features.append(
                                report.latitude
                        );

                        features.append(
                                "]"
                        );

                        features.append(
                                "}"
                        );

                        features.append(
                                "}"
                        );
                    }

                    features.append("]");

                    // -----------------------------------------
                    // SOURCE
                    // -----------------------------------------

                    String sourceJson =
                            "{"
                                    + "\"type\":\"geojson\","
                                    + "\"data\":{"
                                    + "\"type\":\"FeatureCollection\","
                                    + "\"features\":"
                                    + features
                                    + "}"
                                    + "}";

                    Expected<String, Value>
                            sourceExpected =
                            Value.fromJson(
                                    sourceJson
                            );

                    if (sourceExpected.isError()) {

                        Toast.makeText(
                                requireContext(),
                                "Błąd tworzenia zgłoszenia.",
                                Toast.LENGTH_SHORT
                        ).show();

                        return;
                    }

                    style.addStyleSource(
                            REPORT_SOURCE_ID,
                            sourceExpected.getValue()
                    );

                    // -----------------------------------------
                    // RED CIRCLE
                    // -----------------------------------------

                    String layerJson =
                            "{"
                                    + "\"id\":\""
                                    + REPORT_LAYER_ID
                                    + "\","
                                    + "\"type\":\"circle\","
                                    + "\"source\":\""
                                    + REPORT_SOURCE_ID
                                    + "\","
                                    + "\"paint\":{"
                                    + "\"circle-radius\":12,"
                                    + "\"circle-color\":\"#E53935\","
                                    + "\"circle-opacity\":1,"
                                    + "\"circle-stroke-color\":\"#FFFFFF\","
                                    + "\"circle-stroke-width\":3"
                                    + "}"
                                    + "}";

                    Expected<String, Value>
                            layerExpected =
                            Value.fromJson(
                                    layerJson
                            );

                    if (layerExpected.isError()) {

                        Toast.makeText(
                                requireContext(),
                                "Błąd tworzenia markera.",
                                Toast.LENGTH_SHORT
                        ).show();

                        return;
                    }

                    // null = dodaj na wierzchu stylu
                    style.addStyleLayer(
                            layerExpected.getValue(),
                            null
                    );

                    style.setStyleLayerProperty(
                            REPORT_LAYER_ID,
                            "visibility",
                            Value.valueOf(
                                    userReportsLayerEnabled
                                            ? "visible"
                                            : "none"
                            )
                    );
                }
        );
    }

    // =========================================================
    // CLICK W CZERWONY MARKER
    // =========================================================

    private void showReportInfo(
            Report report
    ) {

        if (reportInfoPanel == null || report == null) {
            return;
        }

        selectedReportForFeedback = report;

        reportInfoCategory.setText("Kategoria: " + getCategoryPolishName(report.category));

        reportInfoTime.setText(
                "Godzina: " + report.createdAt
        );

        reportInfoId.setText(
                "ID: " + report.id
        );

        reportInfoConfirmations.setText(
                "👥 Potwierdzone przez "
                        + report.confirmations
                        + " osoby"
        );

        String reaction = reportPreferences().getString(reactionKey(report.id), null);
        reportInfoConfirm.setText("like".equals(reaction) ? "✓" : "👍");
        reportInfoInvalid.setText("dislike".equals(reaction) ? "✓" : "👎");
        boolean canReact = reaction == null
                && !(isLocallyExpired(report) && report.confirmations <= 0);
        reportInfoConfirm.setEnabled(canReact);
        reportInfoInvalid.setEnabled(canReact);

        reportInfoPanel.setVisibility(
                View.VISIBLE
        );
    }

    // =========================================================
    // UKRYJ PANEL
    // =========================================================

    private void hideReportInfo() {

        if (reportInfoPanel != null) {

            reportInfoPanel.setVisibility(
                    View.GONE
            );
        }
    }

    // =========================================================
    // ESCAPE JSON
    // =========================================================

    private String escapeJson(
            String text
    ) {

        if (text == null) {
            return "";
        }

        return text
                .replace(
                        "\\",
                        "\\\\"
                )
                .replace(
                        "\"",
                        "\\\""
                )
                .replace(
                        "\n",
                        "\\n"
                )
                .replace(
                        "\r",
                        "\\r"
                );
    }

    // =========================================================
    // TRASA BEZPIECZNA
    // =========================================================

    private void drawSafeRoute() {
        displayRoute(currentRouteResponse == null ? null : currentRouteResponse.safest,
                "🛡 Wybrano najlepszą trasę", "🛡 Wynik wg ustawionej wagi");
    }

    // =========================================================
    // TRASA SZYBKA
    // =========================================================

    private void drawFastRoute() {
        displayRoute(currentRouteResponse == null ? null : currentRouteResponse.fastest,
                "⚡ Wybrano trasę szybką", "🛡 Poziom bezpieczeństwa: Średni");
    }

    // =========================================================
    // TRASA ZBALANSOWANA
    // =========================================================

    private void drawBalancedRoute() {
        RouteResponse.RouteOption balanced = null;
        if (currentRouteResponse != null
                && currentRouteResponse.alternatives != null
                && !currentRouteResponse.alternatives.isEmpty()) {
            balanced = currentRouteResponse.alternatives.get(0);
        }
        if (balanced == null && currentRouteResponse != null) {
            balanced = currentRouteResponse.safest;
        }
        displayRoute(balanced, "⚖ Wybrano alternatywną trasę",
                "🛡 Alternatywny wariant");
    }

    private void geocodeAndCreateRoute(String destination) {
        if (geocoderExecutor == null || currentLocation == null) {
            Toast.makeText(requireContext(),
                    "Nie można teraz wyszukać trasy.",
                    Toast.LENGTH_SHORT).show();
            return;
        }
        int searchGeneration = ++routeSearchGeneration;
        if (routeCall != null) {
            routeCall.cancel();
        }
        currentRouteResponse = null;
        selectedRoute = null;
        selectedRouteName = null;
        startNavigationButton.setVisibility(View.GONE);
        destinationLocation = null;
        routeDetails.setText("Wyszukiwanie miejsca…");
        safetyStatus.setText("");

        Point start = currentLocation;
        Context context = requireContext().getApplicationContext();
        geocoderExecutor.execute(() -> {
            if (!Geocoder.isPresent()) {
                mainHandler.post(() -> {
                    if (isAdded() && searchGeneration == routeSearchGeneration) {
                        routeDetails.setText("Wyszukiwanie miejsc niedostępne.");
                        Toast.makeText(requireContext(),
                                "Na tym urządzeniu geokodowanie jest niedostępne.",
                                Toast.LENGTH_LONG).show();
                    }
                });
                return;
            }
            Geocoder geocoder = new Geocoder(context, Locale.getDefault());
            List<Address> addresses;
            try {
                addresses = geocoder.getFromLocationName(destination, 1);
            } catch (IOException exception) {
                mainHandler.post(() -> {
                    if (isAdded() && searchGeneration == routeSearchGeneration) {
                        routeDetails.setText("Nie udało się wyszukać miejsca.");
                        Toast.makeText(requireContext(),
                                "Błąd geokodowania: " + exception.getMessage(),
                                Toast.LENGTH_LONG).show();
                    }
                });
                return;
            }

            if (addresses == null || addresses.isEmpty()
                    || !addresses.get(0).hasLatitude()
                    || !addresses.get(0).hasLongitude()) {
                mainHandler.post(() -> {
                    if (isAdded() && searchGeneration == routeSearchGeneration) {
                        routeDetails.setText("Nie znaleziono tego miejsca.");
                        Toast.makeText(requireContext(),
                                "Nie znaleziono miejsca docelowego.",
                                Toast.LENGTH_SHORT).show();
                    }
                });
                return;
            }

            Address address = addresses.get(0);
            Point end = Point.fromLngLat(address.getLongitude(), address.getLatitude());
            mainHandler.post(() -> {
                if (isAdded() && searchGeneration == routeSearchGeneration) {
                    destinationLocation = end;
                    requestRoute(start, end, searchGeneration);
                }
            });
        });
    }

    private void requestRoute(Point start, Point end, int searchGeneration) {
        routeDetails.setText("Wyznaczanie trasy… może potrwać do 90 sekund.");
        System.out.println(
                "Route request: start lat=" + start.latitude()
                        + ", lon=" + start.longitude()
                        + "; end lat=" + end.latitude()
                        + ", lon=" + end.longitude()
        );
        routeCall = RetrofitClient.getApiService().createRoute(
                new RouteRequest(start.latitude(), start.longitude(),
                        end.latitude(), end.longitude()));
        routeCall.enqueue(new Callback<RouteResponse>() {
            @Override
            public void onResponse(Call<RouteResponse> call,
                                   Response<RouteResponse> response) {
                if (!isAdded() || call.isCanceled()
                        || searchGeneration != routeSearchGeneration) {
                    return;
                }
                if (!response.isSuccessful() || response.body() == null) {
                    routeDetails.setText("Nie udało się wyznaczyć trasy.");
                    Toast.makeText(requireContext(),
                            "Błąd API trasy: " + response.code(),
                            Toast.LENGTH_LONG).show();
                    return;
                }
                currentRouteResponse = response.body();
                if (currentRouteResponse.safest == null) {
                    routeDetails.setText("Backend nie zwrócił bezpiecznej trasy.");
                    return;
                }
                drawSafeRoute();
            }

            @Override
            public void onFailure(Call<RouteResponse> call, Throwable throwable) {
                if (!isAdded() || call.isCanceled()
                        || searchGeneration != routeSearchGeneration) {
                    return;
                }
                if (throwable instanceof SocketTimeoutException) {
                    routeDetails.setText("Backend nie wyznaczył trasy w ciągu 90 sekund.");
                    Toast.makeText(requireContext(),
                            "Wyznaczanie trasy trwało zbyt długo. Spróbuj ponownie.",
                            Toast.LENGTH_LONG).show();
                } else {
                    routeDetails.setText("Nie udało się połączyć z backendem.");
                    Toast.makeText(requireContext(),
                            "Błąd połączenia z API trasy: " + throwable.getMessage(),
                            Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private void displayRoute(RouteResponse.RouteOption route,
                             String selectedRouteText, String safetyText) {
        if (route == null || route.geometry == null || route.geometry.coordinates == null) {
            if (isAdded()) {
                Toast.makeText(requireContext(),
                        "Backend nie zwrócił wybranej trasy.",
                        Toast.LENGTH_SHORT).show();
            }
            return;
        }
        List<Point> points = new ArrayList<>();
        for (List<Double> coordinate : route.geometry.coordinates) {
            if (coordinate != null && coordinate.size() >= 2
                    && coordinate.get(0) != null && coordinate.get(1) != null) {
                points.add(Point.fromLngLat(coordinate.get(0), coordinate.get(1)));
            }
        }
        if (points.size() < 2) {
            routeDetails.setText("Backend zwrócił nieprawidłową geometrię trasy.");
            return;
        }
        selectedRoute = route;
        selectedRouteName = selectedRouteText;
        startNavigationButton.setVisibility(View.VISIBLE);
        drawRoute(points);
        moveCameraToRoute(points);
        routeDetails.setText(String.format(Locale.getDefault(),
                "%s • %.1f km • %d min • bezpieczeństwo %.0f%%",
                selectedRouteText, route.distance_m / 1000.0,
                Math.round(route.duration_s / 60.0), route.safety_score));
        safetyStatus.setText(String.format(Locale.getDefault(),
                "%s • bezpieczeństwo %.0f%%",
                safetyText, route.safety_score));
        if (navigationRouteSummary != null) {
            navigationRouteSummary.setText(String.format(Locale.getDefault(),
                    "%s • %.1f km • %d min",
                    selectedRouteText, route.distance_m / 1000.0,
                    Math.round(route.duration_s / 60.0)));
        }
    }

    private void startNavigationForSelectedRoute() {
        if (currentLocation == null) {
            Toast.makeText(requireContext(),
                    "Czekam na Twoją lokalizację GPS.",
                    Toast.LENGTH_SHORT).show();
            return;
        }
        if (selectedRoute == null || selectedRoute.geometry == null
                || selectedRoute.geometry.coordinates == null) {
            Toast.makeText(requireContext(),
                    "Najpierw wyznacz trasę.",
                    Toast.LENGTH_SHORT).show();
            return;
        }

        List<Point> routePoints = new ArrayList<>();
        for (List<Double> coordinate : selectedRoute.geometry.coordinates) {
            if (coordinate != null && coordinate.size() >= 2
                    && coordinate.get(0) != null && coordinate.get(1) != null) {
                routePoints.add(Point.fromLngLat(coordinate.get(0), coordinate.get(1)));
            }
        }
        if (routePoints.size() < 2) {
            Toast.makeText(requireContext(),
                    "Wybrana trasa nie zawiera poprawnej geometrii.",
                    Toast.LENGTH_SHORT).show();
            return;
        }

        List<NavigationStep> steps = buildNavigationSteps(selectedRoute, routePoints);
        if (steps.isEmpty()) {
            Toast.makeText(requireContext(),
                    "Nie udało się przygotować wskazówek dla tej trasy.",
                    Toast.LENGTH_SHORT).show();
            return;
        }

        currentNavigationStepIndex = 0;
        isNavigating = true;
        navigationVibrationTriggered = false;
        showNavigationSteps(steps);
        startNavigationButton.setVisibility(View.GONE);
        routeInfoPanel.setVisibility(View.GONE);
        routeOptionsPanel.setVisibility(View.GONE);
        updateNavigationSummary(
                selectedRouteName == null ? "Trasa" : selectedRouteName,
                selectedRoute.distance_m / 1000.0,
                (int) Math.round(selectedRoute.duration_s / 60.0)
        );

        if (anomalyDetector != null) {
            anomalyDetector.setNavigationActive(true);
        }
        if (locationComponent != null) {
            locationComponent.updateSettings(settings -> {
                settings.setEnabled(true);
                settings.setPulsingEnabled(false);
                return null;
            });
        }

        Point bearingTarget = steps.get(0).maneuverPoint;
        if (bearingTarget == null
                || distanceBetweenPoints(currentLocation, bearingTarget) < 2.0) {
            bearingTarget = routePoints.get(1);
        }
        mapView.getMapboxMap().setCamera(
                new CameraOptions.Builder()
                        .center(currentLocation)
                        .zoom(18.0)
                        .pitch(60.0)
                        .bearing(calculateBearing(currentLocation, bearingTarget))
                        .build()
        );
        updateNavigationProgress(currentLocation);
    }

    private List<NavigationStep> buildNavigationSteps(
            RouteResponse.RouteOption route,
            List<Point> points
    ) {
        List<NavigationStep> apiSteps = buildApiNavigationSteps(route);
        if (!apiSteps.isEmpty()) {
            return apiSteps;
        }
        return buildGeometryNavigationSteps(points);
    }

    private List<NavigationStep> buildApiNavigationSteps(
            RouteResponse.RouteOption route
    ) {
        List<NavigationStep> steps = new ArrayList<>();
        if (route == null || route.navigation_steps == null) {
            return steps;
        }
        for (RouteResponse.NavigationStep step : route.navigation_steps) {
            if (step == null || step.instruction == null
                    || step.instruction.trim().isEmpty()
                    || step.location == null
                    || !Double.isFinite(step.location.lat)
                    || !Double.isFinite(step.location.lon)
                    || step.location.lat < -90.0 || step.location.lat > 90.0
                    || step.location.lon < -180.0 || step.location.lon > 180.0) {
                continue;
            }
            steps.add(new NavigationStep(
                    step.instruction,
                    (int) Math.round(Math.max(0.0, step.distance_m)),
                    normalizeManeuver(step.maneuver),
                    Point.fromLngLat(step.location.lon, step.location.lat)
            ));
        }
        return steps;
    }

    private String normalizeManeuver(String maneuver) {
        if (maneuver == null) {
            return "straight";
        }
        switch (maneuver.toLowerCase(Locale.ROOT)) {
            case "left":
                return "left";
            case "right":
                return "right";
            case "uturn":
                return "uturn";
            case "roundabout":
                return "roundabout";
            case "finish":
            case "arrive":
                return "finish";
            default:
                return "straight";
        }
    }

    private List<NavigationStep> buildGeometryNavigationSteps(List<Point> points) {
        List<NavigationStep> steps = new ArrayList<>();
        if (points == null || points.size() < 2) {
            return steps;
        }

        double distanceSincePreviousStep = 0.0;
        double totalDistance = 0.0;
        double previousStepDistance = 0.0;

        for (int i = 1; i < points.size(); i++) {
            double segmentDistance = distanceBetweenPoints(points.get(i - 1), points.get(i));
            totalDistance += segmentDistance;
            distanceSincePreviousStep += segmentDistance;

            if (i >= points.size() - 1) {
                continue;
            }

            double incomingBearing = calculateBearing(points.get(i - 1), points.get(i));
            double outgoingBearing = calculateBearing(points.get(i), points.get(i + 1));
            double turn = normalizeTurn(outgoingBearing - incomingBearing);
            double absoluteTurn = Math.abs(turn);

            if (absoluteTurn < 35.0) {
                continue;
            }

            String maneuver;
            String instruction;
            if (absoluteTurn >= 150.0) {
                maneuver = "uturn";
                instruction = "Zawróć";
            } else if (turn > 0.0) {
                maneuver = "right";
                instruction = "Skręć w prawo";
            } else {
                maneuver = "left";
                instruction = "Skręć w lewo";
            }

            steps.add(new NavigationStep(
                    instruction,
                    (int) Math.round(distanceSincePreviousStep),
                    maneuver,
                    points.get(i)
            ));
            previousStepDistance = totalDistance;
            distanceSincePreviousStep = 0.0;
        }

        Point destination = points.get(points.size() - 1);
        steps.add(new NavigationStep(
                "Dojdź do celu",
                (int) Math.round(Math.max(0.0, totalDistance - previousStepDistance)),
                "finish",
                destination
        ));
        return steps;
    }

    private double normalizeTurn(double degrees) {
        while (degrees > 180.0) {
            degrees -= 360.0;
        }
        while (degrees < -180.0) {
            degrees += 360.0;
        }
        return degrees;
    }

    // =========================================================
    // RYSOWANIE TRASY
    // =========================================================

    private void drawRoute(
            List<Point> points
    ) {

        if (mapView == null) {
            return;
        }

        LineString lineString =
                LineString.fromLngLats(
                        points
                );

        String sourceJson =
                "{"
                        + "\"type\":\"geojson\","
                        + "\"data\":"
                        + lineString.toJson()
                        + "}";

        String layerJson =
                "{"
                        + "\"id\":\""
                        + ROUTE_LAYER_ID
                        + "\","
                        + "\"type\":\"line\","
                        + "\"source\":\""
                        + ROUTE_SOURCE_ID
                        + "\","
                        + "\"paint\":{"
                        + "\"line-color\":\"#1976D2\","
                        + "\"line-width\":6"
                        + "}"
                        + "}";

        mapView.getMapboxMap().getStyle(
                style -> {

                    try {

                        style.removeStyleLayer(
                                ROUTE_LAYER_ID
                        );

                    } catch (Exception ignored) {
                    }

                    try {

                        style.removeStyleSource(
                                ROUTE_SOURCE_ID
                        );

                    } catch (Exception ignored) {
                    }

                    Expected<String, Value>
                            sourceExpected =
                            Value.fromJson(
                                    sourceJson
                            );

                    if (sourceExpected.isError()) {
                        return;
                    }

                    style.addStyleSource(
                            ROUTE_SOURCE_ID,
                            sourceExpected.getValue()
                    );

                    Expected<String, Value>
                            layerExpected =
                            Value.fromJson(
                                    layerJson
                            );

                    if (layerExpected.isError()) {
                        return;
                    }

                    style.addStyleLayer(
                            layerExpected.getValue(),
                            null
                    );
                }
        );
    }

    // =========================================================
    // KAMERA NA TRASĘ
    // =========================================================

    private void moveCameraToRoute(List<Point> points) {
        if (points == null || points.isEmpty() || mapView == null) {
            return;
        }

        // Jeśli jesteśmy w trybie nawigacji (3D), NIE zmieniaj kąta na 0
        if (isNavigating) {
            if (currentLocation != null) {
                // Pobierz aktualny kąt obrotu kompasu z mapy, żeby kamera nie "szarpała"
                double currentBearing = mapView.getMapboxMap().getCameraState().getBearing();
                
                mapView.getMapboxMap().setCamera(
                        new CameraOptions.Builder()
                                .center(currentLocation)
                                .zoom(18.0)
                                .pitch(60.0) 
                                .bearing(currentBearing) // <- Utrzymujemy bieżący kierunek patrzenia!
                                .build() 
                );
            }
            return;
        }

        // Zwykły podgląd mapy z góry (2D)
        Point first = points.get(0);
        Point last = points.get(points.size() - 1);
        double centerLng = (first.longitude() + last.longitude()) / 2.0;
        double centerLat = (first.latitude() + last.latitude()) / 2.0;

        mapView.getMapboxMap().setCamera(
                new CameraOptions.Builder()
                        .center(Point.fromLngLat(centerLng, centerLat))
                        .zoom(13.0)
                        .pitch(0.0)
                        .bearing(0.0)
                        .build()
        );
    }

    // =========================================================
    // GPS
    // =========================================================

    private void enableLocation() {

        if (mapView == null
                || locationComponent == null) {
            return;
        }

        if (ActivityCompat.checkSelfPermission(
                requireContext(),
                Manifest.permission.ACCESS_FINE_LOCATION
        ) != PackageManager.PERMISSION_GRANTED
                && ActivityCompat.checkSelfPermission(
                requireContext(),
                Manifest.permission.ACCESS_COARSE_LOCATION
        ) != PackageManager.PERMISSION_GRANTED) {

            return;
        }

        locationComponent.updateSettings(
                settings -> {
                    settings.setEnabled(true);
                    
                    // Zmuszamy kropkę do obracania się z kompasem telefonu
                    settings.setPuckBearingEnabled(true);

                    // Ładujemy wbudowane w Mapboxa ikony ze strzałką kierunkową (cone)
                    LocationPuck2D puck = new LocationPuck2D();
                    puck.setBearingImage(ImageHolder.from(com.mapbox.maps.R.drawable.mapbox_user_bearing_icon));
                    puck.setShadowImage(ImageHolder.from(com.mapbox.maps.R.drawable.mapbox_user_icon_shadow));
                    puck.setTopImage(ImageHolder.from(com.mapbox.maps.R.drawable.mapbox_user_puck_icon));
                    
                    // NOWE: Skalujemy wskaźnik do bardziej proporcjonalnych rozmiarów (np. 35% oryginalnego rozmiaru)
                    // Wartość podana w postaci JSON-owej tablicy (wymagane przez Mapbox API)
                    puck.setScaleExpression("[\"interpolate\", [\"linear\"], [\"zoom\"], 10, 0.35, 20, 0.6]");
                    
                    settings.setLocationPuck(puck);

                    return null;
                }
        );

        if (!locationListenerAdded) {

            // Nasłuchiwanie zmiany lokalizacji
            locationComponent
                    .addOnIndicatorPositionChangedListener(
                            onIndicatorPositionChangedListener
                    );
            
            // NOWE: Nasłuchiwanie zmiany obrotu (kompas)
            locationComponent
                    .addOnIndicatorBearingChangedListener(
                            onIndicatorBearingChangedListener
                    );

            locationListenerAdded = true;
        }
    }

    // =========================================================
    // PERMISSION
    // =========================================================

    private void requestLocationPermission() {

        requestPermissions(
                new String[]{
                        Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION
                },
                LOCATION_PERMISSION_REQUEST_CODE
        );
    }

    // =========================================================
    // PERMISSION RESULT
    // =========================================================

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            @NonNull String[] permissions,
            @NonNull int[] grantResults
    ) {

        super.onRequestPermissionsResult(
                requestCode,
                permissions,
                grantResults
        );

        if (requestCode ==
                LOCATION_PERMISSION_REQUEST_CODE) {

            boolean granted = false;

            for (int result : grantResults) {

                if (result ==
                        PackageManager.PERMISSION_GRANTED) {

                    granted = true;

                    break;
                }
            }

            if (granted) {

                firstLocationReceived = false;

                enableLocation();

            } else {

                Toast.makeText(
                        requireContext(),
                        "Brak dostępu do lokalizacji.",
                        Toast.LENGTH_SHORT
                ).show();
            }
        }
    }

    // =========================================================
    // START
    // =========================================================

    @Override
    public void onStart() {

        super.onStart();

        if (mapView != null) {
            mapView.onStart();

            if (ActivityCompat.checkSelfPermission(
                    requireContext(),
                    Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
                    || ActivityCompat.checkSelfPermission(
                    requireContext(),
                    Manifest.permission.ACCESS_COARSE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED) {
                enableLocation();
            }
        }
    }

    // =========================================================
    // STOP
    // =========================================================

    @Override
    public void onStop() {

        if (locationComponent != null
                && locationListenerAdded) {

            // Zatrzymanie GPS
            locationComponent
                    .removeOnIndicatorPositionChangedListener(
                            onIndicatorPositionChangedListener
                    );
            
            // NOWE: Zatrzymanie kompasu
            locationComponent
                    .removeOnIndicatorBearingChangedListener(
                            onIndicatorBearingChangedListener
                    );

            locationListenerAdded = false;
        }

        if (gesturesPlugin != null) {

            gesturesPlugin
                    .removeOnMapClickListener(
                            onMapClickListener
                    );
        }

        if (mapView != null) {
            mapView.onStop();
        }

        super.onStop();
    }

    // =========================================================
    // LOW MEMORY
    // =========================================================

    @Override
    public void onLowMemory() {

        super.onLowMemory();

        if (mapView != null) {
            mapView.onLowMemory();
        }
    }

    // =========================================================
    // DESTROY
    // =========================================================

    @Override
    public void onDestroyView() {
        routeSearchGeneration++;
        mainHandler.removeCallbacks(reportExpiryCleanup);

        if (locationComponent != null
                && locationListenerAdded) {

            // Zatrzymanie GPS
            locationComponent
                    .removeOnIndicatorPositionChangedListener(
                            onIndicatorPositionChangedListener
                    );
            
            // NOWE: Zatrzymanie kompasu
            locationComponent
                    .removeOnIndicatorBearingChangedListener(
                            onIndicatorBearingChangedListener
                    );

            locationListenerAdded = false;
        }

        if (gesturesPlugin != null) {

            gesturesPlugin
                    .removeOnMapClickListener(
                            onMapClickListener
                    );
        }

        if (mapView != null) {
            mapView.onDestroy();
        }

        if (routeCall != null) {
            routeCall.cancel();
            routeCall = null;
        }
        if (geocoderExecutor != null) {
            geocoderExecutor.shutdownNow();
            geocoderExecutor = null;
        }

        locationComponent = null;

        gesturesPlugin = null;

        mapView = null;

        super.onDestroyView();
    }

    private void showNavigationSteps(
            List<NavigationStep> steps
    ) {

        if (isNavigating) {
            routeOptionsPanel.setVisibility(View.GONE);
            routeInfoPanel.setVisibility(View.GONE);
            startNavigationButton.setVisibility(View.GONE);
        }

        currentNavigationSteps.clear();

        if (steps == null || steps.isEmpty()) {

            navigationStepsPanel.setVisibility(
                    View.GONE
            );

            return;
        }

        currentNavigationSteps.addAll(steps);

        navigationExpanded = false;

        navigationStepsPanel.setVisibility(
                View.VISIBLE
        );

        updateNavigationPanel();
    }

    private String getNavigationIcon(String maneuver) {

        if (maneuver == null) {
            return "↑";
        }

        switch (maneuver) {

            case "right":
                return "→";

            case "left":
                return "←";

            case "uturn":
                return "↶";

            case "crosswalk":
                return "🚶";

            case "finish":
                return "🏁";

            case "straight":
            default:
                return "↑";
        }
    }

    private String formatNavigationDistance(int meters) {

        if (meters < 1000) {
            return "za " + meters + " m";
        }

        double kilometers = meters / 1000.0;

        if (kilometers == Math.floor(kilometers)) {
            return "za " + (int) kilometers + " km";
        }

        return String.format(
                java.util.Locale.US,
                "za %.1f km",
                kilometers
        );
    }

    private void showDemoNavigationSteps() {

        if (currentLocation == null) {
            return;
        }

        double startLng =
                currentLocation.longitude();

        double startLat =
                currentLocation.latitude();

        // ============================================
        // TESTOWE PUNKTY MANEWRÓW
        // ============================================

        // Około 15–20 metrów od aktualnej pozycji
        Point rightTurn =
                Point.fromLngLat(
                        startLng + 0.00015,
                        startLat
                );

        // Około 40–50 metrów dalej
        Point leftTurn =
                Point.fromLngLat(
                        startLng + 0.00040,
                        startLat + 0.00020
                );

        // Jeszcze dalej
        Point uTurn =
                Point.fromLngLat(
                        startLng + 0.00070,
                        startLat + 0.00040
                );

        List<NavigationStep> steps =
                new ArrayList<>();

        steps.add(
                new NavigationStep(
                        "Skręć w prawo",
                        20,
                        "right",
                        rightTurn
                )
        );

        steps.add(
                new NavigationStep(
                        "Idź prosto",
                        80,
                        "straight",
                        null
                )
        );

        steps.add(
                new NavigationStep(
                        "Skręć w lewo",
                        350,
                        "left",
                        leftTurn
                )
        );

        steps.add(
                new NavigationStep(
                        "Zawróć",
                        200,
                        "uturn",
                        uTurn
                )
        );

        currentNavigationStepIndex = 0;

        isNavigating = true;

        routeInfoPanel.setVisibility(View.GONE);
        routeOptionsPanel.setVisibility(View.GONE);
        startNavigationButton.setVisibility(View.GONE);

        navigationVibrationTriggered = false;

        showNavigationSteps(steps);

        updateNavigationSummary(
                "🛡 Bezpieczna",
                2.4,
                9
        );

        // Od razu sprawdź odległość od pierwszego manewru
        updateNavigationProgress(currentLocation);

        // WŁĄCZAMY DETEKCJĘ ZAGROŻEŃ TYLKO NA TRASIE
        if (anomalyDetector != null) {
            anomalyDetector.setNavigationActive(true);
        }

        // AKTYWACJA TRYBU NAWIGACJI 3D (JAK GOOGLE MAPS)
        if (locationComponent != null) {
            locationComponent.updateSettings(settings -> {
                settings.setEnabled(true);
                settings.setPulsingEnabled(false); // wyłączamy pulsowanie z trybu spoczynku
                return null;
            });
            
            // NOWE: Obliczamy idealny kąt początkowy (kierunek do pierwszego manewru)
            double routeBearing = calculateBearing(currentLocation, steps.get(0).maneuverPoint);
            
            mapView.getMapboxMap().setCamera(
                    new CameraOptions.Builder()
                            .center(currentLocation)
                            .zoom(18.0) 
                            .pitch(60.0) 
                            .bearing(routeBearing) // Startujemy skierowani idealnie wzdłuż trasy!
                            .build()
            );
        }
    }

    private void exitNavigationMode() {
        if (!isNavigating) return;
        isNavigating = false;
        
        navigationStepsPanel.setVisibility(View.GONE);
        routeInfoPanel.setVisibility(View.VISIBLE);
        routeOptionsPanel.setVisibility(View.VISIBLE);
        if (selectedRoute != null) {
            startNavigationButton.setVisibility(View.VISIBLE);
        }
        
        if (anomalyDetector != null) {
            anomalyDetector.setNavigationActive(false);
        }
        
        // Wracamy do widoku 2D (płasko) patrząc na północ
        if (currentLocation != null) {
            mapView.getMapboxMap().setCamera(
                    new CameraOptions.Builder()
                            .center(currentLocation)
                            .zoom(14.0)
                            .pitch(0.0) // Płasko
                            .bearing(0.0) // Północ u góry
                            .build()
            );
        }
    }

    private void updateNavigationPanel() {

        if (currentNavigationSteps.isEmpty()) {

            navigationStepsPanel.setVisibility(
                    View.GONE
            );

            return;
        }

        if (currentNavigationStepIndex >=
                currentNavigationSteps.size()) {

            return;
        }

        NavigationStep currentStep =
                currentNavigationSteps.get(
                        currentNavigationStepIndex
                );

        navigationCurrentIcon.setText(
                getNavigationIcon(
                        currentStep.maneuver
                )
        );

        navigationCurrentInstruction.setText(
                currentStep.instruction
        );

        navigationCurrentDistance.setText(
                formatNavigationDistance(
                        currentStep.distanceMeters
                )
        );

        if (navigationExpanded) {

            navigationAllSteps.setVisibility(
                    View.VISIBLE
            );

            navigationExpandIcon.setText("⌃");

            buildNavigationList();

        } else {

            navigationAllSteps.setVisibility(
                    View.GONE
            );

            navigationExpandIcon.setText("⌄");
        }
    }

    private void buildNavigationList() {

        navigationAllSteps.removeAllViews();

        if (currentNavigationSteps.size() <= 1) {
            return;
        }

        for (int i = 1;
             i < currentNavigationSteps.size();
             i++) {

            NavigationStep step =
                    currentNavigationSteps.get(i);

            LinearLayout row =
                    new LinearLayout(requireContext());

            row.setLayoutParams(
                    new LinearLayout.LayoutParams(
                            LinearLayout.LayoutParams.MATCH_PARENT,
                            62
                    )
            );

            row.setOrientation(
                    LinearLayout.HORIZONTAL
            );

            row.setGravity(
                    android.view.Gravity.CENTER_VERTICAL
            );

            row.setPadding(
                    14,
                    4,
                    14,
                    4
            );

            TextView icon =
                    new TextView(requireContext());

            icon.setLayoutParams(
                    new LinearLayout.LayoutParams(
                            46,
                            46
                    )
            );

            icon.setGravity(
                    android.view.Gravity.CENTER
            );

            icon.setTextSize(26);

            icon.setText(
                    getNavigationIcon(
                            step.maneuver
                    )
            );

            LinearLayout textContainer =
                    new LinearLayout(
                            requireContext()
                    );

            textContainer.setLayoutParams(
                    new LinearLayout.LayoutParams(
                            0,
                            LinearLayout.LayoutParams.WRAP_CONTENT,
                            1
                    )
            );

            textContainer.setOrientation(
                    LinearLayout.VERTICAL
            );

            textContainer.setPadding(
                    10,
                    0,
                    0,
                    0
            );

            TextView instruction =
                    new TextView(requireContext());

            instruction.setText(
                    step.instruction
            );

            instruction.setTextSize(15);

            instruction.setTypeface(
                    null,
                    android.graphics.Typeface.BOLD
            );

            TextView distance =
                    new TextView(requireContext());

            distance.setText(
                    formatNavigationDistance(
                            step.distanceMeters
                    )
            );

            distance.setTextSize(13);

            textContainer.addView(
                    instruction
            );

            textContainer.addView(
                    distance
            );

            row.addView(icon);
            row.addView(textContainer);

            navigationAllSteps.addView(row);

            if (i < currentNavigationSteps.size() - 1) {

                View separator =
                        new View(requireContext());

                separator.setLayoutParams(
                        new LinearLayout.LayoutParams(
                                LinearLayout.LayoutParams.MATCH_PARENT,
                                1
                        )
                );

                separator.setBackgroundColor(
                        android.graphics.Color.parseColor("#4e1c51")
                );

                navigationAllSteps.addView(
                        separator
                );
            }
        }
    }

    private void updateNavigationSummary(
            String routeType,
            double remainingKm,
            int remainingMinutes
    ) {

        navigationRouteSummary.setText(
                routeType
                        + "  •  "
                        + String.format(
                        java.util.Locale.US,
                        "%.1f km",
                        remainingKm
                )
                        + "  •  "
                        + remainingMinutes
                        + " min"
        );
    }

    private void vibrateForManeuver(String maneuver) {

        Vibrator vibrator =
                (Vibrator) requireContext()
                        .getSystemService(
                                android.content.Context.VIBRATOR_SERVICE
                        );

        if (vibrator == null || !vibrator.hasVibrator()) {
            return;
        }

        long[] pattern;

        switch (maneuver) {

            case "right":
                pattern = new long[]{
                        0,
                        300
                };
                break;

            case "left":
                pattern = new long[]{
                        0,
                        300,
                        150,
                        300
                };
                break;

            case "uturn":
                pattern = new long[]{
                        0,
                        300,
                        150,
                        300,
                        150,
                        300
                };
                break;

            default:
                return;
        }

        if (android.os.Build.VERSION.SDK_INT >=
                android.os.Build.VERSION_CODES.O) {

            vibrator.vibrate(
                    VibrationEffect.createWaveform(
                            pattern,
                            -1
                    )
            );

        } else {

            vibrator.vibrate(pattern, -1);
        }
    }

    // =========================================================
    // OBLICZANIE KĄTA DO CELU (ŻEBY DROGA BYŁA NA GÓRZE)
    // =========================================================
    private double calculateBearing(Point start, Point end) {
        double lat1 = Math.toRadians(start.latitude());
        double lon1 = Math.toRadians(start.longitude());
        double lat2 = Math.toRadians(end.latitude());
        double lon2 = Math.toRadians(end.longitude());

        double dLon = lon2 - lon1;

        double y = Math.sin(dLon) * Math.cos(lat2);
        double x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);

        double bearing = Math.atan2(y, x);
        return (Math.toDegrees(bearing) + 360) % 360;
    }

    private double distanceBetweenPoints(
            Point first,
            Point second
    ) {

        double earthRadius = 6371000.0;

        double lat1 =
                Math.toRadians(first.latitude());

        double lat2 =
                Math.toRadians(second.latitude());

        double deltaLat =
                Math.toRadians(
                        second.latitude()
                                - first.latitude()
                );

        double deltaLng =
                Math.toRadians(
                        second.longitude()
                                - first.longitude()
                );

        double a =
                Math.sin(deltaLat / 2)
                        * Math.sin(deltaLat / 2)
                        +
                        Math.cos(lat1)
                                * Math.cos(lat2)
                                *
                                Math.sin(deltaLng / 2)
                                * Math.sin(deltaLng / 2);

        double c =
                2 * Math.atan2(
                        Math.sqrt(a),
                        Math.sqrt(1 - a)
                );

        return earthRadius * c;
    }

    private void updateNavigationProgress(
            Point userLocation
    ) {

        if (currentNavigationSteps.isEmpty()) {
            return;
        }

        if (userLocation == null) {
            return;
        }

        if (currentNavigationStepIndex >=
                currentNavigationSteps.size()) {

            return;
        }

        NavigationStep currentStep =
                currentNavigationSteps.get(
                        currentNavigationStepIndex
                );

        if (currentStep.maneuverPoint == null) {
            return;
        }

        double distance =
                distanceBetweenPoints(
                        userLocation,
                        currentStep.maneuverPoint
                );

        // Zaktualizuj tekst odległości
        navigationCurrentDistance.setText(
                "za "
                        + Math.round(distance)
                        + " m"
        );

        // Jesteśmy wystarczająco blisko manewru
        if (distance <= VIBRATION_DISTANCE_METERS
                && !navigationVibrationTriggered) {

            vibrateForManeuver(
                    currentStep.maneuver
            );

            navigationVibrationTriggered = true;

            moveToNextNavigationStep();
        }
    }

    private void moveToNextNavigationStep() {

        currentNavigationStepIndex++;

        navigationVibrationTriggered = false;

        if (currentNavigationStepIndex >=
                currentNavigationSteps.size()) {

            navigationCurrentIcon.setText("🏁");

            navigationCurrentInstruction.setText(
                    "Dotarłeś do celu"
            );

            // WYŁĄCZAMY DETEKCJĘ
            if (anomalyDetector != null) {
                anomalyDetector.setNavigationActive(false);
            }

            // POWRÓT DO PŁASKIEJ MAPY
            if (currentLocation != null) {
                mapView.getMapboxMap().setCamera(
                        new CameraOptions.Builder()
                                .center(currentLocation)
                                .zoom(15.0)
                                .pitch(0.0) // Płasko, z góry
                                .bearing(0.0) // Północ na górze
                                .build()
                );
            }

            navigationCurrentDistance.setText("");

            return;
        }

        NavigationStep nextStep =
                currentNavigationSteps.get(
                        currentNavigationStepIndex
                );

        navigationCurrentIcon.setText(
                getNavigationIcon(
                        nextStep.maneuver
                )
        );

        navigationCurrentInstruction.setText(
                nextStep.instruction
        );

        navigationCurrentDistance.setText(
                formatNavigationDistance(
                        nextStep.distanceMeters
                )
        );

        updateNavigationPanel();
    }

    private void setupLayerButton(
            Button button,
            String enabledText,
            String disabledText,
            Runnable onToggle
    ) {

        button.setTag(true);

        // Początkowo warstwa jest włączona
        updateLayerButtonAppearance(
                button,
                true,
                enabledText
        );

        button.setOnClickListener(v -> {

            boolean enabled =
                    button.getTag() == null
                            || (boolean) button.getTag();

            enabled = !enabled;

            button.setTag(enabled);

            updateLayerButtonAppearance(
                    button,
                    enabled,
                    enabled
                            ? enabledText
                            : disabledText
            );

            onToggle.run();
        });
    }

    private void updateReportLayerVisibility() {
        if (mapView == null) return;

        try {
            mapView.getMapboxMap().getStyle(style -> {

                style.setStyleLayerProperty(
                        REPORT_LAYER_ID,
                        "visibility",
                        Value.valueOf(
                                userReportsLayerEnabled
                                        ? "visible"
                                        : "none"
                        )
                );

            });

        } catch (Exception ignored) {
        }
    }
    private void updateLayerButtonAppearance(
            Button button,
            boolean enabled,
            String icon
    ) {

        button.setText(icon);

        if (enabled) {

            button.setBackgroundTintList(
                    android.content.res.ColorStateList.valueOf(
                            android.graphics.Color.parseColor("#4e1c51")
                    )
            );

            button.setTextColor(
                    android.graphics.Color.WHITE
            );

        } else {

            button.setBackgroundTintList(
                    android.content.res.ColorStateList.valueOf(
                            android.graphics.Color.rgb(
                                    224,
                                    224,
                                    224
                            )
                    )
            );

            button.setTextColor(
                    android.graphics.Color.rgb(
                            80,
                            80,
                            80
                    )
            );
        }
    }

    private Bitmap getCameraBitmap() {

        Drawable drawable =
                ContextCompat.getDrawable(
                        requireContext(),
                        R.drawable.ic_camera_map
                );

        if (drawable == null) {
            return null;
        }

        int width = 96;
        int height = 96;

        Bitmap bitmap =
                Bitmap.createBitmap(
                        width,
                        height,
                        Bitmap.Config.ARGB_8888
                );

        Canvas canvas =
                new Canvas(bitmap);

        drawable.setBounds(
                0,
                0,
                width,
                height
        );

        drawable.draw(canvas);

        return bitmap;
    }

    private void updateCameraMarkers(List<Camera> cameras) {

        if (mapView == null) {
            return;
        }

        // ============================================
        // POBIERZ ANNOTATION PLUGIN
        // ============================================

        AnnotationPlugin annotationPlugin =
                mapView.getPlugin(
                        Plugin.MAPBOX_ANNOTATION_PLUGIN_ID
                );

        if (annotationPlugin == null) {
            System.out.println("Brak Mapbox AnnotationPlugin dla kamer");
            return;
        }

        // ============================================
        // UTWÓRZ MANAGERA
        // ============================================

        if (cameraAnnotationManager == null) {

            cameraAnnotationManager =
                    (PointAnnotationManager)
                            annotationPlugin.createAnnotationManager(
                                    AnnotationType.PointAnnotation,
                                    new AnnotationConfig()
                            );

        } else {

            cameraAnnotationManager.deleteAll();
        }

        // ============================================
        // IKONA KAMERY
        // ============================================

        Bitmap cameraBitmap = getCameraBitmap();

        if (cameraBitmap == null) {
            System.out.println("Brak ikony kamer");
            return;
        }

        int renderedCameras = Math.min(cameras.size(), MAX_POINT_ANNOTATIONS);
        for (int i = 0; i < renderedCameras; i++) {
            Camera camera = cameras.get(i);
            PointAnnotationOptions options =
                    new PointAnnotationOptions()
                            .withPoint(
                                    Point.fromLngLat(
                                            camera.getLongitude(),
                                            camera.getLatitude()
                                    )
                            )
                            .withIconImage(cameraBitmap)
                            .withIconSize(1.0);

            cameraAnnotationManager.create(options);
        }

        // ============================================
        // WIDOCZNOŚĆ
        // ============================================

        updateCameraLayerVisibility();
    }

    private void updateCameraLayerVisibility() {

        if (cameraAnnotationManager == null) {
            return;
        }

        cameraAnnotationManager.setIconOpacity(
                camerasLayerEnabled ? 1.0 : 0.0
        );
    }

    private void updateStreetLampMarkers(List<StreetLamp> streetLamps) {

        if (mapView == null) {
            return;
        }

        StringBuilder features = new StringBuilder("[");
        int pointStep = Math.max(
                1,
                (streetLamps.size() + MAX_HEATMAP_POINTS - 1)
                        / MAX_HEATMAP_POINTS
        );
        boolean firstFeature = true;

        for (int i = 0; i < streetLamps.size(); i += pointStep) {
            StreetLamp streetLamp = streetLamps.get(i);

            if (!firstFeature) {
                features.append(",");
            }
            firstFeature = false;

            features.append("{\"type\":\"Feature\",\"geometry\":{")
                    .append("\"type\":\"Point\",\"coordinates\":[")
                    .append(streetLamp.getLongitude())
                    .append(",")
                    .append(streetLamp.getLatitude())
                    .append("]}}");
        }

        features.append("]");

        String sourceJson =
                "{\"type\":\"geojson\",\"data\":{"
                        + "\"type\":\"FeatureCollection\",\"features\":"
                        + features
                        + "}}";

        String layerJson =
                "{\"id\":\"" + STREET_LAMPS_LAYER_ID + "\","
                        + "\"type\":\"heatmap\","
                        + "\"source\":\"" + STREET_LAMPS_SOURCE_ID + "\","
                        + "\"maxzoom\":22,"
                        + "\"paint\":{"
                        + "\"heatmap-radius\":[\"interpolate\",[\"linear\"],[\"zoom\"],"
                        + "10,10,14,16,18,24,22,30],"
                        + "\"heatmap-intensity\":[\"interpolate\",[\"linear\"],[\"zoom\"],"
                        + "10,0.7,14,0.95,18,1.2,22,1.35],"
                        + "\"heatmap-color\":[\"interpolate\",[\"linear\"],"
                        + "[\"heatmap-density\"],"
                        + "0,\"rgba(255,224,102,0)\","
                        + "0.15,\"rgba(255,235,140,0.28)\","
                        + "0.35,\"rgba(255,225,80,0.46)\","
                        + "0.6,\"rgba(255,190,35,0.66)\","
                        + "0.85,\"rgba(255,155,20,0.82)\","
                        + "1,\"rgba(235,105,10,0.9)\"],"
                        + "\"heatmap-opacity\":0.86"
                        + "}}";

        mapView.getMapboxMap().getStyle(style -> {
            try {
                style.removeStyleLayer(STREET_LAMPS_LAYER_ID);
                style.removeStyleSource(STREET_LAMPS_SOURCE_ID);
            } catch (Exception ignored) {
            }

            Expected<String, Value> sourceExpected =
                    Value.fromJson(sourceJson);
            Expected<String, Value> layerExpected =
                    Value.fromJson(layerJson);

            if (sourceExpected.isError() || layerExpected.isError()) {
                System.out.println("Błąd tworzenia heatmapy latarni");
                return;
            }

            style.addStyleSource(
                    STREET_LAMPS_SOURCE_ID,
                    sourceExpected.getValue()
            );
            style.addStyleLayer(
                    layerExpected.getValue(),
                    null
            );

            updateStreetLampLayerVisibility();
        });
    }

    private void updateStreetLampLayerVisibility() {

        if (mapView == null) {
            return;
        }

        mapView.getMapboxMap().getStyle(style ->
                style.setStyleLayerProperty(
                        STREET_LAMPS_LAYER_ID,
                        "visibility",
                        Value.valueOf(
                                lightingLayerEnabled
                                        ? "visible"
                                        : "none"
                        )
                )
        );
    }

    private void updateCrimeEventMarkers(List<CrimeEvent> events) {

        if (mapView == null) {
            return;
        }

        AnnotationPlugin annotationPlugin =
                mapView.getPlugin(
                        Plugin.MAPBOX_ANNOTATION_PLUGIN_ID
                );

        if (annotationPlugin == null) {
            return;
        }

        if (crimeEventAnnotationManager == null) {
            crimeEventAnnotationManager =
                    (PointAnnotationManager)
                            annotationPlugin.createAnnotationManager(
                                    AnnotationType.PointAnnotation,
                                    new AnnotationConfig()
                            );
        } else {
            crimeEventAnnotationManager.deleteAll();
        }

        crimeEventMap.clear();

        Bitmap warningBitmap = getHistoricalThreatBitmap();

        if (warningBitmap == null) {
            return;
        }

        int renderedEvents = Math.min(events.size(), MAX_POINT_ANNOTATIONS);
        for (int i = 0; i < renderedEvents; i++) {
            CrimeEvent event = events.get(i);
            PointAnnotationOptions options =
                    new PointAnnotationOptions()
                            .withPoint(
                                    Point.fromLngLat(
                                            event.getLongitude(),
                                            event.getLatitude()
                                    )
                            )
                            .withIconImage(warningBitmap)
                            .withIconSize(0.7);

            PointAnnotation annotation =
                    crimeEventAnnotationManager.create(options);

            crimeEventMap.put(annotation.getId(), event);
        }

        crimeEventAnnotationManager.addClickListener(
                annotation -> {
                    CrimeEvent event =
                            crimeEventMap.get(annotation.getId());

                    if (event != null) {
                        showCrimeEventInfo(event);
                    }

                    return true;
                }
        );

        updateCrimeEventLayerVisibility();
    }

    private void showCrimeEventInfo(CrimeEvent event) {

        if (safePointInfoPanel != null) {
            safePointInfoPanel.setVisibility(View.GONE);
        }

        if (reportInfoPanel != null) {
            reportInfoPanel.setVisibility(View.GONE);
        }

        historicalThreatInfoCategory.setText(
                "Kategoria: " + event.getCategory()
        );
        historicalThreatInfoDate.setText(
                "Data: " + event.getOccurred_at()
        );

        Double severity = event.getSeverity();
        String severityText = severity == null
                ? "Brak danych"
                : severity < 0.33
                        ? "Niskie"
                        : severity < 0.66
                                ? "Średnie"
                                : "Wysokie";

        historicalThreatInfoSeverity.setText(
                "⚠️ Poziom zagrożenia: " + severityText
        );
        historicalThreatInfoScore.setText(
                "Źródło: " + event.getSource()
                        + "\nOdległość: "
                        + String.format(
                        Locale.US,
                        "%.0f m",
                        event.getDistance_m()
                )
        );

        historicalThreatInfoPanel.setVisibility(View.VISIBLE);
    }

    private void updateCrimeEventLayerVisibility() {

        if (crimeEventAnnotationManager == null) {
            return;
        }

        crimeEventAnnotationManager.setIconOpacity(
                historicalThreatsLayerEnabled ? 1.0 : 0.0
        );
    }

    private static class SafePoint {

        String category;
        String name;
        String openingHoursRaw;
        boolean is24_7;
        double latitude;
        double longitude;

        SafePoint(
                String category,
                String name,
                String openingHoursRaw,
                boolean is24_7,
                double latitude,
                double longitude
        ) {
            this.category = category;
            this.name = name;
            this.openingHoursRaw = openingHoursRaw;
            this.is24_7 = is24_7;
            this.latitude = latitude;
            this.longitude = longitude;
        }
    }

    private List<SafePoint> getExampleSafePoints() {

        double arenaLat = 50.0670;
        double arenaLon = 19.9934;

        List<SafePoint> points = new ArrayList<>();

        points.add(
                new SafePoint(
                        "police",
                        "Komisariat Policji",
                        "00:00-24:00",
                        true,
                        arenaLat + 0.0020,
                        arenaLon - 0.0015
                )
        );

        points.add(
                new SafePoint(
                        "hospital",
                        "Szpital",
                        "00:00-24:00",
                        true,
                        arenaLat + 0.0010,
                        arenaLon + 0.0020
                )
        );

        points.add(
                new SafePoint(
                        "fire_station",
                        "Straż Pożarna",
                        "00:00-24:00",
                        true,
                        arenaLat - 0.0015,
                        arenaLon + 0.0015
                )
        );

        points.add(
                new SafePoint(
                        "pharmacy",
                        "Apteka",
                        "08:00-20:00",
                        false,
                        arenaLat - 0.0010,
                        arenaLon - 0.0020
                )
        );

        points.add(
                new SafePoint(
                        "fuel_station",
                        "Stacja paliw",
                        "00:00-24:00",
                        true,
                        arenaLat + 0.0025,
                        arenaLon + 0.0005
                )
        );

        points.add(
                new SafePoint(
                        "shop",
                        "Sklep",
                        "06:00-23:00",
                        false,
                        arenaLat - 0.0020,
                        arenaLon + 0.0005
                )
        );

        points.add(
                new SafePoint(
                        "public_transport",
                        "Przystanek autobusowy",
                        "00:00-24:00",
                        true,
                        arenaLat + 0.0005,
                        arenaLon - 0.0025
                )
        );

        points.add(
                new SafePoint(
                        "other",
                        "Punkt bezpieczeństwa",
                        "00:00-24:00",
                        true,
                        arenaLat - 0.0025,
                        arenaLon - 0.0005
                )
        );

        return points;
    }

    private Bitmap getSafePointBitmap(String category) {

        String emoji;

        switch (category) {

            case "police":
                emoji = "👮";
                break;

            case "hospital":
                emoji = "🏥";
                break;

            case "fire_station":
                emoji = "🚒";
                break;

            case "pharmacy":
                emoji = "💊";
                break;

            case "fuel_station":
                emoji = "⛽";
                break;

            case "shop":
                emoji = "🛒";
                break;

            case "public_transport":
                emoji = "🚌";
                break;

            default:
                emoji = "📍";
                break;
        }

        int size = 120;

        Bitmap bitmap =
                Bitmap.createBitmap(
                        size,
                        size,
                        Bitmap.Config.ARGB_8888
                );

        Canvas canvas = new Canvas(bitmap);

        Paint paint =
                new Paint(Paint.ANTI_ALIAS_FLAG);

        paint.setTextSize(70);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT);

        canvas.drawText(
                emoji,
                size / 2f,
                82,
                paint
        );

        return bitmap;
    }

    private void updateSafePointMarkers(List<SafePlace> places) {

        if (mapView == null) {
            return;
        }

        AnnotationPlugin annotationPlugin =
                mapView.getPlugin(
                        Plugin.MAPBOX_ANNOTATION_PLUGIN_ID
                );

        if (annotationPlugin == null) {
            return;
        }

        if (safePointAnnotationManager == null) {

            safePointAnnotationManager =
                    (PointAnnotationManager)
                            annotationPlugin.createAnnotationManager(
                                    AnnotationType.PointAnnotation,
                                    new AnnotationConfig()
                            );

        } else {

            safePointAnnotationManager.deleteAll();
        }

        apiSafePlaceMap.clear();

        int renderedPlaces = Math.min(places.size(), MAX_POINT_ANNOTATIONS);
        for (int i = 0; i < renderedPlaces; i++) {
            SafePlace safePlace = places.get(i);

            Bitmap bitmap =
                    getSafePointBitmap(
                            safePlace.getCategory()
                    );

            PointAnnotationOptions options =
                    new PointAnnotationOptions()
                            .withPoint(
                                    Point.fromLngLat(
                                            safePlace.getLongitude(),
                                            safePlace.getLatitude()
                                    )
                            )
                            .withIconImage(bitmap)
                            .withIconSize(0.8);

            PointAnnotation annotation =
                    safePointAnnotationManager.create(
                            options
                    );

            apiSafePlaceMap.put(
                    annotation.getId(),
                    safePlace
            );
        }

        safePointAnnotationManager.addClickListener(
                annotation -> {

                    SafePlace place =
                            apiSafePlaceMap.get(
                                    annotation.getId()
                            );

                    if (place != null) {

                        showSafePlaceInfo(place);
                    }

                    return true;
                }
        );

        updateSafePointLayerVisibility();
    }

    private void showSafePlaceInfo(SafePlace place) {

        if (safePointInfoPanel == null) {
            return;
        }

        String category = place.getCategory();
        String name = place.getName();

        safePointInfoTitle.setText(
                getSafePointEmoji(category) + " " + name
        );
        safePointInfoName.setText("Nazwa: " + name);
        safePointInfoCategory.setText(
                "Kategoria: " + getSafePointCategoryName(category)
        );
        safePointInfoHours.setText(
                "Odległość: "
                        + String.format(Locale.US, "%.0f m", place.getDistance_m())
        );
        safePointInfo247.setText(
                place.isIs_24_7()
                        ? "🕐 Czynne 24/7"
                        : "🕐 Godziny ograniczone"
        );
        safePointInfoPanel.setVisibility(View.VISIBLE);
    }

    private void showSafePointInfo(SafePoint point) {

        if (safePointInfoPanel == null) {
            return;
        }

        safePointInfoTitle.setText(
                getSafePointEmoji(point.category)
                        + " "
                        + point.name
        );

        safePointInfoName.setText(
                "Nazwa: " + point.name
        );

        safePointInfoCategory.setText(
                "Kategoria: "
                        + getSafePointCategoryName(
                        point.category
                )
        );

        safePointInfoHours.setText(
                "Godziny: "
                        + point.openingHoursRaw
        );

        if (point.is24_7) {

            safePointInfo247.setText(
                    "🕐 Czynne 24/7"
            );

        } else {

            safePointInfo247.setText(
                    "🕐 Godziny ograniczone"
            );
        }

        safePointInfoPanel.setVisibility(
                View.VISIBLE
        );
    }

    private String getSafePointCategoryName(
            String category
    ) {

        switch (category) {

            case "police":
                return "Policja";

            case "hospital":
                return "Szpital";

            case "fire_station":
                return "Straż Pożarna";

            case "pharmacy":
                return "Apteka";

            case "fuel_station":
                return "Stacja paliw";

            case "shop":
                return "Sklep";

            case "public_transport":
                return "Transport publiczny";

            default:
                return "Inne";
        }
    }

    private String getSafePointEmoji(
            String category
    ) {

        switch (category) {

            case "police":
                return "👮";

            case "hospital":
                return "🏥";

            case "fire_station":
                return "🚒";

            case "pharmacy":
                return "💊";

            case "fuel_station":
                return "⛽";

            case "shop":
                return "🛒";

            case "public_transport":
                return "🚌";

            default:
                return "📍";
        }
    }

    private List<HistoricalThreat> getExampleHistoricalThreats() {

        double arenaLat = 50.0670;
        double arenaLon = 19.9934;

        List<HistoricalThreat> threats =
                new ArrayList<>();

        threats.add(
                new HistoricalThreat(
                        "Kradzież",
                        "2026-09-12 21:30",
                        0.35,
                        arenaLat + 0.0015,
                        arenaLon + 0.0010
                )
        );

        threats.add(
                new HistoricalThreat(
                        "Napad",
                        "2026-08-27 23:10",
                        0.85,
                        arenaLat - 0.0010,
                        arenaLon + 0.0015
                )
        );

        threats.add(
                new HistoricalThreat(
                        "Wandalizm",
                        "2026-08-19 18:45",
                        0.55,
                        arenaLat + 0.0005,
                        arenaLon - 0.0015
                )
        );

        threats.add(
                new HistoricalThreat(
                        "Kradzież",
                        "2026-07-30 20:15",
                        0.25,
                        arenaLat - 0.0015,
                        arenaLon - 0.0010
                )
        );

        threats.add(
                new HistoricalThreat(
                        "Napad",
                        "2026-07-14 01:20",
                        0.95,
                        arenaLat + 0.0020,
                        arenaLon - 0.0005
                )
        );

        return threats;
    }

    private Bitmap getHistoricalThreatBitmap() {

        int width = 100;
        int height = 100;

        Bitmap bitmap =
                Bitmap.createBitmap(
                        width,
                        height,
                        Bitmap.Config.ARGB_8888
                );

        Canvas canvas =
                new Canvas(bitmap);

        Paint paint =
                new Paint(Paint.ANTI_ALIAS_FLAG);

        paint.setTextSize(75);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT_BOLD);

        canvas.drawText(
                "⚠️",
                width / 2f,
                75,
                paint
        );

        return bitmap;
    }

    private void updateHistoricalThreatMarkers() {

        if (mapView == null) {
            return;
        }

        AnnotationPlugin annotationPlugin =
                mapView.getPlugin(
                        Plugin.MAPBOX_ANNOTATION_PLUGIN_ID
                );

        if (annotationPlugin == null) {
            return;
        }

        if (historicalThreatAnnotationManager == null) {

            historicalThreatAnnotationManager =
                    (PointAnnotationManager)
                            annotationPlugin.createAnnotationManager(
                                    AnnotationType.PointAnnotation,
                                    new AnnotationConfig()
                            );

        } else {

            historicalThreatAnnotationManager.deleteAll();
        }

        historicalThreatMap.clear();

        Bitmap warningBitmap =
                getHistoricalThreatBitmap();

        if (warningBitmap == null) {
            return;
        }

        List<HistoricalThreat> threats =
                getExampleHistoricalThreats();

        for (HistoricalThreat threat : threats) {

            PointAnnotationOptions options =
                    new PointAnnotationOptions()
                            .withPoint(
                                    Point.fromLngLat(
                                            threat.longitude,
                                            threat.latitude
                                    )
                            )
                            .withIconImage(warningBitmap)
                            .withIconSize(0.7);

            PointAnnotation annotation =
                    historicalThreatAnnotationManager.create(
                            options
                    );

            historicalThreatMap.put(
                    annotation.getId(),
                    threat
            );
        }

        historicalThreatAnnotationManager.addClickListener(
                annotation -> {

                    HistoricalThreat threat =
                            historicalThreatMap.get(
                                    annotation.getId()
                            );

                    if (threat != null) {
                        showHistoricalThreatInfo(threat);
                    }

                    return true;
                }
        );

        updateHistoricalThreatLayerVisibility();
    }

    private void showHistoricalThreatInfo(
            HistoricalThreat threat
    ) {

        // Ukryj inne panele
        if (safePointInfoPanel != null) {
            safePointInfoPanel.setVisibility(View.GONE);
        }

        if (reportInfoPanel != null) {
            reportInfoPanel.setVisibility(View.GONE);
        }

        String severityText;

        if (threat.severity < 0.33) {
            severityText = "Niskie";
        } else if (threat.severity < 0.66) {
            severityText = "Średnie";
        } else {
            severityText = "Wysokie";
        }

        historicalThreatInfoCategory.setText(
                "Kategoria: " + threat.category
        );

        historicalThreatInfoDate.setText(
                "Data: " + threat.occuredAt
        );

        historicalThreatInfoSeverity.setText(
                "⚠️ Poziom zagrożenia: " + severityText
        );

        historicalThreatInfoScore.setText(
                "Severity: "
                        + String.format(
                        Locale.US,
                        "%.2f",
                        threat.severity
                )
        );

        historicalThreatInfoPanel.setVisibility(
                View.VISIBLE
        );
    }

    private void updateHistoricalThreatLayerVisibility() {

        if (historicalThreatAnnotationManager != null) {
            historicalThreatAnnotationManager.setIconOpacity(
                    historicalThreatsLayerEnabled ? 1.0 : 0.0
            );
        }

        updateCrimeEventLayerVisibility();
    }
    private void updateSafePointLayerVisibility() {

        if (safePointAnnotationManager == null) {
            return;
        }

        safePointAnnotationManager.setIconOpacity(
                safePointsLayerEnabled ? 1.0 : 0.0
        );
    }

    // =========================================================
    // DYNAMICZNE MENU ZAPISANYCH MIEJSC (ELEGANCKIE UI)
    // =========================================================

    private void showSavedPlacesMenu() {
        android.content.SharedPreferences prefs = requireActivity().getSharedPreferences("SafeRoutePrefs", android.content.Context.MODE_PRIVATE);
        // Puste na start, zero zahardcodowanych miejsc
        String savedData = prefs.getString("saved_places", ""); 

        AlertDialog.Builder builder = new AlertDialog.Builder(requireContext());
        AlertDialog dialog = builder.create();

        // Główny kontener dialogu z zaokrąglonymi rogami
        LinearLayout container = new LinearLayout(requireContext());
        container.setOrientation(LinearLayout.VERTICAL);
        container.setPadding(60, 60, 60, 60);
        
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(android.graphics.Color.parseColor("#1E1E1E")); // Ciemnoszary panel
        bg.setCornerRadius(40f); // Mocne zaokrąglenie
        container.setBackground(bg);

        // Tytuł
        TextView title = new TextView(requireContext());
        title.setText("Twoje Miejsca");
        title.setTextColor(android.graphics.Color.WHITE);
        title.setTextSize(22);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setPadding(0, 0, 0, 40);
        container.addView(title);

        // Lista miejsc (przewijana)
        android.widget.ScrollView scrollView = new android.widget.ScrollView(requireContext());
        LinearLayout listLayout = new LinearLayout(requireContext());
        listLayout.setOrientation(LinearLayout.VERTICAL);
        scrollView.addView(listLayout);

        if (!savedData.isEmpty()) {
            String[] entries = savedData.split("#");
            for (int i = 0; i < entries.length; i++) {
                String entry = entries[i];
                String[] parts = entry.split("\\|");
                if (parts.length == 2) {
                    String name = parts[0];
                    String address = parts[1];
                    final int index = i;

                    // Wiersz pojedynczego miejsca
                    LinearLayout row = new LinearLayout(requireContext());
                    row.setOrientation(LinearLayout.HORIZONTAL);
                    row.setPadding(0, 20, 0, 20);
                    row.setGravity(android.view.Gravity.CENTER_VERTICAL);

                    // Klikalna sekcja tekstowa (Nazwa + Adres)
                    LinearLayout textLayout = new LinearLayout(requireContext());
                    textLayout.setOrientation(LinearLayout.VERTICAL);
                    LinearLayout.LayoutParams textParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
                    textLayout.setLayoutParams(textParams);
                    
                    // Ripple effect po kliknięciu
                    android.util.TypedValue outValue = new android.util.TypedValue();
                    requireContext().getTheme().resolveAttribute(android.R.attr.selectableItemBackground, outValue, true);
                    textLayout.setBackgroundResource(outValue.resourceId);
                    textLayout.setClickable(true);
                    textLayout.setFocusable(true);

                    TextView tvName = new TextView(requireContext());
                    tvName.setText("⭐ " + name);
                    tvName.setTextColor(android.graphics.Color.WHITE);
                    tvName.setTextSize(16);
                    tvName.setTypeface(null, android.graphics.Typeface.BOLD);

                    TextView tvAddress = new TextView(requireContext());
                    tvAddress.setText(address);
                    tvAddress.setTextColor(android.graphics.Color.parseColor("#AAAAAA"));
                    tvAddress.setTextSize(13);
                    tvAddress.setPadding(0, 4, 0, 0);

                    textLayout.addView(tvName);
                    textLayout.addView(tvAddress);

                    // Mały, czerwony 'X' do usuwania
                    TextView btnDelete = new TextView(requireContext());
                    btnDelete.setText("✕");
                    btnDelete.setTextColor(android.graphics.Color.parseColor("#F44336"));
                    btnDelete.setTextSize(20);
                    btnDelete.setTypeface(null, android.graphics.Typeface.BOLD);
                    btnDelete.setPadding(30, 20, 10, 20);

                    row.addView(textLayout);
                    row.addView(btnDelete);

                    // Logika kliknięć
                    textLayout.setOnClickListener(v -> {
                        searchDestination.setText(address);
                        searchButton.performClick();
                        dialog.dismiss();
                    });

                    btnDelete.setOnClickListener(v -> {
                        dialog.dismiss();
                        showDeleteConfirmation(name, index, savedData);
                    });

                    listLayout.addView(row);

                    // Delikatna linia oddzielająca (poza ostatnim elementem)
                    if (i < entries.length - 1) {
                        View divider = new View(requireContext());
                        divider.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 2));
                        divider.setBackgroundColor(android.graphics.Color.parseColor("#2C2C2C"));
                        listLayout.addView(divider);
                    }
                }
            }
        } else {
            TextView empty = new TextView(requireContext());
            empty.setText("Brak zapisanych miejsc.\nKliknij przycisk poniżej, aby coś dodać.");
            empty.setTextColor(android.graphics.Color.GRAY);
            empty.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);
            empty.setPadding(0, 20, 0, 40);
            listLayout.addView(empty);
        }

        // Ogranicz wysokość ScrollView, żeby ekran się nie rozjechał przy 20 miejscach
        LinearLayout.LayoutParams scrollParams = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        scrollView.setLayoutParams(scrollParams);
        container.addView(scrollView);

        // Przycisk "Dodaj nowe miejsce"
        Button btnAdd = new Button(requireContext());
        btnAdd.setText("+ Dodaj nowe miejsce");
        btnAdd.setBackgroundTintList(android.content.res.ColorStateList.valueOf(android.graphics.Color.parseColor("#4CAF50"))); // Zielony
        btnAdd.setTextColor(android.graphics.Color.WHITE);
        btnAdd.setAllCaps(false);
        btnAdd.setTextSize(16);
        
        android.graphics.drawable.GradientDrawable btnBg = new android.graphics.drawable.GradientDrawable();
        btnBg.setColor(android.graphics.Color.parseColor("#4CAF50"));
        btnBg.setCornerRadius(20f);
        btnAdd.setBackground(btnBg);

        LinearLayout.LayoutParams btnParams = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 140); // Grubszy przycisk
        btnParams.setMargins(0, 50, 0, 0);
        btnAdd.setLayoutParams(btnParams);
        
        btnAdd.setOnClickListener(v -> {
            dialog.dismiss();
            showAddPlaceDialog();
        });

        container.addView(btnAdd);

        dialog.setView(container);
        
        // Ukrycie standardowego, kwadratowego tła Androida, żeby zaokrąglenia zadziałały
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT));
        }
        
        dialog.show();
    }

    private void showAddPlaceDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(requireContext());
        AlertDialog dialog = builder.create();

        LinearLayout layout = new LinearLayout(requireContext());
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(60, 60, 60, 60);

        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(android.graphics.Color.parseColor("#1E1E1E"));
        bg.setCornerRadius(40f);
        layout.setBackground(bg);

        TextView title = new TextView(requireContext());
        title.setText("Nowe Miejsce");
        title.setTextColor(android.graphics.Color.WHITE);
        title.setTextSize(22);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setPadding(0, 0, 0, 40);
        layout.addView(title);

        // Stylizowane pola tekstowe
        android.graphics.drawable.GradientDrawable inputBg = new android.graphics.drawable.GradientDrawable();
        inputBg.setColor(android.graphics.Color.parseColor("#2C2C2C"));
        inputBg.setCornerRadius(20f);

        final EditText nameInput = new EditText(requireContext());
        nameInput.setHint("Nazwa (np. Dom chłopaka)");
        nameInput.setHintTextColor(android.graphics.Color.parseColor("#888888"));
        nameInput.setTextColor(android.graphics.Color.WHITE);
        nameInput.setBackground(inputBg);
        nameInput.setPadding(40, 40, 40, 40);
        layout.addView(nameInput);

        final EditText addressInput = new EditText(requireContext());
        addressInput.setHint("Pełny adres (np. ul. Długa 5)");
        addressInput.setHintTextColor(android.graphics.Color.parseColor("#888888"));
        addressInput.setTextColor(android.graphics.Color.WHITE);
        addressInput.setBackground(inputBg);
        addressInput.setPadding(40, 40, 40, 40);
        
        LinearLayout.LayoutParams addressParams = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        addressParams.setMargins(0, 30, 0, 40);
        addressInput.setLayoutParams(addressParams);
        layout.addView(addressInput);

        // Przyciski Zapisz / Anuluj
        LinearLayout btnLayout = new LinearLayout(requireContext());
        btnLayout.setOrientation(LinearLayout.HORIZONTAL);
        btnLayout.setWeightSum(2);

        Button btnCancel = new Button(requireContext());
        btnCancel.setText("Anuluj");
        btnCancel.setTextColor(android.graphics.Color.parseColor("#AAAAAA"));
        btnCancel.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        btnCancel.setAllCaps(false);
        LinearLayout.LayoutParams param1 = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        btnCancel.setLayoutParams(param1);

        Button btnSave = new Button(requireContext());
        btnSave.setText("Zapisz");
        btnSave.setTextColor(android.graphics.Color.parseColor("#4CAF50"));
        btnSave.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        btnSave.setAllCaps(false);
        btnSave.setTypeface(null, android.graphics.Typeface.BOLD);
        LinearLayout.LayoutParams param2 = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        btnSave.setLayoutParams(param2);

        btnLayout.addView(btnCancel);
        btnLayout.addView(btnSave);
        layout.addView(btnLayout);

        // Akcje przycisków
        btnCancel.setOnClickListener(v -> dialog.dismiss());

        btnSave.setOnClickListener(v -> {
            String name = nameInput.getText().toString().replace("|", "").replace("#", "").trim();
            String address = addressInput.getText().toString().replace("|", "").replace("#", "").trim();

            if (!name.isEmpty() && !address.isEmpty()) {
                android.content.SharedPreferences prefs = requireActivity().getSharedPreferences("SafeRoutePrefs", android.content.Context.MODE_PRIVATE);
                String currentData = prefs.getString("saved_places", "");
                
                String newData = currentData.isEmpty() ? name + "|" + address : currentData + "#" + name + "|" + address;
                prefs.edit().putString("saved_places", newData).apply();
                
                Toast.makeText(getContext(), "Zapisano: " + name, Toast.LENGTH_SHORT).show();
                dialog.dismiss();
                showSavedPlacesMenu(); // Odśwież widok
            } else {
                Toast.makeText(getContext(), "Wypełnij obie wartości!", Toast.LENGTH_SHORT).show();
            }
        });

        dialog.setView(layout);
        if (dialog.getWindow() != null) dialog.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT));
        dialog.show();
    }

    private void showDeleteConfirmation(String placeName, int indexToRemove, String currentData) {
        AlertDialog.Builder builder = new AlertDialog.Builder(requireContext());
        AlertDialog dialog = builder.create();

        LinearLayout layout = new LinearLayout(requireContext());
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(60, 60, 60, 60);

        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(android.graphics.Color.parseColor("#1E1E1E"));
        bg.setCornerRadius(40f);
        layout.setBackground(bg);

        TextView title = new TextView(requireContext());
        title.setText("Usunąć miejsce?");
        title.setTextColor(android.graphics.Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        layout.addView(title);

        TextView message = new TextView(requireContext());
        message.setText("Czy na pewno chcesz bezpowrotnie usunąć zakładkę '" + placeName + "'?");
        message.setTextColor(android.graphics.Color.parseColor("#AAAAAA"));
        message.setTextSize(14);
        message.setPadding(0, 20, 0, 40);
        layout.addView(message);

        // Przyciski
        LinearLayout btnLayout = new LinearLayout(requireContext());
        btnLayout.setOrientation(LinearLayout.HORIZONTAL);
        btnLayout.setGravity(android.view.Gravity.END);

        Button btnCancel = new Button(requireContext());
        btnCancel.setText("Anuluj");
        btnCancel.setTextColor(android.graphics.Color.parseColor("#AAAAAA"));
        btnCancel.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        btnCancel.setAllCaps(false);

        Button btnDelete = new Button(requireContext());
        btnDelete.setText("Usuń");
        btnDelete.setTextColor(android.graphics.Color.parseColor("#F44336")); // Czerwony
        btnDelete.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        btnDelete.setAllCaps(false);
        btnDelete.setTypeface(null, android.graphics.Typeface.BOLD);

        btnLayout.addView(btnCancel);
        btnLayout.addView(btnDelete);
        layout.addView(btnLayout);

        btnCancel.setOnClickListener(v -> {
            dialog.dismiss();
            showSavedPlacesMenu(); // Wróć do menu
        });

        btnDelete.setOnClickListener(v -> {
            String[] entries = currentData.split("#");
            StringBuilder newData = new StringBuilder();
            
            for (int i = 0; i < entries.length; i++) {
                if (i != indexToRemove) {
                    if (newData.length() > 0) newData.append("#");
                    newData.append(entries[i]);
                }
            }
            
            android.content.SharedPreferences prefs = requireActivity().getSharedPreferences("SafeRoutePrefs", android.content.Context.MODE_PRIVATE);
            prefs.edit().putString("saved_places", newData.toString()).apply();
            
            Toast.makeText(getContext(), "Usunięto.", Toast.LENGTH_SHORT).show();
            dialog.dismiss();
            showSavedPlacesMenu(); // Otwórz odświeżoną listę
        });

        dialog.setView(layout);
        if (dialog.getWindow() != null) dialog.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT));
        dialog.show();
    }

    private List<CityEvent> getExampleCityEvents() {

        double arenaLat = 50.0670;
        double arenaLon = 19.9934;

        List<CityEvent> events = new ArrayList<>();

        events.add(new CityEvent(
                "Wielki mecz piłkarski",
                "Duże wydarzenie sportowe. Możliwe zwiększone natężenie ruchu oraz ryzyko incydentów.",
                "Mecz sportowy",
                "2026-10-12 18:00",
                "2026-10-12 22:30",
                arenaLat,
                arenaLon,
                1500,
                0.25
        ));

        return events;
    }

    private Bitmap getCityEventBitmap() {

        int width = 100;
        int height = 100;

        Bitmap bitmap =
                Bitmap.createBitmap(
                        width,
                        height,
                        Bitmap.Config.ARGB_8888
                );

        Canvas canvas = new Canvas(bitmap);

        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

        paint.setColor(
                android.graphics.Color.rgb(156, 39, 176)
        );

        canvas.drawCircle(
                width / 2f,
                height / 2f,
                42,
                paint
        );

        paint.setColor(android.graphics.Color.WHITE);
        paint.setTextSize(48);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT_BOLD);

        canvas.drawText(
                "!",
                width / 2f,
                67,
                paint
        );

        return bitmap;
    }

    private void updateCityEventMarkers() {

        if (mapView == null) {
            return;
        }

        AnnotationPlugin annotationPlugin =
                mapView.getPlugin(
                        Plugin.MAPBOX_ANNOTATION_PLUGIN_ID
                );

        if (annotationPlugin == null) {
            return;
        }

        if (cityEventAnnotationManager == null) {

            cityEventAnnotationManager =
                    (PointAnnotationManager)
                            annotationPlugin.createAnnotationManager(
                                    AnnotationType.PointAnnotation,
                                    new AnnotationConfig()
                            );

        } else {

            cityEventAnnotationManager.deleteAll();
        }

        cityEventMap.clear();

        Bitmap eventBitmap =
                getCityEventBitmap();

        if (eventBitmap == null) {
            return;
        }

        List<CityEvent> events =
                getExampleCityEvents();

        for (CityEvent event : events) {

            PointAnnotationOptions options =
                    new PointAnnotationOptions()
                            .withPoint(
                                    Point.fromLngLat(
                                            event.longitude,
                                            event.latitude
                                    )
                            )
                            .withIconImage(eventBitmap)
                            .withIconSize(0.7);

            PointAnnotation annotation =
                    cityEventAnnotationManager.create(
                            options
                    );

            cityEventMap.put(
                    annotation.getId(),
                    event
            );
        }

        cityEventAnnotationManager.addClickListener(
                annotation -> {

                    CityEvent event =
                            cityEventMap.get(
                                    annotation.getId()
                            );

                    if (event != null) {
                        showCityEventInfo(event);
                    }

                    return true;
                }
        );

        updateCityEventLayerVisibility();
    }

    private void showCityEventInfo(
            CityEvent event
    ) {

        if (safePointInfoPanel != null) {
            safePointInfoPanel.setVisibility(
                    View.GONE
            );
        }

        if (reportInfoPanel != null) {
            reportInfoPanel.setVisibility(
                    View.GONE
            );
        }

        if (historicalThreatInfoPanel != null) {
            historicalThreatInfoPanel.setVisibility(
                    View.GONE
            );
        }

        cityEventInfoTitle.setText(
                "🏟️ " + event.title
        );

        cityEventInfoCategory.setText(
                "Kategoria: " + event.category
        );

        cityEventInfoDescription.setText(
                event.description
        );

        cityEventInfoDate.setText(
                "📅 " + event.startsAt
                        + " – "
                        + event.endsAt
        );

        cityEventInfoRisk.setText(
                "⚠️ Wpływ na bezpieczeństwo: +"
                        + String.format(
                        Locale.US,
                        "%.0f",
                        event.riskIncrease * 100
                )
                        + "%"
        );

        cityEventInfoPanel.setVisibility(
                View.VISIBLE
        );
    }

    private void updateCityEventLayerVisibility() {

        if (cityEventAnnotationManager == null) {
            return;
        }

        cityEventAnnotationManager.setIconOpacity(
                cityEventsLayerEnabled
                        ? 1.0
                        : 0.0
        );
    }
    private String getCategoryPolishName(String category) {
        if (category == null) return "Inne";
        switch (category) {
            case "danger": return "Niebezpieczeństwo";
            case "harassment": return "Nękanie";
            case "poor_lighting": return "Słabe oświetlenie";
            case "blocked_path": return "Zablokowana droga";
            case "suspicious_activity": return "Podejrzana aktywność";
            case "other": return "Inne";
            default: return category;
        }
    }
}