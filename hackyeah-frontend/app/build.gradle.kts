import java.util.Properties
import java.io.FileInputStream

plugins {
    alias(libs.plugins.android.application)
}

val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")

if (localPropertiesFile.exists()) {
    localProperties.load(FileInputStream(localPropertiesFile))
}

val mapboxAccessToken = localProperties.getProperty("MAPBOX_ACCESS_TOKEN")
    ?: ""
val apiBaseUrl = localProperties.getProperty("API_BASE_URL")
    ?: "http://10.0.2.2:8000/"

android {
    namespace = "com.example.saferoute"

    compileSdk {
        version = release(36)
    }

    buildFeatures {
        buildConfig = true
    }

    defaultConfig {
        applicationId = "com.example.saferoute"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField(
            "String",
            "MAPBOX_ACCESS_TOKEN",
            "\"$mapboxAccessToken\""
        )

        buildConfigField(
            "String",
            "API_BASE_URL",
            "\"${apiBaseUrl.replace("\\", "\\\\").replace("\"", "\\\"")}\""
        )

        val geminiKey = localProperties.getProperty("GEMINI_API_KEY") ?: ""
        buildConfigField("String", "GEMINI_API_KEY", "\"$geminiKey\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.appcompat)
    implementation(libs.material)

    implementation("com.mapbox.maps:android-ndk27:11.31.1")

    implementation("com.mapbox.navigationcore:android-ndk27:3.31.1")
    implementation("com.mapbox.navigationcore:ui-maps-ndk27:3.31.1")
    implementation("com.mapbox.navigationcore:tripdata-ndk27:3.31.1")
    implementation("com.mapbox.navigationcore:ui-components-ndk27:3.31.1")
    implementation("com.mapbox.navigationcore:voice-ndk27:3.31.1")
    implementation("com.google.android.gms:play-services-location:21.3.0")
    implementation("com.mapbox.search:mapbox-search-android-ndk27:2.31.1")
    implementation("com.mapbox.search:place-autocomplete-ndk27:2.31.1")
    implementation("org.osmdroid:osmdroid-android:6.1.18")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")

    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
}