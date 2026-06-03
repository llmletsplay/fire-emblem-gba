# ROMs Directory

Place legally obtained local ROMs and saves here. This directory is ignored by
Git and must remain private.

Supported ROMs:

- `FE7.gba` - Fire Emblem 7: The Blazing Blade (USA, `AE7E`)
- `FE8.gba` - Fire Emblem 8: The Sacred Stones (USA, `BE8E`)

Configure the active game in `.env`:

```dotenv
FE_GAME=fe7
ROM_FILE=FE7.gba
```

or:

```dotenv
FE_GAME=fe8
ROM_FILE=FE8.gba
```

`FE_GAME` can be omitted when the filename is clear, but setting it explicitly
is recommended. Do not upload ROMs, saves, or savestates in issues or pull
requests.
