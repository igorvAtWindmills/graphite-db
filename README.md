# graphite-db

Personal knowledge base of movies, TV shows, and anime. Entries are plain markdown files with YAML frontmatter, designed for [Obsidian](https://obsidian.md). Connections between works emerge through shared cast and crew — no editorial recommendations, no genre groupings, only people.

## Setup

```bash
pip install requests
cp .env.example .env  # add your TMDB API token
```

Get a TMDB API token at https://www.themoviedb.org/settings/api (use the Read Access Token).

## Usage

```bash
gm "The Dark Knight"
gm "Adolescence" 2025
gm https://www.themoviedb.org/movie/155
gm https://www.themoviedb.org/tv/249042
gm --undo
```

Or directly: `python fetch_movie.py "Title"`.

Each entry gets a full cast and crew list. Every person mentioned gets their own file listing all their works in the database. The Obsidian graph view turns this into a connection map.

## Structure

```
graphite/
├── movies/
├── tv/
├── anime/
└── people/
```
