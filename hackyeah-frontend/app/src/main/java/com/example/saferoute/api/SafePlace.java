package com.example.saferoute.api;

public class SafePlace {

    private int id;
    private String category;
    private String name;
    private String opening_hours_raw;
    private boolean is_24_7;
    private double latitude;
    private double longitude;
    private double distance_m;

    public int getId() {
        return id;
    }

    public String getCategory() {
        return category;
    }

    public String getName() {
        return name;
    }

    public String getOpening_hours_raw() {
        return opening_hours_raw;
    }

    public boolean isIs_24_7() {
        return is_24_7;
    }

    public double getLatitude() {
        return latitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public double getDistance_m() {
        return distance_m;
    }
}