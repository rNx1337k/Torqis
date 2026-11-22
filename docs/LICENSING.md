# Licensing

Torqis is licensed per workshop PC. Activation is **offline**: neither the workshop nor the vendor
needs an internet connection.

## How it works

- Each PC has an ID derived from the Windows machine GUID, shown in **Options → Licence** (e.g. `ABCD-EFGH-JKLM`).
- A licence key contains the workshop name, the PC ID, the issue date and an optional expiry date, signed with
  the vendor's **Ed25519 private key**. The app only contains the public key (`rad/license_pubkey.py`), so keys
  cannot be forged from the app.
- A new PC gets a **14-day trial** with everything unlocked, counted from the first start (the start date is kept
  in `%APPDATA%\Torqis\inicio.dat` and in `HKCU\Software\Torqis\Inicio`; the older of the two wins).
- After the trial, without a valid licence, the app runs in **demo mode**. It is enough to prove that the cable
  and the car talk to each other, not to work with:
  - it connects, identifies the modules and the Auto-Scan says which modules have faults and how many;
  - only the first **2 VAG faults** per reading are shown; the others appear as "hidden fault" (with their
    severity) on screen, in the report and in the history;
  - VAG measuring values run for **60 s per connection** to a module; no CSV logging and no guided tests;
  - nothing is written to a real vehicle (coding, adaptation, basic settings, clearing faults, output tests,
    service reset) and reports are marked as a demo version;
  - generic OBD-II reading and the simulator have no limits.
- The limits live in `rad/licensing.py` (`TRIAL_DAYS`, `FREE_FAULTS`, `FREE_LIVE_SECONDS`).
- While `PUBLIC_KEY` is `None` licensing is switched off (development builds).

> The check runs inside the app, so someone who modifies the program can bypass it. It controls normal
> distribution; it is not protection against determined copying. The Nuitka build makes this harder.

## Vendor workflow

1. **Once:** create the key pair.

   ```bat
   .venv\Scripts\python.exe tools\license_tool.py genkey
   ```

   The private key is written to `%USERPROFILE%\Torqis_licencas\private.key` (outside the repository;
   `*.key` is also in `.gitignore`; a key folder created before the rename, `%USERPROFILE%\RootsAutoDoctor_licencas`, is
   still used while the new one does not exist) and the public key to `rad/license_pubkey.py`. **Back up the private key**:
   without it you cannot issue new keys for this public key. The tool never overwrites an existing private key.
   Commit `rad/license_pubkey.py` and build a new release.

2. **For each workshop:** ask for the PC ID shown in Options → Licence and issue a key.

   **Licence window** (`tools\licencas.bat`, or the "Torqis - Licenças" desktop shortcut on the publisher's PC):
   - **Emitir licença:** paste the PC ID (checked as you type; if that PC already has a licence it says so and fills
     in the workshop), workshop name, contact (Instagram/phone/email), validity (1/3/6 months, 1 year, no end
     date, or a chosen date) and notes. **Gerar licença** creates the key, checks that the program accepts it and
     shows it with a ready-made message for the customer (key + how to activate) and copy buttons.
   - **Licenças emitidas:** every licence issued, newest first, with its status: *Activa*, *Sem fim*, *A acabar*
     (30 days or less, amber), *Expirada* (red) or *Substituída* (a newer key exists for the same PC). Search by
     workshop, PC ID, contact or notes; filter by status; copy the key or the message again; **Renovar…** issues a
     new key for the same PC, counting from the end of the current one if it has not ended yet (no days lost);
     edit contact/notes; open the register in Excel or open the folder.
   - The register is `licencas_emitidas.csv` next to the private key (columns `data;oficina;id_pc;expira;chave;
     contacto;notas`, UTF-8 with BOM so Excel shows accents; older 5-column files are still read). After every change
     it is copied to `D:\Torqis_copia_chaves` if that folder exists (`license_tool.BACKUP_DIRS`).
   - Without the private key, or with one that does not match `rad/license_pubkey.py`, the window refuses to
     issue and says why.

   Command line (the same functions and register):

   ```bat
   .venv\Scripts\python.exe tools\license_tool.py issue --machine ABCD-EFGH-JKLM --workshop "Oficina Silva"
   .venv\Scripts\python.exe tools\license_tool.py issue --machine ABCD-EFGH-JKLM --workshop "Oficina Silva" --expires 2027-12-31 --contact "@oficinasilva" --notes "beta"
   ```

   The key (starting with `RAD1-`) is printed and logged in `licencas_emitidas.csv` next to the private key.
   The workshop pastes it into Options → Licence → Activate licence.

3. **Changing PC:** the key is tied to the PC ID. Issue a new key for the new PC ID.

## Updates

The update check (Options → Updates) reads the latest GitHub release of the repository. To deliver a version to
workshops, publish a GitHub release for the tag and attach `Setup_Torqis_<version>.exe`; the app opens
the installer link. Without releases the app falls back to the highest version tag and opens the releases page.
If the repository is private, the check cannot see it and reports the GitHub error.
