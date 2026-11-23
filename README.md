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
| `stories/<code>.json` | The stories on the app's Insights tab, one file per language (see below) |
| `stories/images/` | Pictures for those stories, shared by every language |
| `stories/animations/` | Lottie animations for those stories, shared by every language |

After changing anything:

```sh
node scripts/validate.mjs && node scripts/validate-config.mjs && node scripts/validate-stories.mjs && node scripts/build-manifest.mjs
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

## Stories (Insights tab)

The Insights tab lists short reads about taking medicines well. They all live here (nothing is built into the app), so stories and pictures can be added or changed with a push, no app release. Until a phone has downloaded them once, the tab shows "No insights found" with a retry.

`stories/<code>.json`:

```json
{
  "schemaVersion": 1,
  "stories": [
    {
      "id": "on-time",
      "category": "Health",
      "title": "Why taking medicine on time matters",
      "summary": "One or two lines for the list.",
      "image": "stories/images/on-time.webp",
      "animation": "stories/animations/on-time.json",
      "readMinutes": 3,
      "featured": true,
      "body": [
        { "type": "paragraph", "text": "…" },
        { "type": "heading", "text": "…" },
        { "type": "tip", "text": "…" },
        { "type": "list", "items": ["…", "…"] },
        { "type": "image", "src": "stories/images/glass.webp", "caption": "…" }
      ],
      "source": { "label": "NHS", "url": "https://www.nhs.uk/…" }
    }
  ]
}
```

- Order in the file is the order in the app. `featured` stories show first as big cards; the rest as a list.
- `id`: lowercase letters, digits and dashes; the same in every language.
- `image` / `src`: a path in this repo (`stories/images/…`, `.webp`, `.png` or `.jpg`, at most 400 KB; about 800×480 WebP works well) or a full `https://` link.
- A language without its own file, or without one of the stories, shows the English story. `stories/en.json` is required.
- `animation` (optional): a Lottie file (`stories/animations/…json`, at most 150 KB, or an `https://` link) that plays in place of the picture on the list and the story page: a short loop showing what the story is about. The app downloads it with the stories, keeps it for offline use and downloads it again when the file changes. Until it's downloaded, or if it's broken, the picture shows, so keep `image` too. The animations and pictures come from `python3 scripts/make-story-art.py` (edit a scene there and run it; see its header for turning the pictures into WebP), but any Lottie file works, e.g. one exported from After Effects or downloaded from LottieFiles.
- Unknown block types are skipped by the app, so new ones can be added later without breaking older builds.

### Ads in stories

`{ "type": "ad" }` puts an ad (a Google inline banner, labelled "Advertisement") where the tag is:

- **Inside a story**, as a body block: in the middle, at the bottom, or several in a long story.
  ```json
  "body": [
    { "type": "paragraph", "text": "…" },
    { "type": "ad" },
    { "type": "paragraph", "text": "…" },
    { "type": "ad" }
  ]
  ```
- **In the list**, as an entry between stories: the ad shows after the story before it.
  ```json
  "stories": [
    { "id": "on-time", … },
    { "id": "breakfast", … },
    { "type": "ad" },
    { "id": "lunch", … }
  ]
  ```

The app keeps it reasonable whatever the file says: at most 3 ads per story and 2 in the list, never two in a row, never before the first text. No ads while the user has ad-free time, and nothing (no gap) when an ad doesn't load. A language without list ads uses the English file's. `validate-stories.mjs` warns about tags the app will ignore. Older app builds skip the tags.

To add or change a story:

1. Edit `stories/en.json` (and the other languages), add any picture to `stories/images/`.
2. Check it: `node scripts/validate-stories.mjs`
3. Update the manifest: `node scripts/build-manifest.mjs`
4. Commit and push. Phones download the changed files the next time the app opens (or on pull to refresh on the Insights tab) and keep them, pictures included, for offline use.
