# Processed data schema

Three files, all written by the pipeline into `data/processed/`. None are edited by hand.

```
clean.py     raw  ->  chart_entries.csv, songs.csv
features.py  songs.csv  ->  songs_features.csv
```

`songs_features.csv` is the table to analyse. `songs.csv` is the same thing without the
engineered columns, kept separate so a bad feature rule cannot spoil a good cleaning run.

The reasoning behind every rule mentioned here is in [cleaning-decisions.md](cleaning-decisions.md).

---

## chart_entries.csv

One row per song per chart week. 327,895 rows, 1958-08-02 to 2021-05-29.

| Column | Type | Notes |
|---|---|---|
| `song_id` | str | title and performer concatenated; the join key |
| `song` | str | title |
| `performer` | str | artist, as Billboard credits them |
| `chart_date` | date | the chart week |
| `position` | int | 1–100, lower is better |
| `instance` | int | which separate chart run this row belongs to; 1 is the original |
| `chart_year` | int | year of `chart_date` |

Every row in the source survives, including the 26 rows where one song holds two positions in a
week and the 58 rows where two songs tie on a rank. `(song_id, chart_date)` is therefore *not*
unique — 13 pairs repeat.

The source `peak_position`, `weeks_on_chart`, `previous_week_position`, `week_id` and `url`
columns are not carried through; the first two are recomputed in `songs.csv`, and the rest are
either reconstructible or superseded.

---

## songs.csv / songs_features.csv

One row per song, 29,389 rows, unique on `song_id`. `songs_features.csv` is `songs.csv` plus
the last block below.

### Identity

| Column | Type | Notes |
|---|---|---|
| `song_id` | str | title and performer concatenated |
| `song`, `performer` | str | readable names |

### Chart history

Computed from the weekly rows, never copied from the source.

| Column | Type | Notes |
|---|---|---|
| `first_observed_chart_date` | date | first week on the chart |
| `last_observed_chart_date` | date | last week on the chart |
| `first_observed_year` | int | year of the first chart date |
| `observed_chart_weeks` | int | count of **distinct** chart dates, so a song holding two positions in one week counts once |
| `best_observed_rank` | int | lowest position number reached |
| `observed_top10_weeks` | int | distinct weeks at position 10 or better; 0 for songs that never got there |
| `n_runs` | int | separate chart runs; "Jingle Bell Rock" has 9 |
| `spans_decades` | bool | charted in more than one decade; true for 785 songs |

"Observed" is meant literally: the dataset starts when the Hot 100 does but ends 2021-05-29, so
a song still charting that week has a truncated history.

### Spotify measurements

Joined from the audio file, one row per song. Missing for 17.4% of songs, and missing far more
often for older ones — see coverage below.

| Column | Type | Notes |
|---|---|---|
| `spotify_track_id` | str | the matched recording |
| `spotify_track_duration_ms` | float | of the matched recording, which is not always the version that charted |
| `spotify_track_explicit` | bool | nullable; missing means no match, not "clean" |
| `spotify_track_popularity` | float | 0–100, streams **today**, not chart success |
| `spotify_genre` | str | a list stored as text, e.g. `"['rock', 'pop']"`; artist-level |
| `danceability`, `energy`, `valence`, `acousticness`, `instrumentalness`, `liveness`, `speechiness` | float | 0–1 |
| `loudness` | float | dB, typically −30 to 0 |
| `tempo` | float | BPM |
| `mode`, `time_signature` | float | stored as float because they can be missing |

### Quality flags

| Column | Type | Notes |
|---|---|---|
| `audio_row_matched` | bool | an audio row exists for this song |
| `eda_core_complete` | bool | danceability, energy, valence and acousticness are all present |

Audio coverage by decade of first charting, printed by `clean.py` on every run:

| Decade | Songs | With audio |
|---|---|---|
| 1950s | 925 | 65.9% |
| 1960s | 6,850 | 76.3% |
| 1970s | 5,299 | 79.5% |
| 1980s | 4,113 | 85.4% |
| 1990s | 3,423 | 82.1% |
| 2000s | 3,418 | 91.8% |
| 2010s | 4,446 | 94.3% |
| 2020–21 | 915 | 63.4% |

Anything grouped by decade is comparing better-covered recent songs with patchier older ones.

### Engineered features (`songs_features.csv` only)

Unlike the columns above, these are choices. Each is a constant at the top of `features.py`.

| Column | Type | Notes |
|---|---|---|
| `decade` | int | 1950, 1960, …, from the first chart year. 2020 is 1.5 years, not a decade |
| `streaming_era` | bool | first charted on or after 2007-08-11, Billboard's first inclusion of streaming |
| `duration_minutes` | float | `spotify_track_duration_ms / 60000` |
| `mood` | str | `happy/energetic`, `happy/calm`, `sad/energetic`, `sad/calm`, split at 0.5 on valence and energy; missing where either is missing |
| `n_genre_labels` | int | how many Spotify labels the song carries |
| `has_genre` | bool | at least one label |
| `genre_bucket` | str | Billboard category, or `unlabeled` / `other` |

`genre_bucket` values: `country`, `rap`, `r&b`, `latin`, `christian`, `dance`, `rock`,
`traditional`, `pop`, plus `unlabeled` (14.1%) and `other` (2.5%).

---

## Using it

Analyse `songs_features.csv` at song level — one row per song, placed in the year it first
charted. Use `chart_entries.csv` only for questions about the chart itself, such as how a
particular week looked, and remember the 13 repeated song-weeks when counting.

Three habits worth keeping:

- report medians, not means; a 51-minute track and a handful of others would drag an average
- filter to `eda_core_complete` for audio figures, and say how many songs that removes
- state the year window a figure uses; 1958 and 2020–21 are partial
