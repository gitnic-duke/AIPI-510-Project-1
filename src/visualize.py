"""Reproduce the final blog figures from the processed song table.

Run: python src/visualize.py
Optional: --input path/to/songs_features.csv --output-dir docs/figures
Each song counts once, by first observed chart decade, 1960–2019.
No missing audio is filled in for any published figure. Tables are exported
beside the SVGs so every plotted value can be inspected without this script.
"""
from pathlib import Path
import argparse
import json
import textwrap
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
ROOT = Path(__file__).resolve().parents[1]
SCORES = ['valence', 'danceability', 'energy', 'acousticness']
DECADES = list(range(1960, 2020, 10))
GENRES = ['pop', 'rock', 'rap', 'r&b', 'country']
COLORS = dict(zip(SCORES, ['#ad482f', '#16746d', '#916807', '#486cab']))
BG = '#fdfdfc'
INK = '#1a1a1a'
MUTED = '#5c5c5c'


def format_minutes(value, _=None):
    """Format a duration in minutes as m:ss for tick labels and annotations."""
    seconds = int(round(value * 60))
    return f'{seconds // 60}:{seconds % 60:02d}'


def configure_plot_style():
    """Apply the shared visual style to every figure."""
    plt.rcParams.update({
        'font.family': 'DejaVu Sans',
        'font.size': 12,
        'figure.facecolor': BG,
        'axes.facecolor': BG,
        'text.color': INK,
        'axes.labelcolor': MUTED,
        'xtick.color': MUTED,
        'ytick.color': MUTED,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.spines.left': False,
        'axes.spines.bottom': False,
        'axes.titleweight': 'bold',
        'axes.titlesize': 15,
        'svg.fonttype': 'none',
        'svg.hashsalt': 'hits-510',
        'savefig.facecolor': BG,
        'lines.linewidth': 2.7,
    })


def create_figure(title, ylabel, *, ymax=1, figsize=(6.5, 4.6), decades=True):
    """Create a styled figure, using decade labels unless an annual axis is needed."""
    fig, ax = plt.subplots(figsize=figsize, layout='constrained')
    ax.set_title(
        textwrap.fill(title, width=43 if figsize[0] >= 6.5 else 34),
        loc='left',
        pad=20
    )
    ax.set_ylabel(ylabel, labelpad=12)
    ax.set_ylim(0, ymax)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#deded9', linewidth=0.7)
    ax.tick_params(length=0, pad=8)
    if decades:
        ax.set_xticks(DECADES, [f'{d}s' for d in DECADES])
        ax.set_xlabel('Decade first seen on the Hot 100', labelpad=12)
        ax.set_xlim(1956, 2014)
    return fig, ax


def save_figure(fig, output_dir, name, description):
    """Save an SVG with its description and close the figure."""
    fig.savefig(
        output_dir / f'{name}.svg',
        metadata={'Date': None, 'Description': description},
        pad_inches=0.12
    )
    plt.close(fig)


def plot_labeled_line(ax, series, color, format_value, offset=10):
    """Draw a line with a formatted value beside each point."""
    ax.plot(series.index, series.values, 'o-', color=color, markersize=6)
    for x, y in series.items():
        ax.annotate(
            format_value(y),
            (x, y),
            xytext=(0, offset),
            textcoords='offset points',
            ha='center',
            fontsize=11,
            color=color
        )


