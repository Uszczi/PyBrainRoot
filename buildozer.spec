[app]

title = PyBrainRoot
package.name = pybrainroot
package.domain = org.pybrainroot

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy==2.3.1

android.permissions = PACKAGE_USAGE_STATS,QUERY_ALL_PACKAGES,SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE,POST_NOTIFICATIONS,KILL_BACKGROUND_PROCESSES

services = monitor:src/pybrainroot/service/monitor_service.py:foreground:sticky:foregroundServiceType=specialUse

android.add_src = android_src

p4a.hook = p4a_hook.py

orientation = portrait

fullscreen = 0

android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

icon.filename = %(source.dir)s/static/icon.png

log_level = 2
warn_on_root = 1

android.logcat_filters = *:S python:V monitor:V

[buildozer]
log_level = 2

[buildozer_python]
python_version = 3
