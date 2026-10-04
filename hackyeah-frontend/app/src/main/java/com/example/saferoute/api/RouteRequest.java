package com.example.saferoute.api;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

public class RouteRequest {

    public Coordinate start;
    public Coordinate end;
    public String departure_time;
    public double safety_weight;
    public String profile;

    public RouteRequest(double startLat, double startLon, double endLat, double endLon) {
        start = new Coordinate(startLat, startLon);
        end = new Coordinate(endLat, endLon);
        SimpleDateFormat dateFormat =
                new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
        dateFormat.setTimeZone(TimeZone.getTimeZone("UTC"));
        departure_time = dateFormat.format(new Date());
        safety_weight = 1.0;
        profile = "walking";
    }

    public static class Coordinate {
        public double lat;
        public double lon;

        public Coordinate(double lat, double lon) {
            this.lat = lat;
            this.lon = lon;
        }
    }
}
