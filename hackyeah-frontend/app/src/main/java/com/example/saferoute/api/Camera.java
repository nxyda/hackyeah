package com.example.saferoute.api;

public class Camera {

    private int id;
    private Long osm_id;
    private double latitude;
    private double longitude;
    private double distance_m;

    public int getId() {
        return id;
    }

    public Long getOsm_id() {
        return osm_id;
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
