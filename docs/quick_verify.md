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
