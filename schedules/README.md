# Encrypted shared schedules

The Android app submits an encrypted appointment to a GitHub Issue in tyuio7777/hunt-briefing-guestbook with the existing guestbook user's GitHub session. Edits and cancellations update the original Issue. The publish-shared-schedules workflow reads that public inbox every five minutes, validates the Issue number, GitHub author, event ID and version, and publishes changes under `channels/<sha256-of-normalized-code>.json`.

The app reads registered channels and decrypts appointments on the device. Titles, descriptions and appointment times are encrypted. The source Issue exposes the author's GitHub identity and operational metadata. Share codes, tokens, subscriber lists and private appointments are never placed in these files.

Appointments expire six calendar months after registration in Korea Standard Time. The daily cleanup workflow prunes expired records and empty channel files. The guestbook repository separately closes expired Issues and removes ciphertext from their current bodies. Git and Issue edit history can retain previous ciphertext. Background publication and device notification delivery depend on GitHub Actions and Android scheduling.
