package org.pybrainroot;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

/**
 * Most Java → Python w procesie :service_monitor.
 *
 * Odbiorca broadcastu (AppOpenReceiver) wkłada nazwę pakietu do kolejki
 * EVENTS, a pętla usługi Pythona czeka na zdarzenia przez
 * EVENTS.poll(timeout, TimeUnit) — natychmiastowe budzenie bez pollingu
 * (wątek Pythona śpi na monitorze kolejki, a nie odpyta w pętli).
 */
public final class AppOpenBridge {

    private AppOpenBridge() {
    }

    /** Kolejka zdarzeń „aplikacja weszła na pierwszy plan”. */
    public static final BlockingQueue<String> EVENTS =
            new LinkedBlockingQueue<String>();
}
