"""Turn the two raw files into the cleaned dataset.

    python src/clean.py

Reads  : data/raw/billboard.csv, data/raw/audio_features.csv
Writes : data/processed/chart_entries.csv   one row per song per chart week
         data/processed/songs.csv           one row per song

The rules applied here are the ones decided in docs/cleaning-decisions.md. Where a function
implements a rule, the decision number is named in its docstring, so the code and the write-up
can be checked against each other.

"""

import ast
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

AUDIO_COLS = [
    "spotify_track_id",
    "spotify_track_duration_ms",
    "spotify_track_explicit",
    "spotify_track_popularity",
    "spotify_genre",
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "liveness",
    "loudness",
    "speechiness",
    "tempo",
    "mode",
    "time_signature",
]

CORE_AUDIO = ["danceability", "energy", "valence", "acousticness"]

CHART_START = pd.Timestamp("1958-08-02")
CHART_END = pd.Timestamp("2021-05-29")


def parse_genres(value):
    """Turn a raw `spotify_genre` cell into a list of labels.

    The column stores a list as text, e.g. "['rock', 'pop']". Shared with features.py, which
    maps the labels onto Billboard's genre categories.

    Args:
        value (str | float): a raw `spotify_genre` cell, possibly missing.

    Returns:
        list[str]: the labels; empty if the cell is missing or unparseable.
    """
    if pd.isna(value):
        return []
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []


def load_raw():
    """Read both raw CSV files without changing them.

    Returns:
        billboard pd.DataFrame exactly as stored on disk
        audio pd.DataFrame exactly as stored on disk
        audio[pd.DataFrame, pd.DataFrame]: (billboard, audio), exactly as stored on disk.
    """
    billboard = pd.read_csv(RAW / "billboard.csv")
    audio = pd.read_csv(RAW / "audio_features.csv")
    return billboard, audio


def clean_chart_entries(billboard):
    """Build the weekly chart table: one row per song per chart week.

    Args:
        billboard (pd.DataFrame): the raw billboard table from load_raw().

    Returns:
        pd.DataFrame: one row per song-week, with columns
            song_id     (str)       song title and performer concatenated
            song        (str)       readable title
            performer   (str)       readable artist
            chart_date  (datetime)  the chart week, parsed from `week_id`
            position    (int)       chart position that week, 1-100
            instance    (int)       which separate chart run this row belongs to
            chart_year  (int)       year of chart_date
        Row count equals the raw table's row count.
    """
    entries = pd.DataFrame({
        "song_id": billboard.song_id,
        # song_id is "Billie JeanMichael Jackson", fine as a key and unreadable everywhere
        # else. This is the only table fed from the chart file, so readable names have to
        # enter here; build_songs() carries them through to songs.csv.
        "song": billboard.song,
        "performer": billboard.performer,
        "chart_date": pd.to_datetime(billboard.week_id, format="%m/%d/%Y"),
        "position": billboard.week_position,
        "instance": billboard.instance,
    })
    entries["chart_year"] = entries.chart_date.dt.year
    return entries


def resolve_audio(audio):
    """Reduce the audio table to exactly one row per song.

    Args:
        audio (pd.DataFrame): the raw audio table from load_raw().

    Returns:
        pd.DataFrame: `song_id` plus AUDIO_COLS, with a unique song_id.
    """
    unique_audio = audio.drop_duplicates()

    # Tie-breaks, so the surviving row never depends on the order rows happen to be in:
    # most popular first, then the longer genre list, then track id.
    unique_audio = unique_audio.assign(
        _n_genres=unique_audio.spotify_genre.map(lambda cell: len(parse_genres(cell))))
    non_duplicate_audio = (
        unique_audio
        .sort_values(["song_id", "spotify_track_popularity", "_n_genres", "spotify_track_id"],
                     ascending=[True, False, False, True])
        .drop_duplicates("song_id")
        .drop(columns="_n_genres"))

    assert non_duplicate_audio.song_id.is_unique, "audio still has duplicate song_ids"

    return non_duplicate_audio[["song_id"] + AUDIO_COLS]


