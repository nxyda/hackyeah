package com.example.saferoute.api;

import java.util.List;

public class RouteResponse {

    public RouteOption fastest;
    public RouteOption safest;
    public List<RouteOption> alternatives;

    public static class RouteOption {
        public Geometry geometry;
        public double duration_s;
        public double distance_m;
        public double safety_score;
        public String explanation;
        public List<NavigationStep> navigation_steps;
    }

    public static class Geometry {
        public List<List<Double>> coordinates;
    }

    public static class NavigationStep {
        public String instruction;
        public String maneuver;
        public double distance_m;
        public Coordinate location;
    }

    public static class Coordinate {
        public double lat;
        public double lon;
    }
}
