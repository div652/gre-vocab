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
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.webkit.WebViewAssetLoader;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;

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
 */
public class MainActivity extends AppCompatActivity {

    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final String START_URL = ORIGIN + "/assets/flashcards.html";

    private WebView web;
    private ValueCallback<Uri[]> filePicker;
    private static final int PICK_FILE = 1001;

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
                return loader.shouldInterceptRequest(req.getUrl());
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

    private class Bridge {
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
