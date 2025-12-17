[app]
title = Smart File Organizer
package.name = smartfileorganizer
package.domain = org.bishal

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg

version = 0.1

requirements = python3,kivy,kivymd

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools_version = 33.0.2

android.allow_backup = True
android.private_storage = False
