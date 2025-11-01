# UUID7 Package Fix Documentation

## The Problem

### What Was Happening

When deploying or updating the Raspberry Pi client, the setup script would fail with:
```
❌ Some dependencies failed verification.
  ✗ uuid7 - FAILED
```

Even though the package appeared to be installed:
```bash
pip list | grep uuid7
# uuid7  0.1.0
```

The Python import would still fail:
```python
import uuid7  # ModuleNotFoundError
```

### Root Cause

There were **two different packages** that provide UUID7 functionality:

1. **`uuid6` package (v2024.1.12+)** - The official, maintained package
   - Provides UUID7 via: `from uuid6 import uuid7`
   - Used by the server code
   - Reliable and well-maintained

2. **`uuid7` package (v0.1.0)** - A separate, less maintained package
   - Attempts to provide: `import uuid7`
   - Has import issues on some systems
   - Was incorrectly specified in client requirements.txt

### The Mismatch

**Server code** (correct):
```bash
pip install uuid6
python3 -c "from uuid6 import uuid7; print(str(uuid7()))"
```

**Client code** (incorrect):
```bash
pip install uuid7  # Wrong package!
python3 -c "import uuid7"  # Fails to import
```

**Python code** (incorrect):
```python
import uuid7  # Should be: from uuid6 import uuid7
```

## The Solution

### Changes Made

#### 1. Fixed Requirements Files

**pi_client/requirements.txt**:
```diff
- uuid7>=0.1.0
+ uuid6>=2024.1.12  # Provides uuid7 functionality
```

**server/requirements.txt**:
```diff
- uuid7>=0.1.0
+ uuid6>=2024.1.12  # Provides uuid7 functionality
```

#### 2. Fixed Python Imports

**pi_client/device_manager.py**:
```diff
- import uuid7
+ from uuid6 import uuid7
```

#### 3. Fixed Setup Script

**pi_client/deploy/setup.sh**:
```diff
- "$VENV_DIR/bin/pip" install --no-cache-dir --ignore-installed --no-deps uuid7
+ "$VENV_DIR/bin/pip" install --no-cache-dir --ignore-installed --no-deps uuid6
```

```diff
- DEPS_TO_CHECK="uuid7 supabase pytz realtime requests dotenv opuslib numpy pyaudio gpiozero"
+ DEPS_TO_CHECK="uuid6 supabase pytz realtime requests dotenv opuslib numpy pyaudio gpiozero"
```

#### 4. Added Virtual Environment Rebuild Option

**pi_client/deploy/setup.sh** - New feature:
- Detects existing virtual environments
- Offers option to rebuild venv from scratch for updates
- Prevents stale package conflicts

```bash
Options:
  1) Keep existing venv and update packages (faster)
  2) Delete and rebuild venv from scratch (recommended for updates)
```

#### 5. Updated Documentation

**pi_client/deploy/pi_deploy.md**:
- Added guidance on when to rebuild venv
- Clarified update strategy (minor vs major updates)
- Explained benefits of rebuilding venv

## How to Apply This Fix

### If You're Experiencing the Error Now

1. **SSH to your Raspberry Pi**:
   ```bash
   ssh user@raspberrypi.local
   ```

2. **Pull the latest code** (includes the fix):
   ```bash
   cd /tmp
   rm -rf javia
   git clone https://github.com/shreyashguptas/javia.git
   cd javia
   ```

3. **Run the setup script**:
   ```bash
   bash pi_client/deploy/setup.sh
   ```

4. **When prompted**, choose **option 2** to rebuild the venv:
   ```
   Choose option [1-2] (default: 1): 2
   ```

5. **Verify the fix**:
   ```bash
   # Check service is running
   sudo systemctl status voice-assistant-client.service
   
   # Verify uuid6 is installed (not uuid7)
   ~/venvs/pi_client/bin/pip list | grep uuid
   # Should show: uuid6  2024.1.12
   ```

### For New Installations

The fix is already included. Just follow the normal installation instructions in `pi_client/deploy/pi_deploy.md`.

## Why This Matters

### Package Ecosystem Context

In the Python UUID space:
- **`uuid`** (built-in) - Provides UUID1, UUID3, UUID4, UUID5
- **`uuid6`** (PyPI) - Extends built-in with UUID6, UUID7, UUID8
- **`uuid7`** (PyPI) - Alternative implementation (less maintained)

The `uuid6` package is the official, recommended way to use UUID7 in Python.

### Impact on the System

UUID7 is used for:
- **Device registration**: Each Pi client gets a unique UUID7 identifier
- **Update tracking**: Device updates are tracked by UUID
- **API authentication**: Device identity verification

Without this fix:
- ❌ Device registration would fail
- ❌ OTA updates would not work
- ❌ Device tracking would be broken
- ❌ Service would fail to start

## Prevention for Future

### Best Practices

1. **Always specify exact package names** in requirements.txt
2. **Test imports** after package installation
3. **Use the same packages** across server and client
4. **Document package sources** (e.g., `# Provides uuid7 functionality`)
5. **Rebuild venvs** during major updates to prevent conflicts

### For Developers

When adding UUID functionality to new code:

✅ **Correct**:
```python
from uuid6 import uuid7

device_id = str(uuid7())
```

❌ **Incorrect**:
```python
import uuid7  # Don't use the uuid7 package

device_id = str(uuid7.uuid7())
```

### Requirements Template

Always use:
```txt
# UUID generation (provides UUID7)
uuid6>=2024.1.12
```

Never use:
```txt
# Don't use this!
uuid7>=0.1.0
```

## Verification Checklist

After applying the fix, verify:

- [ ] `uuid6` package is installed (not `uuid7`)
- [ ] Python can import: `from uuid6 import uuid7`
- [ ] Device manager can generate UUIDs
- [ ] Service starts successfully
- [ ] No import errors in logs

## References

- **UUID6 Package**: https://pypi.org/project/uuid6/
- **UUID7 Specification**: https://datatracker.ietf.org/doc/html/draft-ietf-uuidrev-rfc4122bis
- **Our Deployment Docs**: [pi_deploy.md](../pi_client/deploy/pi_deploy.md)

## Related Issues

This fix resolves:
- Import errors for uuid7
- Virtual environment package conflicts
- Stale package issues during updates
- Inconsistency between server and client dependencies

