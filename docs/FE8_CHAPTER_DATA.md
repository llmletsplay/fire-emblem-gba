# Fire Emblem 8: Chapter Objectives Reference

Source of truth for `src/data/fe8_chapters.py`. Boss char IDs from FE8 decomp `constants/characters.h`.

## Shared Route (Prologue - Chapter 8)

Both Eirika and Ephraim routes play these chapters.

| Ch | Name | Objective | Boss | Boss ID | New Units |
|----|------|-----------|------|---------|-----------|
| 0 | Prologue: The Fall of Renais | Defeat boss O'Neill | O'Neill | `0x68` | Eirika, Seth |
| 1 | Chapter 1: Escape! | Seize gate | Breguet | `0x46` | Franz, Gilliam |
| 2 | Chapter 2: The Protected | Defeat boss Bone | Bone | `0x47` | Ross, Garcia, Moulder |
| 3 | Chapter 3: The Bandits of Borgo | Defeat boss Bazba | Bazba | `0x48` | Neimi, Colm |
| 4 | Chapter 4: Ancient Horrors | Defeat all monsters | - | - | Artur, Lute |
| 5 | Chapter 5: The Empire's Reach | Seize throne | Saar | `0x4A` | Natasha, Joshua |
| 5x | Chapter 5x: Unbroken Heart | Survive 7 turns | - | - | Ephraim, Kyle, Forde, Orson |
| 6 | Chapter 6: Victims of War | Seize throne | Novala | `0x4B` | - |
| 7 | Chapter 7: Waterside Renvall | Seize throne | Murray | `0x4C` | Vanessa, Tana |
| 8 | Chapter 8: It's a Trap! | Seize throne | Tirado | `0x4D` | Ephraim (joins party) |

## Eirika Route (Chapters 9-20 + Final)

Selected when choosing Eirika after Chapter 8.

| Ch | Name | Objective | Boss | Boss ID | New Units |
|----|------|-----------|------|---------|-----------|
| 9 | Distant Blade | Seize throne | - | - | Tethys, Gerik, Marisa, Innes |
| 10 | Revolt at Carcino | Defeat boss Pablo | Pablo | `0x4F` | - |
| 11 | Creeping Darkness | Defeat all monsters | - | - | L'Arachel, Dozla |
| 12 | Village of Silence | Defeat boss Gheb | Gheb | `0x5A` | Ewan, Cormag |
| 13 | Hamill Canyon | Defeat boss Aias | Aias | `0x51` | Saleh |
| 14 | Queen of White Dunes | Seize throne | Carlyle | `0x52` | Rennac |
| 15 | Scorched Sand | Defeat boss Caellach | Caellach | `0x53` | Myrrh |
| 16 | Ruled by Madness | Seize throne | Orson | `0x6D` | Duessel |
| 17 | River of Regret | Defeat boss Riev | Riev | `0x57` | Syrene |
| 18 | Two Faces of Evil | Defeat boss Vigarde | Vigarde | `0x6B` | Knoll |
| 19 | Last Hope | Rout (defeat all) | - | - | - |
| 20 | Darkling Woods | Defeat boss Morva | Morva | `0x41` | - |
| 21 | Final: Sacred Stone | Defeat Fomortiis | Fomortiis | `0xBE` | - |

## Ephraim Route (Chapters 9-20 + Final)

**Status**: Not yet implemented in `fe8_chapters.py`. Uses different chapter numbers in memory.

| Ch | Name | Objective | Boss | Notes |
|----|------|-----------|------|-------|
| 9 | Fort Rigwald | Seize | - | TBD |
| 10 | Turning Traitor | Defeat boss | Beran | TBD |
| 11 | Phantom Ship | Rout | - | TBD |
| 12 | Landing at Taizel | Defeat boss | - | TBD |
| 13 | Fluorspar's Oath | Seize | Aias | TBD |
| 14 | Father and Son | Seize | Vigarde | TBD |
| 15+ | (shared with Eirika from Ch15) | - | - | Same as above |

## Objective Types

| Type | Description | How to Complete |
|------|-------------|-----------------|
| `seize` | Move Lord to throne/gate | Eirika/Ephraim must stand on tile and select "Seize" |
| `defeat_boss` | Kill the named boss | Boss is usually on the throne |
| `rout` | Defeat all enemies | Every enemy on the map must be killed |
| `survive` | Survive for N turns | Keep lord alive until turn limit |

## Recruitment Notes

Some chapters have recruitable enemies or NPCs with special conditions:
- **Ch5**: Joshua is an enemy myrmidon — talk to him with Natasha
- **Ch9 (Eirika)**: Marisa — talk with Gerik
- **Ch12 (Eirika)**: Cormag — talk with Eirika
- **Ch14 (Eirika)**: Rennac — talk with L'Arachel or pay gold

## Verification Status

- Prologue through Ch8: Chapter numbers verified in memory
- Eirika Ch9-21: Chapter numbers assumed sequential (need live verification for later chapters)
- Ephraim route: Not yet mapped to memory chapter numbers
- Seize positions: None verified (coordinates vary by map)
- Boss char IDs: All from decomp `constants/characters.h`
