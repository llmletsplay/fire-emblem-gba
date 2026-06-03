# Fire Emblem 8: The Sacred Stones - Map Assets

## Map File Naming Convention

Place chapter maps in this directory following these naming patterns:

### Standard Chapters
- `fe8-chapter1-map.png` - Chapter 1: Escape!
- `fe8-chapter2-map.png` - Chapter 2: The Protected
- `fe8-chapter3-map.png` - Chapter 3: The Bandits of Borgo
- `fe8-chapter4-map.png` - Chapter 4: Ancient Horrors
- `fe8-chapter5-map.png` - Chapter 5: The Empire's Reach
- `fe8-chapter6-map.png` - Chapter 6: Victims of War
- `fe8-chapter7-map.png` - Chapter 7: Waterside Renvall
- `fe8-chapter8-map.png` - Chapter 8: It's a Trap!

### Route Split (Eirika's Route)
- `fe8-chapter9-eirika-map.png` - Chapter 9: Distant Blade
- `fe8-chapter10-eirika-map.png` - Chapter 10: Revolt at Carcino
- `fe8-chapter11-eirika-map.png` - Chapter 11: Creeping Darkness
- `fe8-chapter12-eirika-map.png` - Chapter 12: Village of Silence
- `fe8-chapter13-eirika-map.png` - Chapter 13: Hamill Canyon
- `fe8-chapter14-eirika-map.png` - Chapter 14: Queen of White Dunes
- `fe8-chapter15-eirika-map.png` - Chapter 15: Scorched Sand
- `fe8-chapter16-eirika-map.png` - Chapter 16: Ruled by Madness

### Route Split (Ephraim's Route)
- `fe8-chapter9-ephraim-map.png` - Chapter 9: Fort Rigwald
- `fe8-chapter10-ephraim-map.png` - Chapter 10: Turning Traitor
- `fe8-chapter11-ephraim-map.png` - Chapter 11: Phantom Ship
- `fe8-chapter12-ephraim-map.png` - Chapter 12: Landing at Taizel
- `fe8-chapter13-ephraim-map.png` - Chapter 13: Fluorspar's Oath
- `fe8-chapter14-ephraim-map.png` - Chapter 14: Father and Son
- `fe8-chapter15-ephraim-map.png` - Chapter 15: Scorched Sand
- `fe8-chapter16-ephraim-map.png` - Chapter 16: Ruled by Madness

### Final Chapters (Shared)
- `fe8-chapter17-map.png` - Chapter 17: River of Regrets
- `fe8-chapter18-map.png` - Chapter 18: Two Faces of Evil
- `fe8-chapter19-map.png` - Chapter 19: Last Hope
- `fe8-chapter20-map.png` - Chapter 20: Darkling Woods
- `fe8-chapter21-map.png` - Chapter 21: Sacred Stone

### Special/Gaiden Chapters
- `fe8-chapter5x-map.png` - Chapter 5x: Unbroken Heart

## Map Sources
You can obtain chapter maps from:
- https://fireemblemwiki.org/wiki/Main_Page
- https://fireemblem.fandom.com/wiki/Fire_Emblem:_The_Sacred_Stones
- In-game screenshots with UI disabled

## Map Requirements
- PNG format preferred
- Recommended resolution: Original GBA resolution (240x160) or scaled up versions
- Clear visibility of terrain types
- Grid overlay optional (can be added programmatically)

## Integration with Vision Model
Maps will be used to provide context to the vision model about:
- Terrain types and movement costs
- Objective locations
- Enemy positions and reinforcement points
- Treasure chest locations

Enable/disable map integration in `config.py` with `USE_MAP_CONTEXT = True/False`