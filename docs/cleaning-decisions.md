# Cleaning decisions

Every judgement call made while turning the raw files into the cleaned dataset, with the
options considered and the reason for the choice. Each was settled by inspecting the affected
rows in [`notebooks/cleaning_decisions.ipynb`](../notebooks/cleaning_decisions.ipynb).

---

## 1. Duplicate audio rows

**Problem.** `audio_features.csv` has 29,503 rows for 29,386 songs: 24 rows are exact
duplicates, and 93 songs have rows that disagree. Audio features are attached to every chart
week of a song, so duplicates on the audio side would silently multiply chart rows.

**What the rows are.** Every conflicting pair shares the same `spotify_track_id` — the same
recording captured at different times, not different recordings. All 93 differ on popularity,
9 on Spotify's artist genre tags, and 2 on audio values, by at most 0.026 on the 0–1 scores.

**Options.** Keep the first row; drop all duplicated songs; or choose by a stated rule.

**Chosen.** Drop exact duplicates, then keep the row with the highest
`spotify_track_popularity`, breaking ties by the longer genre list and then by
`spotify_track_id` alphabetically. Dropping the songs entirely would lose real data for no
gain; "keep the first" depends on row order. Since no available choice can move a result, the
rule exists to make the output deterministic. The merge is asserted to be many-to-one and to
leave the chart row count unchanged.

**Worth noting.** The same track scored differently on two scrapes, so Spotify's audio features
are model estimates rather than fixed properties of a recording.

---

## 2. Repeated chart rows

**Problem.** 26 rows put the same song twice in one chart week; 58 rows across 24 weeks put two
different songs at the same rank.

**What the rows are.** All 26 are "Unchained Melody" by The Righteous Brothers in late 1990,
when two separate recordings charted at once after *Ghost* revived the song; `song_id` is built
from title and performer, so both recordings share one identifier. The 58 are ties, spread
between 1958 and 1989, or 0.018% of chart rows.

**Options.** Drop the lower-ranked row; merge them into one entry; or keep both and aggregate
carefully.

**Chosen.** Keep every row. All of them are genuine chart entries, and deleting them would
remove real chart history to satisfy an assumption the data never made. Song-level figures
count *distinct chart dates* rather than rows, so a song holding two positions in one week is
never counted twice, and the best rank is the minimum position reached. No validation assumes
one row per rank per week, or exactly 100 rows per week — five weeks in 1991 have 99.

---

## 3. Chart history is recomputed, never copied

**Problem.** The source `weeks_on_chart` column counts rows rather than weeks, so it advances
twice in a single week during the 1990 "Unchained Melody" overlap. It also keeps counting
across separate chart runs, so a song re-entering decades later continues from its old total.

**Options.** Repair the column, or ignore it and recompute.

**Chosen.** Recompute. `observed_chart_weeks`, `best_observed_rank` and the first and last
chart dates are derived from the weekly records; the source `peak_position` and
`weeks_on_chart` are not carried into the cleaned data. Repairing a column whose definition is
unclear would mean guessing at intent. For "Unchained Melody" this is the difference between 57
chart rows and the 44 distinct dates it actually spent on the Hot 100.

---

## 4. Implausible durations are kept

**Problem.** 28 tracks report over ten minutes, out of 24,288 with a duration, including one of
51 minutes.

**What the rows are.** All 28 genuinely charted, together accounting for 305 chart weeks. Their
album metadata shows the cause: "Tubular Bells" charted as an edited single but is matched to
the 26-minute album track, "Autobahn" to a 22-minute remaster, and "Sexual" by Goddess to a
meditation album that is not the charting recording at all.

**Options.** Drop them, flag them, or leave them.

**Chosen.** Leave them, unflagged. Excluding tracks over ten minutes moves a decade median by
at most 0.003 minutes — under a fifth of a second — because the median is the middle song and
cannot be pulled by an outlier. The mean does move, which is why medians are used throughout.

**Worth noting.** These are not wrong numbers so much as the wrong version of the right song,
and album versions are more common for older songs, so the mismatch is not spread evenly across
decades. This bears directly on any claim about song length.

---

## 5. Genre categories

**Problem.** `spotify_genre` holds 1,145 distinct labels, a median of four per song, and
nothing at all for 14% of songs. The labels describe the *artist* rather than the song, and
reflect Spotify's present-day tagging.

**Options.** Invent our own categories; use a machine-learning convention such as the GTZAN
ten; or use Billboard's own genre charts.

**Chosen.** Billboard's categories, from <https://www.billboard.com/charts/>: country, rap,
r&b, latin, christian, dance/electronic, rock and pop. Using Billboard's categories on
Billboard's own chart means the taxonomy is theirs rather than ours. One category is ours and
is declared as such: **traditional**, for the "adult standards" and "brill building pop" music
that dominates the 1950s and 60s, for which Billboard publishes no modern chart, and without
which those decades would empty into "other".

**How a song is assigned.** Each label that matches a category casts one vote, and the category
with the most votes wins; ties break by a fixed priority order in which pop comes last, since
it is attached to nearly every charting artist. A vote rather than first-match, because one
stray label should not outrank five: under first-match, Chuck Berry's "Johnny B. Goode" landed
in r&b on a single `soul` label against five rock labels, and "Bad Guy" landed in dance because
`electropop` contains `electro`.

**Coverage and known faults.** 83.4% of songs land in a Billboard category, 14% are
`unlabeled`, 2.5% `other`. Unlabeled is 27.7% of 1950s songs against 3.6% in the 2010s, so
genre mix by decade is least reliable at the older end. Disco usually lands in r&b rather than
dance, because disco artists carry more soul and funk labels than electronic ones, and reggae
has no Billboard genre chart in this list, so it falls into `other`.

---

## 6. The streaming era

**Problem.** There is no single date on which streaming arrived on the Hot 100.

| Date | Change |
|---|---|
| 1991 | Nielsen SoundScan point-of-sale data replaces reported sales |
| 12 February 2005 | paid digital downloads counted |
| **11 August 2007** | streaming and on-demand services first incorporated |
| 21 February 2013 | YouTube video streams added |
| 2018–2019 | paid and free streams reweighted |

**Options.** 2013, the date usually cited in coverage of "streaming changing the charts"; 2007,
the first actual inclusion; or no boolean at all, using a continuous time axis instead.

**Chosen.** `streaming_era` is true for songs whose *first* chart date falls on or after
11 August 2007 — 6,331 songs, against 23,058 before it. February 2013 refers to the addition of
YouTube, five and a half years after streaming actually entered the formula. The 137 songs
whose chart run crosses the boundary are assigned to the pre-streaming era by first chart date,
consistent with every other song-level figure.

**How it is used.** As an annotation on continuous time series, not as the basis for a
before-and-after claim, because the formula changed five times over the period and any gap
across the boundary mixes changes in music with changes in measurement. Billboard also applies
a "recurrent" rule that drops a song once it has spent 20 weeks on the chart and fallen below
number 50, revised several times, so chart longevity is partly an artefact of chart
administration rather than of listening.

**Source.** Dates come from Wikipedia's Billboard Hot 100 article, citing Billboard and a
February 2013 New York Times report. To be confirmed against Billboard's own pages before
publication.
