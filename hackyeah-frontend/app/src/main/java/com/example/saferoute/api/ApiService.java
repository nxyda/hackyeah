package com.example.saferoute.api;

import java.util.List;

import retrofit2.Call;
import retrofit2.http.GET;
import retrofit2.http.Path;
import retrofit2.http.Body;
import retrofit2.http.POST;
import retrofit2.http.Query;

public interface ApiService {

    @GET("v1/safe-places/nearby")
    Call<List<SafePlace>> getNearbySafePlaces(
            @Query("lon") double longitude,
            @Query("lat") double latitude,
            @Query("radius_m") double radius
    );

    @GET("v1/cameras/nearby")
    Call<List<Camera>> getNearbyCameras(
            @Query("lon") double longitude,
            @Query("lat") double latitude,
            @Query("radius_m") double radius
    );

    @GET("v1/street-lamps/nearby")
    Call<List<StreetLamp>> getNearbyStreetLamps(
            @Query("lon") double longitude,
            @Query("lat") double latitude,
            @Query("radius_m") double radius
    );

    @GET("v1/street-lamps/{street_lamp_id}")
    Call<StreetLamp> getStreetLamp(
            @Path("street_lamp_id") int streetLampId
    );

    @GET("v1/cameras/{camera_id}")
    Call<Camera> getCamera(
            @Path("camera_id") int cameraId
    );

    @GET("v1/crime-events/nearby")
    Call<List<CrimeEvent>> getNearbyCrimeEvents(
            @Query("lon") double longitude,
            @Query("lat") double latitude,
            @Query("radius_m") double radius,
            @Query("occurred_after") String occurredAfter,
            @Query("occurred_before") String occurredBefore
    );

    @GET("v1/crime-events/{event_id}")
    Call<CrimeEvent> getCrimeEvent(
            @Path("event_id") int eventId
    );
    @POST("v1/route")
    Call<RouteResponse> createRoute(@Body RouteRequest request);
}