plugins { id("com.android.application") }

android {
    namespace = "dev.div652.grevocab"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.div652.grevocab"
        // Android 15 is API 35. Targeting 35 is what the user asked for; minSdk
        // stays low because raising it would only exclude older phones for no gain.
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("VERSION_NAME") ?: "1.0"
    }

    signingConfigs {
        create("release") {
            val store = System.getenv("KEYSTORE_PATH")
            if (store != null) {
                storeFile = file(store)
                // Generated with OpenSSL rather than keytool, so it is PKCS12.
                // Java reads PKCS12 natively, but AGP infers the type from the
                // extension, so say it explicitly.
                storeType = "PKCS12"
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (System.getenv("KEYSTORE_PATH") != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // The 4 MB HTML is already one file; compressing it again buys nothing and
    // slows first paint.
    androidResources { noCompress += listOf("html") }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("androidx.core:core:1.13.1")
    implementation("androidx.activity:activity:1.9.3")
}