def load_data(path):
    """Validate the input and return all songs, complete-audio songs, and known lengths."""
    songs = pd.read_csv(path)
    required = {
        'song_id',
        'first_observed_year',
        'decade',
        'duration_minutes',
        'genre_bucket',
        'eda_core_complete',
        'has_genre',
        *SCORES,
    }
    missing = required - set(songs.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')
    if not songs.song_id.is_unique:
        raise ValueError('Expected one row per song_id.')
    # Accept bools or their CSV string forms; never interpret "False" as True.
    for column in ['eda_core_complete', 'has_genre']:
        songs[column] = songs[column].astype(str).str.lower().map({
            'true': True,
            'false': False,
        })
        if songs[column].isna().any():
            raise ValueError(f'{column} must contain True or False.')
    if not songs.eda_core_complete.equals(songs[SCORES].notna().all(axis=1)):
        raise ValueError('Audio completeness flag disagrees with measured scores.')
    if not songs[SCORES].stack().between(0, 1).all():
        raise ValueError('Audio scores must be between 0 and 1.')
    sample = songs[songs.first_observed_year.between(1960, 2019)].copy()
    if not (sample.decade == sample.first_observed_year // 10 * 10).all():
        raise ValueError('Decade must refer to first observed chart year.')
    if sorted(sample.decade.unique()) != DECADES:
        raise ValueError('All six full decades are required.')
    sample.genre_bucket = sample.genre_bucket.fillna('unlabeled')
    audio = sample[sample.eda_core_complete].copy()
    lengths = sample.dropna(subset=['duration_minutes']).copy()
    if not lengths.duration_minutes.gt(0).all():
        raise ValueError('Durations must be positive.')
    return sample, audio, lengths


def summarize_decades(audio, lengths, tables_dir):
    """Calculate and export the decade summaries used by the main stories."""
    audio_medians = audio.groupby('decade')[SCORES].median().reindex(DECADES)
    audio_medians.to_csv(tables_dir / 'audio_medians.csv')
    duration_summary = lengths.groupby('decade').duration_minutes.agg(['count', 'median'])
    duration_summary['under_three_pct'] = lengths.duration_minutes.lt(3).groupby(lengths.decade).mean() * 100
    duration_summary.to_csv(tables_dir / 'duration.csv')
    return audio_medians, duration_summary


def plot_duration_overview(duration_summary, output_dir):
    """Show the rise and fall in median recording length."""
    fig, ax = create_figure(
        'Hits grew longer before they got shorter',
        'Median length · minutes:seconds',
        ymax=5
    )
    ax.yaxis.set_major_formatter(FuncFormatter(format_minutes))
    plot_labeled_line(ax, duration_summary['median'], '#ad482f', format_minutes)
    save_figure(
        fig,
        output_dir,
        'duration_overview',
        'Median Spotify recording length by first chart decade; songs with known duration.'
    )


def plot_audio_overview(audio, tables_dir, output_dir):
    """Export annual audio summaries and draw one panel for each score."""
    subtitles = {
        'valence': 'Valence',
        'danceability': 'Danceability',
        'energy': 'Energy',
        'acousticness': 'Acousticness',
    }
    # Separate SVGs allow the webpage to stack the panels on narrow screens.
    # Keep the anonymous quartile aggregations to preserve the exported CSV headers.
    annual = audio.groupby('first_observed_year')[SCORES].agg([
        'median',
        lambda s: s.quantile(0.25),
        lambda s: s.quantile(0.75),
    ])
    annual.to_csv(tables_dir / 'annual_audio.csv')
    for score in SCORES:
        fig, ax = create_figure(subtitles[score], 'Score (0–1)', figsize=(6, 4), decades=False)
        yearly = audio.groupby('first_observed_year')[score]
        yearly_median = yearly.median()
        ax.plot(yearly_median.index, yearly_median, color=COLORS[score])
        ax.fill_between(
            yearly_median.index,
            yearly.quantile(0.25),
            yearly.quantile(0.75),
            color=COLORS[score],
            alpha=0.15,
            linewidth=0
        )
        ax.set_xticks([1960, 1980, 2000, 2019])
        ax.set_xlim(1960, 2019)
        ax.set_xlabel('First year seen on the Hot 100')
        save_figure(
            fig,
            output_dir,
            f'overview_{score}',
            'Annual median; shaded band contains the middle 50% of songs, not a confidence interval.'
        )


def plot_valence_danceability(audio, tables_dir, output_dir):
    """Show how often low valence and high danceability occur together."""
    audio['joint'] = audio.valence.lt(0.5) & audio.danceability.ge(0.5)
    joint = audio.groupby('decade').joint.agg(['size', 'sum', 'mean'])
    joint['percent'] = joint['mean'] * 100
    joint.to_csv(tables_dir / 'valence_danceability.csv')
    fig, ax = create_figure(
        'Lower valence + higher danceability became common',
        'Songs with audio',
        ymax=100
    )
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    plot_labeled_line(ax, joint.percent, COLORS['danceability'], lambda v: f'{v:.1f}%')
    ax.text(
        0.02,
        0.91,
        'Valence < 0.5 AND danceability ≥ 0.5',
        transform=ax.transAxes,
        fontsize=11,
        color=MUTED
    )
    save_figure(
        fig,
        output_dir,
        'valence_danceability',
        'Share meeting both stated score cutoffs, with each song counted once.'
    )


def plot_short_songs(duration_summary, output_dir):
    """Show the share of recordings shorter than three minutes."""
    fig, ax = create_figure(
        'Short songs are returning—not setting a record',
        'Songs with known duration',
        ymax=100
    )
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    plot_labeled_line(ax, duration_summary.under_three_pct, '#ad482f', lambda v: f'{v:.1f}%')
    ax.text(
        0.47,
        0.9,
        'Short = under 3 minutes',
        transform=ax.transAxes,
        fontsize=12,
        color=MUTED
    )
    save_figure(
        fig,
        output_dir,
        'short_songs',
        'Percentage of known Spotify recording durations strictly below three minutes.'
    )


def plot_recent_duration(lengths, tables_dir, output_dir):
    """Show annual recording lengths from 1990 onward."""
    recent_duration = lengths[lengths.first_observed_year >= 1990].groupby('first_observed_year').duration_minutes.agg([
        'count',
        'median',
    ])
    recent_duration.to_csv(tables_dir / 'annual_duration.csv')
    fig, ax = create_figure(
        'The shortening continued through the 2010s',
        'Median length · minutes:seconds',
        ymax=5,
        decades=False
    )
    ax.plot(recent_duration.index, recent_duration['median'], color='#ad482f')
    ax.yaxis.set_major_formatter(FuncFormatter(format_minutes))
    ax.set_xticks([1990, 2000, 2010, 2019])
    ax.set_xlim(1988, 2021)
    ax.set_xlabel('First year seen on the Hot 100')
    for y in [2010, 2019]:
        ax.scatter(y, recent_duration.loc[y, 'median'], color='#ad482f')
        ax.annotate(
            format_minutes(recent_duration.loc[y, 'median']),
            (y, recent_duration.loc[y, 'median']),
            xytext=(0, 12),
            textcoords='offset points',
            ha='center',
            color='#ad482f'
        )
    save_figure(
        fig,
        output_dir,
        'recent_duration',
        'Annual median recording duration, 1990–2019; all songs with duration available.'
    )


def plot_acoustic_shift(audio_medians, output_dir):
    """Show the decade medians for acousticness."""
    fig, ax = create_figure(
        'The biggest acousticness drop came before the 1990s',
        'Median acousticness (0–1)'
    )
    plot_labeled_line(
        ax,
        audio_medians.acousticness,
        COLORS['acousticness'],
        lambda v: f'{v:.3f}'
    )
    save_figure(
        fig,
        output_dir,
        'acoustic_shift',
        'Median acousticness among songs with all four core audio scores, by first chart decade.'
    )


def plot_fixed_genre_mix(audio, tables_dir, output_dir):
    """
    Compare observed mean valence with a fixed 1980s genre mix.
    Note: we removed this from the final webpage but are still keeping the figure
    """
    selected_genres = audio[(audio.decade >= 1980) & audio.genre_bucket.isin(GENRES)]
    counts = pd.crosstab(
        selected_genres.decade,
        selected_genres.genre_bucket
    ).reindex(columns=GENRES)
    if not (counts >= 50).all().all():
        raise ValueError('Fixed-mix comparison requires at least 50 songs per genre-decade.')
    # Hold the five genres at their 1980s proportions in every later decade.
    weights = counts.loc[1980] / counts.loc[1980].sum()
    means = selected_genres.groupby(['decade', 'genre_bucket']).valence.mean().unstack()
    genre_mix = pd.DataFrame({
        'Observed mix': selected_genres.groupby('decade').valence.mean(),
        '1980s mix held fixed': means.mul(weights).sum(axis=1),
    })
    selected_counts = selected_genres.groupby('decade').size()
    all_audio_counts = audio[audio.decade >= 1980].groupby('decade').size()
    genre_mix['included_audio_pct'] = selected_counts / all_audio_counts * 100
    genre_mix.to_csv(tables_dir / 'fixed_genre_mix.csv')
    counts.to_csv(tables_dir / 'fixed_genre_counts.csv')
    fig, ax = create_figure(
        'Valence falls even when the genre mix stays fixed',
        'Mean valence (0–1)'
    )
    for column, color, style in [
        ('Observed mix', '#ad482f', 'o-'),
        ('1980s mix held fixed', '#16746d', 's--'),
    ]:
        ax.plot(genre_mix.index, genre_mix[column], style, color=color, label=column)
    ax.set_xticks([1980, 1990, 2000, 2010], [f'{d}s' for d in [1980, 1990, 2000, 2010]])
    ax.set_xlim(1977, 2013)
    ax.legend(frameon=False, loc='upper right')
    for column, label_offset, color in [
        ('Observed mix', 12, '#ad482f'),
        ('1980s mix held fixed', -20, '#16746d'),
    ]:
        ax.annotate(
            f'{genre_mix.loc[2010, column]:.3f}',
            (2010, genre_mix.loc[2010, column]),
            xytext=(0, label_offset),
            textcoords='offset points',
            ha='center',
            color=color
        )
    save_figure(
        fig,
        output_dir,
        'fixed_genre_mix',
        'Means in five genre buckets; fixed mix uses their 1980s audio-sample proportions throughout.'
    )


def plot_genre_acousticness(audio, lengths, tables_dir, output_dir):
    """Export genre summaries and draw the four acousticness panels."""
    genre_duration = lengths[lengths.decade >= 1990].groupby([
        'decade',
        'genre_bucket',
    ]).duration_minutes.agg(['count', 'median'])
    genre_acousticness = audio.groupby([
        'decade',
        'genre_bucket',
    ]).acousticness.agg(['count', 'median'])
    genre_duration.to_csv(tables_dir / 'genre_duration.csv')
    genre_acousticness.to_csv(tables_dir / 'genre_acousticness.csv')
    # Individual panels keep five overlapping genre lines out of the main story.
    for genre in ['pop', 'rock', 'r&b', 'country']:
        data = genre_acousticness.xs(genre, level='genre_bucket')
        genre_label = 'R&B' if genre == 'r&b' else genre.title()
        fig, ax = create_figure(
            f'{genre_label} · acousticness also fell',
            'Median score (0–1)',
            figsize=(6, 4)
        )
        ax.plot(
            data.index,
            data['median'].where(data['count'] >= 50),
            'o-',
            color=COLORS['acousticness']
        )
        ax.set_xticks([1960, 1980, 2000, 2010], ['1960s', '1980s', '2000s', '2010s'])
        save_figure(
            fig,
            output_dir,
            'acoustic_' + genre.replace('&', ''),
            'Exploratory artist-tag genre bucket; only groups with at least 50 complete-audio songs shown.'
        )


def plot_audio_coverage(sample, tables_dir, output_dir):
    """Export coverage summaries and show missing audio by decade."""
    coverage = sample.groupby('decade').eda_core_complete.agg(['size', 'sum', 'mean'])
    coverage['percent'] = coverage['mean'] * 100
    coverage.to_csv(tables_dir / 'coverage.csv')
    genre_coverage = sample.groupby('genre_bucket').eda_core_complete.agg([
        'size',
        'sum',
        'mean',
    ])
    genre_coverage.to_csv(tables_dir / 'genre_coverage.csv')
    pd.crosstab(
        sample.decade,
        sample.genre_bucket,
        normalize='index'
    ).mul(100).to_csv(tables_dir / 'genre_composition_all_songs.csv')
    fig, ax = create_figure(
        'Earlier decades have more missing audio',
        'Songs with all four audio scores',
        ymax=100
    )
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    plot_labeled_line(ax, coverage.percent, '#67635d', lambda v: f'{v:.1f}%', offset=-20)
    save_figure(
        fig,
        output_dir,
        'audio_coverage',
        'Core-audio coverage among all charting songs in each first observed decade.'
    )

def plot_genre_overview(tables_dir, output_dir):
    """Show each decade's genre composition, including unlabeled songs."""
    shares = pd.read_csv(
        tables_dir / 'genre_composition_all_songs.csv',
        index_col='decade'
    ).reindex(DECADES)

    # Match the notebook's display groups.
    main_genres = ['rock', 'pop', 'rap', 'r&b', 'country', 'traditional']
    other_genres = ['dance', 'latin', 'christian', 'other']

    plot_data = shares.reindex(columns=main_genres, fill_value=0).copy()
    plot_data['other_labeled'] = shares.reindex(
        columns=other_genres, fill_value=0
    ).sum(axis=1)
    plot_data['unlabeled'] = shares.get('unlabeled', 0)

    # Catch missing decades or categories accidentally left out of the chart.
    if shares.isna().any().any() or not (
        plot_data.sum(axis=1).sub(100).abs() < 0.01
    ).all():
        raise ValueError('Genre shares must cover every decade and sum to 100%.')

    # Each entry specifies the legend label, fill color, and label color.
    styles = {
        'rock': ('Rock', '#496db0', 'white'),
        'pop': ('Pop', '#b24a36', 'white'),
        'rap': ('Rap', '#267a78', 'white'),
        'r&b': ('R&B', '#87528b', 'white'),
        'country': ('Country', '#c18a20', INK),
        'traditional': ('Traditional', '#7a6758', 'white'),
        'other_labeled': ('Other labeled', '#bbbbbb', INK),
        'unlabeled': ('Unlabeled', '#e5e5e5', INK),
    }

    fig, ax = create_figure(
        'The genre mix of charting songs changed',
        'Share of songs',
        ymax=100,
        figsize=(9, 6)
    )
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    ax.set_yticks([0, 25, 50, 75, 100])

    bottom = pd.Series(0.0, index=DECADES)

    for genre, (label, color, text_color) in styles.items():
        values = plot_data[genre]

        ax.bar(
            DECADES,
            values,
            bottom=bottom,
            width=7,
            color=color,
            edgecolor=BG,
            linewidth=0.6,
            label=label
        )

        # Label larger segments; small ones remain visible without crowding.
        for decade in DECADES:
            share = values.loc[decade]
            if share >= 8:
                ax.text(
                    decade,
                    bottom.loc[decade] + share / 2,
                    f'{share:.0f}%',
                    ha='center',
                    va='center',
                    fontsize=11,
                    fontweight='bold',
                    color=text_color
                )

        bottom = bottom + values

    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.18),
        ncol=4,
        frameon=False,
        fontsize=10
    )

    save_figure(
        fig,
        output_dir,
        'genre_overview',
        'Genre shares among all songs first seen on the Hot 100 in '
        '1960–2019. Each song belongs to one broad artist-tag bucket; '
        'unlabeled songs are included. Genre assignments are exploratory.'
    )


