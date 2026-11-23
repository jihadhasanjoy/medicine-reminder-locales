# medicine-reminder-locales

Translations and remote config for the Medicine Reminder app
(jihadhasanjoy/MedicineReminder). Phones download them at launch, so
texts, new languages and update rules change without an app release.

**Two branches:** the store app's release builds read `main`; the test app
(`com.dropwise.medicinereminder.test`) and every debug build read `dev`.
Try changes on `dev`, then merge to `main` to reach users.

## Files

| File | What |
|---|---|
| `locales/<code>.json` | App texts; `en` is the source, every key in every language |
| `languages.json` | Languages offered (`code`, `nativeName`, `rtl`, `script`: latin, indic, arabic, cjk) |
| `manifest.json` | Version and file hashes; rebuild after every change |
| `app-config.json` | Update rules, store links and ad settings (below) |

After changing anything:

```sh
node scripts/validate.mjs && node scripts/validate-config.mjs && node scripts/build-manifest.mjs
```

A new language needs no app release: add `locales/<code>.json` and its
entry in `languages.json`.

## app-config.json

| Field | Meaning |
|---|---|
| `adFreeTrialDays` | Days without ads for a new user (0: the welcome offers a video instead) |
| `rewardedAdFreeHours` | Hours without ads per watched video (0: no video offer) |
| `minVersion` | Older than this (`"1.2.0"` or `"1.2.0-7"`): Update required |
| `latestVersion` | Older than this: a "new version" sheet on each launch |
| `storeUrlProd` | Store app: where Update now goes (keep `storeUrl` the same) |
| `storeUrlDev` | Test app: its Firebase App Distribution invite link |
| `bannerUnit`, `rewardedUnit` | AdMob units of the app's own account; empty: built-in or test ads |
