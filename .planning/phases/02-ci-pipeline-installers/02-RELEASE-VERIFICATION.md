# Release Verification Guide

How to verify that the GitHub Actions release workflow produces installer artifacts
before committing to a real release.

## Decision: No Apple Developer Account

macOS builds will produce **unsigned .dmg files**. Gatekeeper will show a warning on
first open, which users can bypass via System Settings > Privacy & Security > Open Anyway.

Signed macOS builds can be added later by enrolling in Apple Developer Program ($99/year)
and wiring the secrets listed in the Appendix below.

## GitHub Actions Workflow Permissions

Before pushing a tag, ensure the workflow has permission to create releases:

1. Go to: GitHub repo > **Settings** > **Actions** > **General**
2. Scroll to "Workflow permissions"
3. Select **Read and write permissions**
4. Click **Save**

This allows the workflow to create draft releases and upload assets.

## Test Tag Push — Step-by-Step

When you are ready to verify the end-to-end flow, run these commands from the
root of the repository on the branch you want to release from (typically `main`):

```bash
# 1. Create the test tag
git tag v0.1.0-rc.1

# 2. Push the tag to GitHub (this triggers the "Release Desktop App" workflow)
git push origin v0.1.0-rc.1
```

### What to expect

| Step | Location | Expected result |
|------|----------|-----------------|
| Workflow triggered | GitHub > Actions tab | "Release Desktop App" workflow appears within ~30 s |
| Build duration | GitHub > Actions tab | 15–30 min on first run (Nuitka compilation is slow) |
| Matrix jobs | GitHub > Actions tab | 4 jobs: macos-14 (arm64), macos-13 (x86_64), ubuntu-22.04, windows-latest |
| Draft release created | GitHub > Releases | Draft named "Mageflow Viewer v0.1.0-rc.1" |

### Artifacts to verify

Check that the draft release contains:

- [ ] macOS arm64: `Mageflow Viewer_*_aarch64.dmg`
- [ ] macOS x86_64: `Mageflow Viewer_*_x64.dmg`
- [ ] Linux: `mageflow-viewer_*_amd64.deb` and/or `mageflow-viewer_*_amd64.AppImage`
- [ ] Windows: `Mageflow Viewer_*_x64-setup.exe` or `.msi`

A partial success (at least Linux) is acceptable for initial verification.

### macOS DMG — first-launch warning

Because the DMG is unsigned, Gatekeeper will show:

> "Mageflow Viewer" cannot be opened because it is from an unidentified developer.

Users bypass this via:
1. Right-click the app > **Open** > **Open** (first time only), or
2. System Settings > **Privacy & Security** > scroll down > **Open Anyway**

### Cleanup after verification

```bash
# Delete the test tag locally
git tag -d v0.1.0-rc.1

# Delete it from GitHub
git push origin --delete v0.1.0-rc.1
```

Also delete the draft release from GitHub UI:
GitHub > Releases > find the draft > "Delete release"

## Appendix: macOS Signing Secrets (for future use)

If you later enroll in Apple Developer Program, add these to
GitHub repo > Settings > Secrets and variables > Actions > New repository secret:

| Secret name | How to get the value |
|-------------|----------------------|
| `APPLE_CERTIFICATE` | Export "Developer ID Application" cert from Keychain Access as .p12, then `base64 -i cert.p12 \| pbcopy` |
| `APPLE_CERTIFICATE_PASSWORD` | Password you chose when exporting the .p12 |
| `APPLE_SIGNING_IDENTITY` | Full cert name, e.g. `Developer ID Application: Your Name (TEAMID)` |
| `APPLE_ID` | Your Apple Developer account email |
| `APPLE_PASSWORD` | App-specific password from https://appleid.apple.com > Sign-In and Security > App-Specific Passwords |
| `APPLE_TEAM_ID` | 10-character Team ID from https://developer.apple.com/account > Membership Details |
| `KEYCHAIN_PASSWORD` | Any random strong password — used only for the ephemeral CI keychain |

## Appendix: Windows Signing (deferred to v1.1)

Azure Trusted Signing secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_CLIENT_SECRET`) are already wired as empty placeholders in the workflow.
The `signCommand` is not yet active. Windows ships unsigned for v1.0.
