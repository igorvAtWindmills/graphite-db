# graphite

A personal movie and TV database. You add a title, it pulls the full cast and crew from TMDB and creates a markdown file for the title and one for every person in it. Open it in Obsidian and the graph view shows how everything connects — not by genre or mood, just by people.

## Setup

1. Get a TMDB Read Access Token at https://www.themoviedb.org/settings/api
2. Put it in a `.env` file: `TMDB_API_TOKEN=your_token_here`
3. `pip install requests`

## Add something

```bash
python fetch.py "The Dark Knight"
python fetch.py "Adolescence" 2025
python fetch.py https://www.themoviedb.org/movie/155
python fetch.py --undo   # remove the last thing you added
```

## How it works

Each title gets a markdown file with cast, crew, and metadata. Each person gets a file listing everything they appear in. The connections live in the graph, not in the files.

```
graphite/
├── movies/
├── tv/
├── anime/
└── people/
```