def export_missing_audio_sensitivity(sample, tables_dir):
    """Export hypothetical mean changes under different missing-audio assumptions."""
    # Reproduce the notebook's mean-only missing-audio sensitivity check.
    observed = sample.groupby('decade')[SCORES].mean()
    groups = sample.groupby(['decade', 'genre_bucket'])[SCORES]
    group_means = groups.transform('mean')
    group_counts = groups.transform('count')
    fallback = sample.groupby('decade')[SCORES].transform('mean')
    # Use a genre-decade mean only with at least 20 measured values and a genre tag.
    # Otherwise, fall back to that decade's mean for the score.
    use_genre_mean = group_counts.ge(20).mul(sample.has_genre, axis=0)
    estimates = group_means.where(use_genre_mean, fallback)
    scenario = sample[SCORES].fillna(estimates).groupby(sample.decade).mean()
    # The extreme bounds assign every missing score either 0 or 1.
    # These scenarios affect this table only; plotted scores are never filled in.
    lower = sample[SCORES].fillna(0).groupby(sample.decade).mean()
    upper = sample[SCORES].fillna(1).groupby(sample.decade).mean()
    # For the smallest change, compare the 2010s lower bound to the 1960s upper
    # bound; reverse those choices for the largest possible change.
    bounds = pd.DataFrame({
        'observed_change': observed.loc[2010] - observed.loc[1960],
        'genre_scenario_change': scenario.loc[2010] - scenario.loc[1960],
        'smallest_possible_change': lower.loc[2010] - upper.loc[1960],
        'largest_possible_change': upper.loc[2010] - lower.loc[1960],
    })
    bounds.to_csv(tables_dir / 'missing_audio_bounds.csv')


