"""Hook p4a — wstrzykuje deklaracje komponentów do AndroidManifest.xml.

p4a renderuje manifest z szablonu, ale `android.extra_manifest_xml` ląduje
na poziomie <manifest> (przed <application>), a <service>/<receiver> muszą
być dziećmi <application>. Hook `after_apk_build` modyfikuje wygenerowany
manifest — w tym momencie p4a już go wyrenderowało (make_package), a gradle
jeszcze nie rozpoczął budowy APK.

Idempotentny — przy ponownym buildzie z cache'owanym distem wpisy nie są
duplikowane.
"""
from pathlib import Path

_MARKERS = (
    "org.pybrainroot.AppOpenAccessibilityService",
    "org.pybrainroot.AppOpenReceiver",
)

_APPLICATION_ENTRIES = """\
    <service
        android:name="org.pybrainroot.AppOpenAccessibilityService"
        android:label="PyBrainRoot"
        android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
        android:exported="true">
        <intent-filter>
            <action android:name="android.accessibilityservice.AccessibilityService" />
        </intent-filter>
    </service>

    <receiver
        android:name="org.pybrainroot.AppOpenReceiver"
        android:exported="false"
        android:process=":service_monitor" />
"""


def after_apk_build(toolchain) -> None:
    """Dodaje usługę dostępności i receiver do <application> w manifeście."""
    manifest = (
        Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"
    )
    content = manifest.read_text(encoding="utf-8")
    if all(marker in content for marker in _MARKERS):
        return  # wpisy już obecne (cache'owany dist z poprzedniego buildu)
    if "</application>" not in content:
        raise SystemExit("[p4a-hook] brak </application> w AndroidManifest.xml")
    manifest.write_text(
        content.replace("</application>", _APPLICATION_ENTRIES + "</application>"),
        encoding="utf-8",
    )
    print("[p4a-hook] dodano service/receiver do AndroidManifest.xml")
