# AIPI-510-Project-1

AIPI 510 Project 1 — Nicholas and Kuba.

How the sound of American hit songs changed between 1958 and 2021, using Billboard Hot 100
chart history joined to Spotify's audio measurements.

## Data

Raw data in `data/raw` was imported from
[TidyTuesday 2021-09-14](https://github.com/rfordatascience/tidytuesday/tree/main/data/2021/2021-09-14),
downloaded 2026-09-17.

| File | Contents |
|---|---|
| `billboard.csv` | one row per song per chart week: 327,895 rows, 1958-08-02 to 2021-05-29 |
| `audio_features.csv` | Spotify's measurements per song: 29,503 rows, 29,386 unique songs |

The two join on `song_id`, the song title and performer concatenated. After cleaning, 86.7% of
chart rows carry audio features; coverage is worse for older songs.

**Citation.** TidyTuesday credits the data to
[Data.World](https://data.world/kcmillersean/billboard-hot-100-1958-2017#) by way of Sean
Miller, [Billboard.com](https://www.billboard.com/) and Spotify. The TidyTuesday repository is
released under CC0 1.0; the chart data originates with Billboard and the audio measurements
with Spotify, whose own terms apply to the content.

## Repository layout

```
data/raw/          downloaded, never modified
data/processed/    produced by the scripts
docs/              cleaning decisions and other write-ups
notebooks/         exploration, and the decisions behind the cleaning rules
src/               the pipeline
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Cleaning decisions

Every judgement call in the pipeline — the problem, the options, the choice and the reason —
is recorded in **[docs/cleaning-decisions.md](docs/cleaning-decisions.md)**. In short:

| # | Problem | Choice |
|---|---|---|
| 1 | 24 exact duplicate audio rows, 93 songs with conflicting rows | keep the most popular row, by a deterministic rule |
| 2 | One song twice in a week; two songs sharing a rank | keep every row, count distinct chart dates |
| 3 | `weeks_on_chart` counts rows, not weeks | recompute chart history from the weekly records |
| 4 | 28 tracks over ten minutes | keep them; medians are unaffected |
| 5 | 1,145 Spotify genre labels | Billboard's own genre categories, assigned by a vote |
| 6 | No single date when streaming reached the chart | 11 August 2007, used as annotation, not as a cause |