def build_songs(chart_entries, audio_resolved):
    """Build the song-level table: chart history, audio measurements and quality flags.

    Chart history is computed from chart_entries, never copied from the source (decision 3).
    `observed_chart_weeks` counts distinct chart dates rather than rows, which is what stops
    the 1990 double-entry from being counted twice (decision 2).

    Args:
        chart_entries (pd.DataFrame): output of clean_chart_entries().
        audio_resolved (pd.DataFrame): output of resolve_audio(), unique on song_id.

    Returns:
        pd.DataFrame: one row per song, with columns
            song_id                    (str)
            song                       (str)       readable title
            performer                  (str)       readable artist
            first_observed_chart_date  (datetime)  earliest chart date
            last_observed_chart_date   (datetime)  latest chart date
            first_observed_year        (int)       year of the first chart date
            observed_chart_weeks       (int)       count of DISTINCT chart dates
            best_observed_rank         (int)       lowest position number reached
            observed_top10_weeks       (int)       distinct dates at position <= 10
            n_runs                     (int)       separate chart runs, from `instance`
            spans_decades              (bool)      charted in more than one decade
            audio_row_matched          (bool)      an audio row exists for this song
            eda_core_complete          (bool)      all four CORE_AUDIO features present
            ... plus every column in AUDIO_COLS
    """
    songs = chart_entries.groupby("song_id").agg(
        song=("song", "first"),
        performer=("performer", "first"),
        first_observed_chart_date=("chart_date", "min"),
        last_observed_chart_date=("chart_date", "max"),
        # nunique, not size: a song holding two chart positions in one week (decision 2)
        # spent one week on the chart, not two.
        observed_chart_weeks=("chart_date", "nunique"),
        best_observed_rank=("position", "min"),
        n_runs=("instance", "nunique"),
    )

    songs["first_observed_year"] = songs.first_observed_chart_date.dt.year
    songs["spans_decades"] = (
        songs.first_observed_chart_date.dt.year // 10
        != songs.last_observed_chart_date.dt.year // 10)

    # Songs that never reached the top 10 are absent from this count, so they need filling
    # with 0 rather than being left missing.
    top10_weeks = (chart_entries[chart_entries.position <= 10]
                   .groupby("song_id").chart_date.nunique())
    songs["observed_top10_weeks"] = top10_weeks.reindex(songs.index, fill_value=0)

    songs = songs.reset_index().merge(
        audio_resolved, on="song_id", how="left", validate="m:1")

    songs["audio_row_matched"] = songs.spotify_track_id.notna()
    songs["eda_core_complete"] = songs[CORE_AUDIO].notna().all(axis=1)

    return songs


def check(chart_entries, songs, billboard):
    """Print the quality report and assert the rules that must never break.

    This is what replaces re-running a notebook to ask "are there duplicates, is anything
    missing". Every run of the pipeline answers it.

    Args:
        chart_entries (pd.DataFrame): output of clean_chart_entries().
        songs (pd.DataFrame): output of build_songs().
        billboard (pd.DataFrame): the raw billboard table, for before-and-after comparison.

    Returns:
        None. Prints a report.

    Raises:
        AssertionError: if any invariant below is violated.
    """
    # Each assertion is a rule from docs/cleaning-decisions.md. Nothing here checks that one
    # song holds one rank per week, or that a week has 100 rows: decision 2 shows both are
    # false in this data.
    assert len(chart_entries) == len(billboard), "chart rows were added or lost"
    assert songs.song_id.is_unique, "songs.csv has duplicate song_ids"
    assert len(songs) == billboard.song_id.nunique(), "a song was invented or lost"
    assert chart_entries.position.between(1, 100).all(), "a chart position is outside 1-100"
    assert chart_entries.chart_date.between(CHART_START, CHART_END).all(), \
        "a chart date falls outside the dataset window"
    assert songs.observed_chart_weeks.ge(1).all(), "a song has no chart weeks"
    assert (songs.observed_top10_weeks <= songs.observed_chart_weeks).all(), \
        "a song has more top-10 weeks than chart weeks"

    print(f"chart entries : {len(chart_entries):,} rows "
          f"({chart_entries.chart_date.min().date()} to {chart_entries.chart_date.max().date()})")
    print(f"songs         : {len(songs):,} rows")
    print(f"  with an audio row  : {songs.audio_row_matched.mean():6.1%}")
    print(f"  with core features : {songs.eda_core_complete.mean():6.1%}")
    print(f"  charting in more than one decade: {songs.spans_decades.sum():,}")

    # Audio coverage is worse for older songs. That bias has to be discussed in the write-up,
    # so the pipeline reports it on every run rather than leaving it to memory.
    print("\naudio coverage by decade of first charting:")
    decade = songs.first_observed_year // 10 * 10
    coverage = songs.groupby(decade).agg(
        songs=("song_id", "size"),
        with_audio=("audio_row_matched", "mean"),
        core_complete=("eda_core_complete", "mean"))
    coverage[["with_audio", "core_complete"]] *= 100
    print(coverage.round(1).to_string())


def main():
    """Run the pipeline and write the processed files."""
    PROCESSED.mkdir(parents=True, exist_ok=True)

    billboard, audio = load_raw()

    chart_entries = clean_chart_entries(billboard)
    audio_resolved = resolve_audio(audio)
    songs = build_songs(chart_entries, audio_resolved)

    check(chart_entries, songs, billboard)

    chart_entries.to_csv(PROCESSED / "chart_entries.csv", index=False)
    songs.to_csv(PROCESSED / "songs.csv", index=False)
    print(f"\nwrote {len(chart_entries):,} chart entries and {len(songs):,} songs "
          f"to {PROCESSED.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
