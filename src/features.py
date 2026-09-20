"""Add the engineered features used by the analysis.

    python src/features.py

Reads  : data/processed/songs.csv          (produced by clean.py)
Writes : data/processed/songs_features.csv one row per song, ready for eda.py

clean.py fixes what is broken in the source. This script adds what is useful and, unlike
cleaning, every choice here is debatable: the mood thresholds, the streaming cutoff and the
genre keyword lists are ours, not the data's. Each is stated in docs/cleaning-decisions.md and
defined as a constant below, so changing one's mind means editing one line and rerunning this
script, without touching the cleaning pass.

Nothing here drops rows or alters a measured value.
"""

from pathlib import Path

import pandas as pd

from clean import PROCESSED, parse_genres

# Mood splits valence (happy-sounding) and energy at their midpoint. A round number chosen for
# being explainable, not fitted to anything; it labels a song roughly, it does not measure
# emotion (decision in docs/cleaning-decisions.md).
MOOD_THRESHOLD = 0.5

# The chart date on which Billboard first incorporated streaming into the Hot 100. Not the
# 2013 YouTube change, which is the date usually cited (decision 6).
STREAMING_ERA_START = pd.Timestamp("2007-08-11")

# Billboard's own genre categories, from https://www.billboard.com/charts/, plus "traditional"
# for the 1950s and 60s standards Billboard has no modern chart for. Order breaks ties, which
# is why pop is last: it is attached to nearly every charting artist (decision 5).
GENRE_RULES = [
    ("country",     ["country", "nashville", "redneck", "bluegrass"]),
    ("rap",         ["rap", "hip hop", "trap", "drill", "grime"]),
    ("r&b",         ["r&b", "rhythm and blues", "soul", "motown", "funk", "quiet storm",
                     "urban contemporary", "new jack swing", "doo-wop"]),
    ("latin",       ["latin", "reggaeton", "salsa", "bachata", "merengue",
                     "regional mexican", "banda", "tejano", "spanish"]),
    ("christian",   ["christian", "gospel", "worship", "ccm"]),
    ("dance",       ["edm", "house", "techno", "trance", "electronic", "disco",
                     "eurodance", "freestyle", "hi-nrg"]),
    ("rock",        ["rock", "metal", "punk", "grunge", "new wave", "mellow gold",
                     "british invasion", "merseybeat", "psychedelic"]),
    ("traditional", ["adult standards", "brill building", "easy listening", "lounge",
                     "big band", "swing", "vocal jazz", "jazz", "blues", "folk"]),
    ("pop",         ["pop", "boy band", "girl group", "bubblegum"]),
]

GENRE_CATEGORIES = [category for category, _ in GENRE_RULES]


def to_bucket(labels):
    """Map a song's Spotify genre labels onto one Billboard category.

    Every label matching a category casts one vote and the category with the most votes wins;
    ties go to the earlier entry in GENRE_RULES. A vote rather than first-match because one
    stray label should not outrank five: Chuck Berry carries `blues rock`, `classic rock`,
    `rock`, `rock-and-roll` and `rockabilly` alongside a single `soul`.

    Args:
        labels (list[str]): the song's Spotify genre labels, possibly empty.

    Returns:
        str: a category from GENRE_CATEGORIES, or "unlabeled" when the song has no labels at
            all, or "other" when its labels match no category.
    """
    if not labels:
        return "unlabeled"

    votes = {category: sum(any(keyword in label for keyword in keywords) for label in labels)
             for category, keywords in GENRE_RULES}
    most = max(votes.values())
    if most == 0:
        return "other"
    for category in GENRE_CATEGORIES:       # priority order breaks ties
        if votes[category] == most:
            return category


def add_time_features(songs):
    """Add the decade a song first charted in, and whether that was in the streaming era.

    Both are assigned from the *first* chart date, consistent with every other song-level
    figure. The 137 songs whose chart run crosses the streaming boundary therefore count as
    pre-streaming.

    Args:
        songs (pd.DataFrame): the cleaned song table.

    Returns:
        pd.DataFrame: a copy with columns
            decade         (int)   1950, 1960, ... from first_observed_year
            streaming_era  (bool)  first charted on or after STREAMING_ERA_START
    """
    songs = songs.copy()
    songs["decade"] = songs.first_observed_year // 10 * 10
    songs["streaming_era"] = songs.first_observed_chart_date >= STREAMING_ERA_START
    return songs


