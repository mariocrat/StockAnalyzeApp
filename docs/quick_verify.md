# AlphaMate Quick Verification

Run this from the project root before committing or before asking someone else
to continue the work:

```cmd
verify_project.bat
```

You can also double-click `verify_project.bat` in the project folder. The batch
file calls the PowerShell script with the correct project path, so it works from
Command Prompt without having to remember the long command.

The script checks:

- Backend tests
- Backend compile
- Tracked secret scan
- Frontend release-env tests
- Frontend Android branding tests
- Frontend mobile billing tests
- Frontend mobile AdMob tests
- Frontend client event tests
- Frontend API error request ID tests
- Frontend AI idempotency tests
- Frontend lint
- Frontend production build

To also confirm the Android wrapper and debug APK build, run this from the
project root:

```cmd
verify_android_debug.bat
```

That heavier check runs `npm run mobile:build`, syncs Capacitor assets into the
Android project, and builds `frontend/android/app/build/outputs/apk/debug/app-debug.apk`.

This is a local development quality check. Production release environment checks
that require real server secrets still need the backend and frontend release
checks described in `docs/manual_test_guide.md`.
