package com.example.saferoute;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Map;

public final class TrustScore {

    private static final String PREFS_NAME = "SafeRouteReportPrefs";
    private static final String KEY_CREATED = "trust_reports_created";
    private static final String KEY_LIKES = "trust_likes";
    private static final String KEY_DISLIKES = "trust_dislikes";
    private static final String REACTION_PREFIX = "reaction_";
    private TrustScore() {
    }

    public static int getReportsCreated(Context context) {
        return preferences(context).getInt(KEY_CREATED, 0);
    }

    public static int getLikes(Context context) {
        return reactionCount(context, "like");
    }

    public static int getDislikes(Context context) {
        return reactionCount(context, "dislike");
    }

    public static int getScore(Context context) {
        int score = getReportsCreated(context) * 5
                + getLikes(context) * 2;
        return Math.max(0, Math.min(100, score));
    }

    public static void recordReportCreated(Context context) {
        SharedPreferences preferences = preferences(context);
        preferences.edit()
                .putInt(KEY_CREATED, preferences.getInt(KEY_CREATED, 0) + 1)
                .apply();
    }

    public static boolean recordReaction(Context context, String reportId, String reaction) {
        SharedPreferences preferences = preferences(context);
        String key = REACTION_PREFIX + reportId;
        if (preferences.contains(key)) {
            return false;
        }

        SharedPreferences.Editor editor = preferences.edit().putString(key, reaction);
        if ("like".equals(reaction)) {
            editor.putInt(KEY_LIKES, reactionCount(context, "like") + 1);
        } else if ("dislike".equals(reaction)) {
            editor.putInt(KEY_DISLIKES, reactionCount(context, "dislike") + 1);
        } else {
            return false;
        }
        editor.apply();
        return true;
    }

    private static int reactionCount(Context context, String reaction) {
        SharedPreferences preferences = preferences(context);
        String key = "like".equals(reaction) ? KEY_LIKES : KEY_DISLIKES;
        if (preferences.contains(key)) {
            return preferences.getInt(key, 0);
        }

        int count = 0;
        for (Map.Entry<String, ?> entry : preferences.getAll().entrySet()) {
            if (entry.getKey().startsWith(REACTION_PREFIX)
                    && reaction.equals(entry.getValue())) {
                count++;
            }
        }
        preferences.edit().putInt(key, count).apply();
        return count;
    }

    private static SharedPreferences preferences(Context context) {
        return context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }
}