def add_audio_features(songs):
    """Add song length in minutes and a coarse mood label.

    Both are left missing where the underlying measurement is missing, rather than filled:
    zero is a real value for valence and energy, so filling would invent data.

    Args:
        songs (pd.DataFrame): the cleaned song table.

    Returns:
        pd.DataFrame: a copy with columns
            duration_minutes  (float)  spotify_track_duration_ms / 60000
            mood              (str)    happy/energetic, happy/calm, sad/energetic, sad/calm,
                                       or missing when valence or energy is unavailable
    """
    songs = songs.copy()
    songs["duration_minutes"] = songs.spotify_track_duration_ms / 60_000

    happy = songs.valence >= MOOD_THRESHOLD
    energetic = songs.energy >= MOOD_THRESHOLD
    songs["mood"] = (
        happy.map({True: "happy", False: "sad"})
        + "/"
        + energetic.map({True: "energetic", False: "calm"}))
    songs.loc[songs.valence.isna() | songs.energy.isna(), "mood"] = pd.NA
    return songs


def add_genre_features(songs):
    """Add the Billboard genre category and how much genre information backs it.

    Args:
        songs (pd.DataFrame): the cleaned song table, carrying the raw `spotify_genre` text.

    Returns:
        pd.DataFrame: a copy with columns
            n_genre_labels  (int)   how many Spotify labels the song carries
            has_genre       (bool)  the song carries at least one label
            genre_bucket    (str)   a GENRE_CATEGORIES value, "unlabeled" or "other"
    """
    songs = songs.copy()
    labels = songs.spotify_genre.map(parse_genres)
    songs["n_genre_labels"] = labels.map(len)
    songs["has_genre"] = songs.n_genre_labels > 0
    songs["genre_bucket"] = labels.map(to_bucket)
    return songs


def report(songs):
    """Print what the engineered features look like, and assert they are self-consistent.

    The genre mix by decade is the useful check: it should track music history. If rap were to
    appear in the 1960s, or rock to vanish from the 1980s, a keyword rule has gone wrong.

    Args:
        songs (pd.DataFrame): the table with all engineered features.

    Returns:
        None. Prints a report.

    Raises:
        AssertionError: if a feature contradicts the data it was derived from.
    """
    assert songs.genre_bucket.isin(GENRE_CATEGORIES + ["unlabeled", "other"]).all(), \
        "a song landed in an unknown genre category"
    assert (songs.genre_bucket == "unlabeled").equals(~songs.has_genre), \
        "unlabeled should mean exactly 'no genre labels'"
    assert songs.mood.notna().equals(songs.valence.notna() & songs.energy.notna()), \
        "mood exists exactly where valence and energy do"
    assert songs.loc[songs.streaming_era, "first_observed_chart_date"].ge(
        STREAMING_ERA_START).all(), "a pre-streaming song was flagged as streaming era"

    print(f"streaming era : {songs.streaming_era.sum():,} songs "
          f"(first charted on or after {STREAMING_ERA_START.date()})")
    print(f"mood assigned : {songs.mood.notna().mean():.1%} of songs\n")

    print("mood mix:")
    print((songs.mood.value_counts(normalize=True) * 100).round(1).to_string())

    print("\ngenre categories:")
    print(songs.genre_bucket.value_counts().to_string())

    print("\ngenre mix by decade (% of songs first charting in that decade):")
    mix = pd.crosstab(songs.decade, songs.genre_bucket, normalize="index") * 100
    print(mix.round(1).to_string())


def main():
    """Add every engineered feature and write the analysis-ready table."""
    songs = pd.read_csv(PROCESSED / "songs.csv", parse_dates=[
        "first_observed_chart_date", "last_observed_chart_date"])

    songs = add_time_features(songs)
    songs = add_audio_features(songs)
    songs = add_genre_features(songs)

    report(songs)

    songs.to_csv(PROCESSED / "songs_features.csv", index=False)
    print(f"\nwrote {len(songs):,} songs to data/processed/songs_features.csv")


if __name__ == "__main__":
    main()
