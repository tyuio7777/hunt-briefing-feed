# Encrypted shared schedules

`channels/<sha256-of-code>.json` contains AES-256-GCM ciphertext and opaque ownership metadata only.
Share codes, creator credentials, GitHub tokens, FCM tokens, schedule titles, descriptions and appointment times must never be committed here.

The Android app decrypts only a registered code's channel. Personal appointments never enter this folder.
The existing proxy's `/schedules/v1/write` route validates a separate device creator credential, optimistic version and operation ID before committing a record. Knowledge of the share code does not grant permission to replace or delete an existing record.

Records become invisible at creation time + 6 calendar months (KST). The daily cleanup workflow removes expired current records and empty channel files. Git history and third-party copies can retain ciphertext: this is not a guarantee of irreversible erasure. GitHub may delay a scheduled run or disable an inactive public repository's schedule after 60 days; client-side expiry remains enforced.

Only schedule files are managed here. Official feed content, reference data and other scheduled tasks remain independent.
