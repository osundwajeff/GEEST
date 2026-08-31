# GEOE3 Plugin Release Process

## Quick Release Steps

### 1. Update Version in config.json

Before releasing, add a new `Version X.Y.Z - <title>` block at the top of
`docs/plugin/changelog.txt` mirroring the `CHANGELOG.md` `[Unreleased]`
entries — `admin.py` bakes this file (not `CHANGELOG.md`) into the plugin
`metadata.txt` shown in the QGIS Plugin Manager.

Edit `config.json`:

```json
{
  "general": {
    "version": "1.2.3",
    ...
  }
}
```

### 2. Commit and Push Changes

Commit, push and merge changes upstream.

### 3. Pull Latest Changes

Pull latest changes through git.

### 4. Create and Push Tag

```bash
# Create tag (must start with 'v')
git tag -a v1.2.3 -m "Release version 1.2.3"

# Push tag
git push origin v1.2.3
```

### 5. Automated Build

Pushing the tag automatically triggers `.github/workflows/release.yml` which:

- Creates GitHub release
- Generates plugin ZIP
- Uploads ZIP to release
- Updates plugin repository XML

### 6. Verify

Check release at: https://github.com/worldbank/GEOE3/releases

---
