# Unify 🎵

A terminal music player powered by YouTube Music. Search songs, get synced lyrics, manage playlists — all from your terminal. Works out of the box on Linux, macOS and Windows.

> Unofficial client. Not affiliated with YouTube or Google.

---

![Unify player](https://raw.githubusercontent.com/Nexora-get/unify/main/screenshots/player.webp)

---

## Requirements

- **Python 3.8+** — everything else installs automatically

---

## Run

```bash
python3 unify.py    # Linux / macOS
py unify.py         # Windows
```

First run takes ~30 seconds to set up. Every run after is instant.

---

## Troubleshooting

**Something broke** → press `D` inside the app — the debug panel shows exactly what's failing

**Search doesn't work** → YouTube changed their API; wait 24h for the auto-update, or force it:
```bash
~/.unify/env/bin/pip install -U ytmusicapi yt-dlp          # Linux/macOS
%USERPROFILE%\.unify\env\Scripts\pip install -U ytmusicapi yt-dlp  # Windows
```

**Songs skip instantly** → open debug panel (`D`), check MPV STDERR section

**mpv won't install on Windows** → run `winget install Mpv.Mpv` in PowerShell, or [download manually](https://sourceforge.net/projects/mpv-player-windows/files/64bit/)

**No lyrics** → that song isn't in [lrclib.net](https://lrclib.net)'s database yet

**Reset everything** → delete `~/.unify/` (Linux/macOS) or `%USERPROFILE%\.unify\` (Windows), then run again

**Still stuck?** → join the Discord: **[discord.gg/kWVPEHr3nA](https://discord.gg/kWVPEHr3nA)**  
Share what the `D` debug panel shows when asking for help.

---

## How to Use

**Search & Play**
- `s` → type a song/artist → `Enter` to search
- `↑` / `↓` to browse results → `Enter` to play

**Home Screen**
- `Tab` → opens home screen (recent plays + recommendations)
- `Tab` again → switch between Recent and Recommended
- `Enter` to play any track

**Queue**
- `q` → add selected track to queue
- `Q` → show/hide queue panel
- `r` → remove track from queue

**Playlists**
- `a` → save selected track to a playlist
- `A` → create playlist by typing song names (Unify searches them)
- `L` → load a saved playlist
- `r` → remove track from loaded playlist

**Lyrics**
- Load automatically — synced when available, plain text as fallback
- `j` / `k` → scroll lyrics down / up

---

## All Keys

| Key | Action |
|-----|--------|
| `s` | Search |
| `Enter` | Play selected |
| `Space` / `p` | Pause / resume |
| `n` | Next track |
| `b` | Previous track |
| `→` / `←` | Seek ±5 seconds |
| `+` / `-` | Volume up / down |
| `S` | Toggle shuffle |
| `↑` / `↓` | Move selection |
| `Tab` | Home screen |
| `g` | Jump to song number |
| `q` | Add to queue |
| `Q` | Show / hide queue |
| `r` | Remove from queue / playlist |
| `L` | Load playlist |
| `a` | Save to playlist |
| `A` | Create / edit playlist |
| `j` / `k` | Scroll lyrics |
| `D` | Debug panel |
| `W` | Refresh recommendations |
| `Esc` / `Ctrl+C` | Quit |

---

## File Locations

**Linux / macOS**
| | Path |
|-|------|
| Dependencies | `~/.unify/env/` |
| Playlists | `~/.config/unify_playlists.json` |
| History | `~/.config/unify_history.json` |

**Windows**
| | Path |
|-|------|
| Dependencies | `%USERPROFILE%\.unify\env\` |
| Playlists | `%USERPROFILE%\.config\unify_playlists.json` |
| History | `%USERPROFILE%\.config\unify_history.json` |
| mpv | `%LOCALAPPDATA%\mpv\` |

---

## Credits

Built with [mpv](https://mpv.io), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [Rich](https://github.com/Textualize/rich), lyrics from [lrclib.net](https://lrclib.net). All open source.

---

## Made by

[@aceauspicio](https://github.com/aceauspicio) · [@itsrachitraj](https://github.com/itsrachitraj)
