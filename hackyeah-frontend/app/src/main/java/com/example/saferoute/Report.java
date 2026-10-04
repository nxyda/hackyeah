package com.example.saferoute;

import org.osmdroid.util.GeoPoint;

class Report {
    String id;
    GeoPoint location;
    String timestamp;
    String category;

    public Report(String id, GeoPoint location, String timestamp, String category) {
        this.id = id;
        this.location = location;
        this.timestamp = timestamp;
        this.category = category;
    }
}