def write_summary(sample, audio, lengths, input_path, tables_dir, output_dir):
    """Write the sample metadata and print the output summary."""
    metadata = {
        'first_year': 1960,
        'last_year': 2019,
        'songs': len(sample),
        'complete_audio': len(audio),
        'known_duration': len(lengths),
        'missing_audio': len(sample) - len(audio),
        'missing_audio_with_genre': int((~sample.eda_core_complete & sample.has_genre).sum()),
        'input_file': input_path.name,
        'unit': 'one song, assigned to first observed chart decade',
        'audio_sample': 'all four core scores present',
        'duration_sample': 'duration present',
        'genre_warning': 'artist-tag keyword buckets; exploratory and not manually validated',
    }
    (tables_dir / 'summary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))
    print(f"Wrote {len(list(output_dir.glob('*.svg')))} SVG figures and supporting tables to {output_dir}")


def main():
    """Load the song table, generate each story, and export supporting data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        type=Path,
        default=ROOT / 'data/processed/songs_features.csv'
    )
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/figures')
    args = parser.parse_args()

    # Audio charts require all four scores, duration charts only require length
    sample, audio, lengths = load_data(args.input)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / 'data'
    tables_dir.mkdir(exist_ok=True)

    configure_plot_style()
    audio_medians, duration_summary = summarize_decades(audio, lengths, tables_dir)

    # Start with the overall trends, then explore the three main stories.
    plot_duration_overview(duration_summary, output_dir)
    plot_audio_overview(audio, tables_dir, output_dir)
    plot_valence_danceability(audio, tables_dir, output_dir)
    plot_short_songs(duration_summary, output_dir)
    plot_recent_duration(lengths, tables_dir, output_dir)
    plot_acoustic_shift(audio_medians, output_dir)

    # Supporting analysis: genre differences and the limits of missing data.
    plot_fixed_genre_mix(audio, tables_dir, output_dir)
    plot_genre_acousticness(audio, lengths, tables_dir, output_dir)
    plot_audio_coverage(sample, tables_dir, output_dir)
    plot_genre_overview(tables_dir, output_dir)
    export_missing_audio_sensitivity(sample, tables_dir)
    write_summary(sample, audio, lengths, args.input, tables_dir, output_dir)


if __name__ == '__main__':
    main()
