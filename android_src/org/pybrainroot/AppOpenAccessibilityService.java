package org.pybrainroot;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.ComponentName;
import android.content.Intent;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;

/**
 * Usługa dostępności: zdarzeniowe wykrywanie otwierania aplikacji.
 *
 * Dostaje TYPE_WINDOW_STATE_CHANGED dokładnie w momencie, gdy aplikacja
 * wchodzi na pierwszy plan — bez pollingu i bez kosztu baterii. Przy
 * włączonym monitoringu (monitor_config.json: enabled=true, targets
 * niepuste) wysyła jawny broadcast do odbiorcy w procesie :service_monitor,
 * gdzie zdarzenie trafia do kolejki mostu AppOpenBridge czytanej przez
 * pętlę Pythona. Dopasowanie pakietu do celów robi Python — dzięki temu
 * usługa Pythona zachowuje stan „aplikacja na pierwszym planie” również
 * przy zdarzeniach innych aplikacji (launcher, ustawienia).
 *
 * Konfiguracja usługi ustawiana programowo w onServiceConnected —
 * nie wymaga pliku res/xml ani meta-data w manifeście.
 */
public class AppOpenAccessibilityService extends AccessibilityService {

    private static final String TAG = "AppOpenService";
    private static final String CONFIG_NAME = "monitor_config.json";

    public static final String ACTION_APP_OPEN = "org.pybrainroot.APP_OPEN";
    public static final String EXTRA_PACKAGE = "pkg";
    public static final String RECEIVER_CLASS = "org.pybrainroot.AppOpenReceiver";

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        AccessibilityServiceInfo info = new AccessibilityServiceInfo();
        info.eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        info.flags = AccessibilityServiceInfo.DEFAULT;
        info.notificationTimeout = 100;
        setServiceInfo(info);
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        try {
            handleEvent(event);
        } catch (Exception e) {
            Log.w(TAG, "błąd obsługi zdarzenia", e);
        }
    }

    private void handleEvent(AccessibilityEvent event) {
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            return;
        }
        if (event.getPackageName() == null) {
            return;
        }
        String pkg = event.getPackageName().toString();
        if (pkg.isEmpty()) {
            return;
        }

        JSONObject cfg = readConfig();
        if (cfg == null || !cfg.optBoolean("enabled", false)) {
            return;
        }
        JSONArray targets = cfg.optJSONArray("targets");
        if (targets == null || targets.length() == 0) {
            return;
        }

        // jawny broadcast — trafia do odbiorcy w procesie :service_monitor
        // nawet wtedy, gdy aplikacja nie jest na pierwszym planie
        Intent intent = new Intent(ACTION_APP_OPEN);
        intent.setComponent(new ComponentName(getPackageName(), RECEIVER_CLASS));
        intent.putExtra(EXTRA_PACKAGE, pkg);
        sendBroadcast(intent);
    }

    /** Czyta monitor_config.json z getFilesDir (katalog współdzielony z usługą Pythona). */
    private JSONObject readConfig() {
        FileInputStream in = null;
        try {
            File file = new File(getFilesDir(), CONFIG_NAME);
            if (!file.exists()) {
                return null;
            }
            in = new FileInputStream(file);
            byte[] buf = new byte[(int) file.length()];
            int off = 0;
            while (off < buf.length) {
                int read = in.read(buf, off, buf.length - off);
                if (read <= 0) {
                    break;
                }
                off += read;
            }
            return new JSONObject(new String(buf, "UTF-8"));
        } catch (Exception e) {
            Log.w(TAG, "nie udało się przeczytać konfiguracji", e);
            return null;
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    @Override
    public void onInterrupt() {
        // nic do posprzątania — usługa jest bezstanowa
    }
}
