
# (str) Title of your application
 title = Sakura Project

# (str) Package name
 package.name = sakura

# (str) Package domain (needed for android/ios packaging)
 package.domain = org.sakura

# (str) Source code where main.py live
 source.dir = .

# (list) List of source files to include
 source.include_exts = py,png,jpg,kv,atlas

# (str) Application version
 version = 0.1

# (list) Application requirements
 requirements = python3,kivy

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
 orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
 fullscreen = 0

# (list) List of service to declare
 #services = NAME:ENTRYPOINT_TO_PY,NAME2:ENTRYPOINT2_TO_PY

# (list) Permissions
 android.permissions = INTERNET

# (int) Target Android API, default is 27
 android.api = 33

# (int) Minimum API required
 android.minapi = 21

# (str) Android NDK version
 android.ndk = 23.1.7779620

# (bool) Accept Android SDK license automatically
 android.accept_sdk_license = True

[buildozer]

# (int) Log level (0 = error only, 1 = error + warning, 2 = error + warning + info, 3 = debug)
 log_level = 2

# (int) Warn on root, default is 1
 warn_on_root = 1
