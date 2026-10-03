package org.pybrainroot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Odbiorca zdarzeń otwarcia aplikacji — działa w procesie :service_monitor
 * (android:process w manifeście), więc może włożyć pakiet do statycznej
 * kolejki mostu, na której blokuje się pętla Pythona usługi.
 */
public class AppOpenReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        String pkg = intent.getStringExtra(AppOpenAccessibilityService.EXTRA_PACKAGE);
        if (pkg != null && !pkg.isEmpty()) {
            AppOpenBridge.EVENTS.offer(pkg);
        }
    }
}
