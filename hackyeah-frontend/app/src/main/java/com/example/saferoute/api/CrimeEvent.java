package com.example.saferoute.api;

public class CrimeEvent {

    private int id;
    private String category;
    private double latitude;
    private double longitude;
    private String occurred_at;
    private String source;
    private Double severity;
    private double distance_m;

    public int getId() {
        return id;
    }

    public String getCategory() {
        return category;
    }

    public double getLatitude() {
        return latitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public String getOccurred_at() {
        return occurred_at;
    }

    public String getSource() {
        return source;
    }

    public Double getSeverity() {
        return severity;
    }

    public double getDistance_m() {
        return distance_m;
    }
}
