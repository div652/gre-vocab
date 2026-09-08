package dev.div652.grevocab;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.IntentSenderRequest;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.webkit.WebViewAssetLoader;

import com.google.android.gms.auth.api.identity.AuthorizationRequest;
import com.google.android.gms.auth.api.identity.AuthorizationResult;
import com.google.android.gms.auth.api.identity.Identity;
import com.google.android.gms.common.api.Scope;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Collections;

/**
 * A thin shell around the same self-contained flashcards.html that the web app
 * serves. The HTML is bundled in assets/, so the app never touches the network.
 *
 * Two details are load-bearing:
 *
 * 1. Assets are served through WebViewAssetLoader on an https:// origin rather
 *    than loaded as file:///android_asset/. localStorage on a file:// origin is
 *    unreliable across WebView versions, and localStorage is where the user's
 *    difficulty marks live - losing them would be the whole point of the app.
 *
 * 2. Export uses a JS bridge. A blob: download inside a WebView is silently
 *    dropped by DownloadManager, so the web build calls AndroidBridge.saveText
 *    when it is present and falls back to a blob elsewhere.
 *
 * 3. Sign-in cannot use the web flow. Google rejects OAuth inside an embedded
 *    WebView (disallowed_useragent), and custom URI schemes are no longer
 *    accepted for Android OAuth clients, which closes the Custom Tabs route
 *    too. Play Services authorizes natively and hands the token to the page.
 *    Nothing identifies the app in code - Google matches it by package name
 *    plus signing certificate, registered as an Android OAuth client.
 */
public class MainActivity extends AppCompatActivity {

    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final String START_URL = ORIGIN + "/assets/flashcards.html";

    /** The only hosts the WebView may reach. Everything else - web fonts, the
     *  Google sign-in script the browser build uses - is refused.
     *
     *  i.ytimg.com serves the iswearenglish thumbnails on each card. It is the
     *  one entry a guest can trigger without signing in, and it was added
     *  deliberately: bundling 1116 thumbnails would have added 23 MB to a
     *  5.9 MB app. They load lazily and fail to a text label offline. */
    private static final String[] NET_ALLOW = {
            "https://www.googleapis.com/",
            "https://oauth2.googleapis.com/",
            "https://i.ytimg.com/",
    };

    private static final String DRIVE_APPDATA = "https://www.googleapis.com/auth/drive.appdata";

    private WebView web;
    private ValueCallback<Uri[]> filePicker;
    private static final int PICK_FILE = 1001;
    private ActivityResultLauncher<IntentSenderRequest> authLauncher;

    @Override
    protected void onCreate(@Nullable Bundle saved) {
        super.onCreate(saved);

        // Apps targeting SDK 35 are edge-to-edge by default on Android 15, so
        // without this the header slides under the status bar.
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        web = new WebView(this);
        setContentView(web);
        ViewCompat.setOnApplyWindowInsetsListener(web, (v, windowInsets) -> {
            Insets bars = windowInsets.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage - the difficulty marks
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setTextZoom(100);

        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .setDomain("appassets.androidplatform.net")
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                String s = u.toString();
                if (s.startsWith(ORIGIN)) return loader.shouldInterceptRequest(u);
                for (String ok : NET_ALLOW) {
                    if (s.startsWith(ok)) return null;      // null = let it through
                }
                // Refused rather than fetched. The page is one self-contained
                // file; anything else it references is optional decoration.
                return new WebResourceResponse("text/plain", "utf-8", 204, "Blocked",
                        Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (u.toString().startsWith(ORIGIN)) return false;
                // Anything genuinely external opens in a real browser.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (Exception ignored) {
                }
                return true;
            }
        });

        // Import uses an <input type="file">, which needs this to open a picker.
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb,
                                             FileChooserParams params) {
                if (filePicker != null) filePicker.onReceiveValue(null);
                filePicker = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "Select difficulty.json"), PICK_FILE);
                    return true;
                } catch (Exception e) {
                    filePicker = null;
                    return false;
                }
            }
        });

        // Consent, when it is needed, arrives as a PendingIntent to launch.
        authLauncher = registerForActivityResult(
                new ActivityResultContracts.StartIntentSenderForResult(), result -> {
                    try {
                        AuthorizationResult r = Identity.getAuthorizationClient(this)
                                .getAuthorizationResultFromIntent(result.getData());
                        deliverToken(r.getAccessToken(), null);
                    } catch (Exception e) {
                        deliverToken(null, msg(e, "sign-in cancelled"));
                    }
                });

        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        web.loadUrl(START_URL);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (web.canGoBack()) web.goBack();
                else finish();
            }
        });
    }

    @Override
    protected void onActivityResult(int req, int res, @Nullable Intent data) {
        super.onActivityResult(req, res, data);
        if (req != PICK_FILE || filePicker == null) return;
        Uri[] out = null;
        if (res == Activity.RESULT_OK && data != null && data.getData() != null) {
            out = new Uri[]{data.getData()};
        }
        filePicker.onReceiveValue(out);
        filePicker = null;
    }

    /** Ask Play Services for a Drive appdata token, prompting only if needed. */
    private void startAuthorize() {
        AuthorizationRequest req = AuthorizationRequest.builder()
                .setRequestedScopes(Arrays.asList(
                        new Scope(DRIVE_APPDATA), new Scope("email"), new Scope("profile")))
                .build();
        Identity.getAuthorizationClient(this).authorize(req)
                .addOnSuccessListener(r -> {
                    if (r.hasResolution() && r.getPendingIntent() != null) {
                        try {
                            authLauncher.launch(new IntentSenderRequest.Builder(
                                    r.getPendingIntent().getIntentSender()).build());
                        } catch (Exception e) {
                            deliverToken(null, msg(e, "could not open the consent screen"));
                        }
                    } else {
                        deliverToken(r.getAccessToken(), null);   // already granted
                    }
                })
                .addOnFailureListener(e -> deliverToken(null, msg(e, "sign-in failed")));
    }

    /** Hand the result to the page, which then behaves exactly as on the web. */
    private void deliverToken(@Nullable String token, @Nullable String error) {
        JSONObject o = new JSONObject();
        try {
            if (token != null) o.put("access_token", token);
            if (error != null) o.put("error", error);
        } catch (Exception ignored) {
        }
        final String js = "window.__androidAuth && window.__androidAuth(" + o + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }

    private static String msg(Exception e, String fallback) {
        return e.getMessage() == null || e.getMessage().isEmpty() ? fallback : e.getMessage();
    }

    private class Bridge {
        /** Called by the page's "Sign in with Google" button. */
        @JavascriptInterface
        public void signIn() {
            runOnUiThread(MainActivity.this::startAuthorize);
        }

        /** Write exported marks somewhere the user can actually find them. */
        @JavascriptInterface
        public void saveText(String name, String content) {
            try {
                File dir = getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
                if (dir == null) dir = getFilesDir();
                if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("mkdirs failed");
                File f = new File(dir, name);
                try (OutputStreamWriter w = new OutputStreamWriter(
                        new FileOutputStream(f), StandardCharsets.UTF_8)) {
                    w.write(content);
                }
                toast("Saved to " + f.getAbsolutePath());
            } catch (Exception e) {
                toast("Save failed: " + e.getMessage());
            }
        }
    }

    private void toast(final String msg) {
        runOnUiThread(() -> Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show());
    }
}
