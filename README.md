# How the hits changed

Sixty-two years of the Billboard Hot 100, joined to Spotify's audio measurements, to ask what
actually changed about hit songs between 1958 and 2021.

Course project for AIPI 510 (Duke). Nicholas Wang and Kuba Romanczuk.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python src/clean.py       # raw -> chart_entries.csv, songs.csv
.venv/bin/python src/features.py    # songs.csv -> songs_features.csv
```

Both scripts print a report and assert their own invariants, so a broken run fails loudly
instead of producing quietly wrong numbers. Raw data is committed, so this works from a fresh
clone with no downloads.

## What we found so far

Measured on songs placed in the year they first charted, 1959–2020:

- Hits got **less cheerful**. Median valence holds near 0.70 from the 1960s through the 1980s,
  then falls to 0.47 in the 2010s.
- Hits did **not** simply get shorter. Median length rises from 2.7 minutes in the 1960s to 4.3
  in the 1990s, and has fallen since to 3.6 — still well above where it started.
- The chart changed genre. Traditional pop is 32% of 1950s hits; rock peaks at 56% in the
  1980s; rap and pop together make up 68% of the 2010s.

Figures and the written story are in progress.

## Data

From [TidyTuesday 2021-09-14](https://github.com/rfordatascience/tidytuesday/tree/main/data/2021/2021-09-14),
downloaded 2026-09-17, which credits
[Data.World](https://data.world/kcmillersean/billboard-hot-100-1958-2017#) by way of Sean
Miller, Billboard and Spotify. The TidyTuesday repository is CC0 1.0; the chart data and audio
measurements carry Billboard's and Spotify's own terms.

| File | Rows | Contents |
|---|---|---|
| `data/raw/billboard.csv` | 327,895 | one row per song per chart week, 1958-08-02 to 2021-05-29 |
| `data/raw/audio_features.csv` | 29,503 | Spotify measurements per song |

The files join on `song_id`, the title and performer concatenated. After cleaning, 82.6% of
songs carry audio features — 65.9% for the 1950s against 94.3% for the 2010s, which is a bias
every decade comparison has to account for.

Spotify withdrew public access to the audio-features endpoint in November 2024, so no
comparable data exists past 2021. That ceiling is part of the story rather than a gap we can
fill.

## Layout

```
data/raw/          committed, never modified
data/processed/    written by the scripts
docs/              schema and the reasoning behind each cleaning rule
notebooks/         exploration, and the decisions the cleaning rules came from
src/               the pipeline
```

## Documentation

- [docs/processed-schema.md](docs/processed-schema.md) — every column in the processed files
- [docs/cleaning-decisions.md](docs/cleaning-decisions.md) — each problem found in the data, the
  options considered, and why we chose what we chose

Worth knowing before reading any figure: one song charted twice in the same week in 1990 and
both rows are real; the source `weeks_on_chart` counts rows rather than weeks; some durations
belong to album versions of songs that charted as edited singles; and Billboard changed the
Hot 100 formula five times over this period, so an era comparison is never only about music.
