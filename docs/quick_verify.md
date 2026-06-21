# AlphaMate Quick Verification

Run this from the project root before committing or before asking someone else
to continue the work:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1
```

The script checks:

- backend unittest suite
- backend Python compile check
- frontend release environment tests
- Android branding tests
- mobile AdMob policy tests
- frontend lint
- frontend production build

This is a local development quality check. Production release environment checks
that require real server secrets still need the backend and frontend release
checks described in `docs/manual_test_guide.md`.
