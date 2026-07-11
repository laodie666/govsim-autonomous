# Smallville-Style Pixel Art Visual Specification

## Overview

This document specifies how to transform the current hand-drawn vector art visualizer into a Smallville-style top-down pixel art tile map using the Kenney RPG Urban Kit (CC0). The aesthetic should be retro, 16-bit RPG town with crisp pixel edges, no anti-aliasing.

---

## A. Annotated Tile Grid Mockup

### Grid Dimensions
- **Map size**: 40 columns × 25 rows
- **Tile size**: 32px (16×16 Kenney tiles scaled 2×)
- **Viewport**: 1280×800 pixels

### Legend
```
. = grass (ground tile)
# = building wall
+ = door
- = window
~ = water (lake)
T = tree (foliage)
P = dirt path
R = road (stone/paved)
F = floor (interior)
= = roof (top row of building)
```

### Tile Grid Layout (40×25)

```
Row 0:  T..T......................................T..T
Row 1:  ................................................
Row 2:  ....#####..................................#####
Row 3:  ....#FFF#..................................#FFF#
Row 4:  ....#F-F#..................................#F-F#
Row 5:  ....#F+F#..................................#F+F#
Row 6:  ....#####..................................#####
Row 7:  ......P......................................P..
Row 8:  ......P......................................P..
Row 9:  ..T...P.................T....................P..
Row 10: .....P......................................P...
Row 11: .....P..........#####.......................P...
Row 12: .....P..........#FFF#.......................P...
Row 13: ..T...P..........#F-F#..........T...........P...
Row 14: .....P..........#F+F#.......................P...
Row 15: .....P..........#####.......................P...
Row 16: .....P......................................P...
Row 17: .....P......................................P...
Row 18: ..T...P......................................P..
Row 19: .....P......................................P...
Row 20: .....P......................................P...
Row 21: .....P......................................P...
Row 22: .....P......................................P...
Row 23: .....P......................................P...
Row 24: .....P......................................P...
```

**Wait — let me redo this with the actual layout from the screenshot:**

### Corrected Layout (matching current screenshot positions)

```
Row 0:  T..T......................................T..T
Row 1:  ................................................
Row 2:  ..#####....................................#####
Row 3:  ..#FFF#....................................#FFF#
Row 4:  ..#F-F#....................................#F-F#
Row 5:  ..#F+F#....................................#F+F#
Row 6:  ..#####....................................#####
Row 7:  ....P......................................P....
Row 8:  ....P......................................P....
Row 9:  T...P.............T.......................P...T
Row 10: ....P......................................P....
Row 11: ..###.............#####...................###...
Row 12: ..#F#.............#FFF#...................#F#...
Row 13: ..#F#.............#F-F#.............T.....#F#...
Row 14: ..#F#.............#F+F#...................#F#...
Row 15: ..###.............#####...................###...
Row 16: ....P......................................P....
Row 17: ....P......................................P....
Row 18: T...P......................................P...T
Row 19: ....P......................................P....
Row 20: ....P......................................P....
Row 21: ....P......................................P....
Row 22: ....P......................................P....
Row 23: ....P......................................P....
Row 24: ....P......................................P....
```

**Actually, let me create a more accurate layout based on the screenshot:**

### Final Layout (40×25 grid)

The screenshot shows:
- **Town Hall**: Center, ~col 17-23, row 10-15 (6×6 tiles)
- **Alice's home**: Top-left, ~col 3-6, row 3-6 (4×4 tiles)
- **Bob's home**: Top-right, ~col 33-36, row 3-6 (4×4 tiles)
- **Charlie's home**: Mid-left, ~col 3-6, row 11-14 (4×4 tiles)
- **Diana's home**: Mid-right, ~col 33-36, row 11-14 (4×4 tiles)
- **Eve's home**: Bottom-left, ~col 3-6, row 18-21 (4×4 tiles)
- **Frank's home**: Bottom-right, ~col 33-36, row 18-21 (4×4 tiles)
- **Lake**: Bottom-center, ~col 14-26, row 21-24 (12×4 tiles)
- **Paths**: Connect each home to Town Hall
- **Trees**: Scattered around edges and between buildings

```
Col:  0123456789012345678901234567890123456789
Row 0:  T..T..................................T..T
Row 1:  ..........................................
Row 2:  ..#####..............................#####
Row 3:  ..#FFF#..............................#FFF#
Row 4:  ..#F-F#..............................#F-F#
Row 5:  ..#F+F#..............................#F+F#
Row 6:  ..#####..............................#####
Row 7:  ....P................................P....
Row 8:  ....P................................P....
Row 9:  T...P............T..................P...T
Row 10: ....P............#####..............P....
Row 11: ..###............#FFF#..............###..
Row 12: ..#F#............#F-F#..............#F#..
Row 13: ..#F#............#F+F#.......T......#F#..
Row 14: ..#F#............#####..............#F#..
Row 15: ..###.................................###..
Row 16: ....P................................P....
Row 17: ....P................................P....
Row 18: T...P................................P...T
Row 19: ....P................................P....
Row 20: ....P................................P....
Row 21: ....P...........~~~~~~~~~~~~........P....
Row 22: ....P...........~~~~~~~~~~~~........P....
Row 23: ....P...........~~~~~~~~~~~~........P....
Row 24: ....P...........~~~~~~~~~~~~........P....
```

**Note**: The paths (P) should curve naturally from each home to the Town Hall. In the pixel art, use diagonal path tiles where paths bend.

---

## B. Specific Kenney Tile Recommendations

### Ground Tiles
- **Grass**: Use `tile_0000.png` through `tile_0009.png` (grass variants with slight color/texture variation)
  - Primary: `tile_0000.png` (solid green grass)
  - Variation 1: `tile_0001.png` (grass with small flowers)
  - Variation 2: `tile_0002.png` (grass with texture)
  - Randomly distribute these 3 variants across the map for natural look

- **Dirt Path**: Use `tile_0050.png` through `tile_0059.png` (dirt/path tiles)
  - Straight path: `tile_0050.png`
  - Corner/bend: `tile_0051.png`, `tile_0052.png`
  - Intersection: `tile_0053.png`

- **Water (Lake)**: Use `tile_0200.png` through `tile_0209.png` (water tiles)
  - Static water: `tile_0200.png`
  - Animated water (if available): Use tile animation cycle
  - Shore edge: `tile_0205.png` (water-to-grass transition)

### Building Tiles

**Town Hall (6×6 tiles)**:
- **Walls**: Use red/brown building wall tiles (`tile_0100.png` range)
  - Wall: `tile_0100.png` (red brick wall)
  - Wall corner: `tile_0101.png`
- **Roof**: Use darker red/brown roof tiles (`tile_0110.png` range)
  - Roof: `tile_0110.png` (dark red roof)
  - Roof peak: `tile_0111.png`
- **Door**: Use entrance tiles (`tile_0150.png` range)
  - Door: `tile_0150.png` (wooden door)
- **Windows**: Use window tiles (`tile_0120.png` range)
  - Window: `tile_0120.png` (glass window with frame)
- **Floor (interior)**: Use floor tiles (`tile_0130.png` range)
  - Floor: `tile_0130.png` (wooden floor)

**Agent Homes (4×4 tiles each)**:
- Use the same building tile set but with different color variants:
  - **Alice's home**: Red walls (`tile_0100.png`)
  - **Bob's home**: Blue walls (`tile_0105.png` - blue variant)
  - **Charlie's home**: Green walls (`tile_0106.png` - green variant)
  - **Diana's home**: Yellow/orange walls (`tile_0107.png`)
  - **Eve's home**: Purple walls (`tile_0108.png`)
  - **Frank's home**: Teal walls (`tile_0109.png`)

### Foliage Tiles (from Foliage Pack)
- **Trees**: Use `foliagePack_001.png` through `foliagePack_010.png`
  - Large tree: `foliagePack_001.png`
  - Medium tree: `foliagePack_002.png`
  - Small tree: `foliagePack_003.png`
  - Pine tree: `foliagePack_004.png`
  - Randomly place 15-20 trees around the map edges and between buildings

- **Bushes**: Use `foliagePack_020.png` through `foliagePack_025.png`
  - Bush cluster: `foliagePack_020.png`
  - Small bush: `foliagePack_021.png`

- **Flowers**: Use `foliagePack_030.png` through `foliagePack_035.png`
  - Flower cluster: `foliagePack_030.png`
  - Scatter 5-10 flower clusters in grass areas

### Character Sprites
- **Base sprites**: Use character tilesheet from `tilemap.png` (right side, character rows)
  - The tilemap shows 6 character variants with different hair/clothing colors
  - Each character has 4-direction walk animation (up, down, left, right)
  - Each direction has 2-3 animation frames

- **Agent color tinting**:
  - **Alice** (#FF6B6B red): Use character sprite #1, tint clothing red
  - **Bob** (#4ECDC4 teal): Use character sprite #2, tint clothing teal
  - **Charlie** (#FFE66D yellow): Use character sprite #3, tint clothing yellow
  - **Diana** (#95E1D3 mint): Use character sprite #4, tint clothing mint
  - **Frank** (#AA96DA purple): Use character sprite #5, tint clothing purple

---

## C. Color Palette

### Agent Colors (from current AGENT_COLORS)
```
Alice:   #FF6B6B  (coral red)
Bob:     #4ECDC4  (teal)
Charlie: #FFE66D  (yellow)
Diana:   #95E1D3  (mint green)
Frank:   #AA96DA  (lavender purple)
```

### Building Colors
```
Town Hall walls:    #8B4513  (saddle brown)
Town Hall roof:     #654321  (dark brown)
Town Hall door:     #4A2511  (very dark brown)
Town Hall windows:  #87CEEB  (sky blue)
Town Hall floor:    #DEB887  (burlywood)

Alice home walls:   #CD5C5C  (indian red, matches #FF6B6B)
Bob home walls:     #20B2AA  (light sea green, matches #4ECDC4)
Charlie home walls: #F0E68C  (khaki, matches #FFE66D)
Diana home walls:   #98FB98  (pale green, matches #95E1D3)
Eve home walls:     #DDA0DD  (plum, matches #AA96DA)
Frank home walls:   #48D1CC  (medium turquoise, matches #4ECDC4)
```

### Environment Colors
```
Grass:              #90EE90  (light green)
Grass variation 1:  #7CFC00  (lawn green)
Grass variation 2:  #32CD32  (lime green)
Dirt path:          #D2B48C  (tan)
Water:              #87CEEB  (sky blue)
Water deep:         #4682B4  (steel blue)
Tree trunk:         #8B4513  (saddle brown)
Tree leaves:        #228B22  (forest green)
Tree leaves var:    #006400  (dark green)
```

---

## D. Layout Requirements

### Town Hall (Center)
- **Position**: Center of map, approximately col 17-23, row 10-15
- **Size**: 6×6 tiles (largest building)
- **Features**:
  - Red/brown brick walls on all 4 sides
  - Dark brown roof (top row of tiles)
  - Wooden door at bottom-center (col 20, row 15)
  - Windows on left and right walls (2 windows each side)
  - Wooden floor visible through door
  - Flag pole on roof (optional, use `tile_0160.png` if available)

### Agent Homes (Scattered)
- **Size**: 4×4 tiles each (smaller than Town Hall)
- **Positions**:
  - Alice: Top-left (col 3-6, row 3-6)
  - Bob: Top-right (col 33-36, row 3-6)
  - Charlie: Mid-left (col 3-6, row 11-14)
  - Diana: Mid-right (col 33-36, row 11-14)
  - Eve: Bottom-left (col 3-6, row 18-21)
  - Frank: Bottom-right (col 33-36, row 18-21)
- **Features**:
  - Each home has unique wall color matching agent color
  - Door at bottom-center
  - 1-2 windows on side walls
  - Roof on top row

### Paths
- **Width**: 1 tile wide
- **Connections**: Each home connects to Town Hall via dirt path
- **Style**: Use dirt/path tiles with natural curves
- **Layout**:
  - Alice's path: Goes right from home, then down to Town Hall
  - Bob's path: Goes left from home, then down to Town Hall
  - Charlie's path: Goes right from home, then down to Town Hall
  - Diana's path: Goes left from home, then down to Town Hall
  - Eve's path: Goes right from home, then up to Town Hall
  - Frank's path: Goes left from home, then up to Town Hall
  - Town Hall to Lake: Path goes straight down from Town Hall door to lake shore

### Lake
- **Position**: Bottom-center, col 14-26, row 21-24
- **Size**: 12×4 tiles
- **Features**:
  - Water tiles in center
  - Shore/grass transition tiles on edges
  - Optional: Add 2-3 rocks near shore (`foliagePack_040.png`)

### Trees and Decorations
- **Tree count**: 15-20 trees total
- **Placement**:
  - 2-3 trees near each home (but not blocking paths)
  - 4-5 trees along map edges (top, bottom, left, right)
  - 2-3 trees between Town Hall and lake
  - 2-3 trees scattered in open grass areas
- **Bushes**: 5-8 bush clusters near trees
- **Flowers**: 5-10 flower clusters in grass areas

---

## E. Differences from Current Screenshot

### What Changes

| Current (Hand-drawn) | New (Pixel Art) |
|---------------------|-----------------|
| Smooth, rounded buildings with triangular roofs | Blocky pixel art buildings with flat roof tiles |
| Smooth gradient grass background | Tiled grass with texture variation (3 grass tile variants) |
| Circular trees with smooth gradients | Pixel art tree tiles (16×16 scaled 2×) |
| Curved smooth paths | Dirt path tiles with pixel-perfect edges |
| Flat colored agent circles | Kenney character sprites (4-direction walk animation) |
| Smooth oval lake with gradient | Water tiles with pixel edges, shore transition tiles |
| Rounded speech bubbles with smooth borders | Pixel-art speech bubbles (blocky corners, 1px border) |
| Anti-aliased edges everywhere | Crisp pixel edges, no anti-aliasing |
| Children's storybook illustration style | Retro 16-bit RPG town aesthetic |

### Specific Visual Changes

1. **Buildings**:
   - Remove smooth curves and gradients
   - Replace with blocky wall tiles (1px pixel edges)
   - Roof becomes flat row of darker tiles (not triangular)
   - Windows become simple 2×2 pixel squares with frame

2. **Ground**:
   - Remove smooth gradient background
   - Replace with tiled grass (randomly distribute 3 grass variants)
   - Add subtle texture variation

3. **Trees**:
   - Remove circular smooth trees
   - Replace with pixel art tree tiles (trunk + leaf canopy)
   - Trees should look like 16-bit RPG trees

4. **Paths**:
   - Remove smooth curved paths
   - Replace with dirt path tiles
   - Paths should have pixel-perfect edges

5. **Agents**:
   - Remove colored circles
   - Replace with Kenney character sprites
   - Tint clothing to match agent colors
   - Add 4-direction walk animation

6. **Lake**:
   - Remove smooth oval with gradient
   - Replace with water tiles
   - Add shore transition tiles
   - Water should look like 16-bit RPG water

7. **Speech Bubbles**:
   - Remove rounded corners and smooth borders
   - Replace with pixel-art style bubbles (blocky corners)
   - Use 1px border, white fill, black text
   - Pointer should be pixel-perfect triangle

---

## F. Implementation Notes for Blind Implementer

### Step 1: Setup Tile System

```typescript
// Tile configuration
const TILE_SIZE = 32; // pixels (16×16 Kenney tiles scaled 2×)
const MAP_WIDTH = 40; // tiles
const MAP_HEIGHT = 25; // tiles
const VIEWPORT_WIDTH = 1280; // pixels
const VIEWPORT_HEIGHT = 800; // pixels

// Tile types enum
enum TileType {
  GRASS = 'grass',
  PATH = 'path',
  WATER = 'water',
  WALL = 'wall',
  ROOF = 'roof',
  DOOR = 'door',
  WINDOW = 'window',
  FLOOR = 'floor',
  TREE = 'tree',
  BUSH = 'bush',
  FLOWER = 'flower',
}
```

### Step 2: Load Tile Assets

```typescript
// Load individual tile images
const tileImages = {
  grass: [
    '/sprites/tiles/tile_0000.png',
    '/sprites/tiles/tile_0001.png',
    '/sprites/tiles/tile_0002.png',
  ],
  path: '/sprites/tiles/tile_0050.png',
  water: '/sprites/tiles/tile_0200.png',
  wall: {
    red: '/sprites/tiles/tile_0100.png',
    blue: '/sprites/tiles/tile_0105.png',
    green: '/sprites/tiles/tile_0106.png',
    yellow: '/sprites/tiles/tile_0107.png',
    purple: '/sprites/tiles/tile_0108.png',
    teal: '/sprites/tiles/tile_0109.png',
  },
  roof: '/sprites/tiles/tile_0110.png',
  door: '/sprites/tiles/tile_0150.png',
  window: '/sprites/tiles/tile_0120.png',
  floor: '/sprites/tiles/tile_0130.png',
  tree: [
    '/sprites/nature/foliagePack_001.png',
    '/sprites/nature/foliagePack_002.png',
    '/sprites/nature/foliagePack_003.png',
  ],
  bush: '/sprites/nature/foliagePack_020.png',
  flower: '/sprites/nature/foliagePack_030.png',
};

// Preload all images
await Promise.all(Object.values(tileImages).flat().map(src => {
  const img = new Image();
  img.src = src;
  return new Promise(resolve => img.onload = resolve);
}));
```

### Step 3: Define Map Layout

```typescript
// Map grid (40×25)
// Each cell contains tile type and optional variant
const mapGrid: TileCell[][] = [];

// Initialize with grass
for (let y = 0; y < MAP_HEIGHT; y++) {
  mapGrid[y] = [];
  for (let x = 0; x < MAP_WIDTH; x++) {
    mapGrid[y][x] = {
      type: TileType.GRASS,
      variant: Math.floor(Math.random() * 3), // Random grass variant
    };
  }
}

// Place Town Hall (6×6, center)
const townHallX = 17;
const townHallY = 10;
for (let y = townHallY; y < townHallY + 6; y++) {
  for (let x = townHallX; x < townHallX + 6; x++) {
    if (y === townHallY) {
      mapGrid[y][x] = { type: TileType.ROOF };
    } else if (y === townHallY + 5 && x === townHallX + 2) {
      mapGrid[y][x] = { type: TileType.DOOR };
    } else if (y === townHallY + 5) {
      mapGrid[y][x] = { type: TileType.WALL, variant: 'red' };
    } else if (x === townHallX || x === townHallX + 5) {
      mapGrid[y][x] = { type: TileType.WINDOW };
    } else {
      mapGrid[y][x] = { type: TileType.FLOOR };
    }
  }
}

// Place agent homes (4×4 each)
const homes = [
  { name: 'Alice', x: 3, y: 3, color: 'red' },
  { name: 'Bob', x: 33, y: 3, color: 'blue' },
  { name: 'Charlie', x: 3, y: 11, color: 'green' },
  { name: 'Diana', x: 33, y: 11, color: 'yellow' },
  { name: 'Eve', x: 3, y: 18, color: 'purple' },
  { name: 'Frank', x: 33, y: 18, color: 'teal' },
];

homes.forEach(home => {
  for (let y = home.y; y < home.y + 4; y++) {
    for (let x = home.x; x < home.x + 4; x++) {
      if (y === home.y) {
        mapGrid[y][x] = { type: TileType.ROOF };
      } else if (y === home.y + 3 && x === home.x + 1) {
        mapGrid[y][x] = { type: TileType.DOOR };
      } else if (y === home.y + 3) {
        mapGrid[y][x] = { type: TileType.WALL, variant: home.color };
      } else if (x === home.x || x === home.x + 3) {
        mapGrid[y][x] = { type: TileType.WINDOW };
      } else {
        mapGrid[y][x] = { type: TileType.FLOOR };
      }
    }
  }
});

// Place lake (12×4, bottom-center)
const lakeX = 14;
const lakeY = 21;
for (let y = lakeY; y < lakeY + 4; y++) {
  for (let x = lakeX; x < lakeX + 12; x++) {
    mapGrid[y][x] = { type: TileType.WATER };
  }
}

// Place paths (connect homes to Town Hall)
// Alice's path: right then down
for (let x = 6; x <= 17; x++) {
  mapGrid[5][x] = { type: TileType.PATH };
}
for (let y = 5; y <= 10; y++) {
  mapGrid[y][17] = { type: TileType.PATH };
}

// Bob's path: left then down
for (let x = 23; x <= 33; x++) {
  mapGrid[5][x] = { type: TileType.PATH };
}
for (let y = 5; y <= 10; y++) {
  mapGrid[y][23] = { type: TileType.PATH };
}

// Charlie's path: right then down
for (let x = 6; x <= 17; x++) {
  mapGrid[13][x] = { type: TileType.PATH };
}
for (let y = 13; y <= 15; y++) {
  mapGrid[y][17] = { type: TileType.PATH };
}

// Diana's path: left then down
for (let x = 23; x <= 33; x++) {
  mapGrid[13][x] = { type: TileType.PATH };
}
for (let y = 13; y <= 15; y++) {
  mapGrid[y][23] = { type: TileType.PATH };
}

// Eve's path: right then up
for (let x = 6; x <= 17; x++) {
  mapGrid[20][x] = { type: TileType.PATH };
}
for (let y = 15; y <= 20; y++) {
  mapGrid[y][17] = { type: TileType.PATH };
}

// Frank's path: left then up
for (let x = 23; x <= 33; x++) {
  mapGrid[20][x] = { type: TileType.PATH };
}
for (let y = 15; y <= 20; y++) {
  mapGrid[y][23] = { type: TileType.PATH };
}

// Town Hall to Lake path
for (let y = 15; y <= 21; y++) {
  mapGrid[y][20] = { type: TileType.PATH };
}

// Place trees (15-20 trees)
const treePositions = [
  { x: 1, y: 1 }, { x: 38, y: 1 },
  { x: 1, y: 9 }, { x: 38, y: 9 },
  { x: 1, y: 18 }, { x: 38, y: 18 },
  { x: 10, y: 2 }, { x: 29, y: 2 },
  { x: 10, y: 23 }, { x: 29, y: 23 },
  { x: 8, y: 8 }, { x: 31, y: 8 },
  { x: 8, y: 16 }, { x: 31, y: 16 },
  { x: 15, y: 18 }, { x: 24, y: 18 },
];

treePositions.forEach(pos => {
  if (mapGrid[pos.y] && mapGrid[pos.y][pos.x]) {
    mapGrid[pos.y][pos.x] = {
      type: TileType.TREE,
      variant: Math.floor(Math.random() * 3),
    };
  }
});
```

### Step 4: Render Map (Z-order)

```typescript
function renderMap(ctx: CanvasRenderingContext2D) {
  // Z-order: ground → paths → buildings → decorations → agents → UI
  
  // Layer 1: Ground tiles (grass)
  for (let y = 0; y < MAP_HEIGHT; y++) {
    for (let x = 0; x < MAP_WIDTH; x++) {
      const cell = mapGrid[y][x];
      if (cell.type === TileType.GRASS) {
        const img = tileImages.grass[cell.variant];
        ctx.drawImage(img, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
  
  // Layer 2: Paths
  for (let y = 0; y < MAP_HEIGHT; y++) {
    for (let x = 0; x < MAP_WIDTH; x++) {
      const cell = mapGrid[y][x];
      if (cell.type === TileType.PATH) {
        ctx.drawImage(tileImages.path, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
  
  // Layer 3: Water
  for (let y = 0; y < MAP_HEIGHT; y++) {
    for (let x = 0; x < MAP_WIDTH; x++) {
      const cell = mapGrid[y][x];
      if (cell.type === TileType.WATER) {
        ctx.drawImage(tileImages.water, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
  
  // Layer 4: Buildings (walls, roof, door, window, floor)
  for (let y = 0; y < MAP_HEIGHT; y++) {
    for (let x = 0; x < MAP_WIDTH; x++) {
      const cell = mapGrid[y][x];
      if ([TileType.WALL, TileType.ROOF, TileType.DOOR, TileType.WINDOW, TileType.FLOOR].includes(cell.type)) {
        let img;
        if (cell.type === TileType.WALL) {
          img = tileImages.wall[cell.variant];
        } else {
          img = tileImages[cell.type];
        }
        ctx.drawImage(img, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
  
  // Layer 5: Decorations (trees, bushes, flowers)
  for (let y = 0; y < MAP_HEIGHT; y++) {
    for (let x = 0; x < MAP_WIDTH; x++) {
      const cell = mapGrid[y][x];
      if (cell.type === TileType.TREE) {
        const img = tileImages.tree[cell.variant];
        ctx.drawImage(img, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      } else if (cell.type === TileType.BUSH) {
        ctx.drawImage(tileImages.bush, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      } else if (cell.type === TileType.FLOWER) {
        ctx.drawImage(tileImages.flower, x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }
}
```

### Step 5: Character Sprites and Animation

```typescript
// Character sprite configuration
const CHARACTER_SPRITE_SIZE = 32; // 16×16 scaled 2×
const ANIMATION_FRAMES = 3; // frames per direction
const DIRECTIONS = ['up', 'down', 'left', 'right'];

// Agent configuration
const agents = [
  { name: 'Alice', color: '#FF6B6B', spriteIndex: 0 },
  { name: 'Bob', color: '#4ECDC4', spriteIndex: 1 },
  { name: 'Charlie', color: '#FFE66D', spriteIndex: 2 },
  { name: 'Diana', color: '#95E1D3', spriteIndex: 3 },
  { name: 'Frank', color: '#AA96DA', spriteIndex: 4 },
];

// Load character sprites from tilemap
// The tilemap has character sprites on the right side
// Each character has 4 directions × 3 frames = 12 tiles
// Extract individual character sprites from tilemap

function tintSprite(sourceCanvas: HTMLCanvasElement, color: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = sourceCanvas.width;
  canvas.height = sourceCanvas.height;
  const ctx = canvas.getContext('2d')!;
  
  ctx.drawImage(sourceCanvas, 0, 0);
  
  // Get image data
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;
  
  // Parse target color
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  
  // Tint non-transparent pixels
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] > 0) { // If not transparent
      // Blend with target color (preserve luminance)
      const luminance = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) / 255;
      data[i] = r * luminance;
      data[i + 1] = g * luminance;
      data[i + 2] = b * luminance;
    }
  }
  
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

// Render agent at position
function renderAgent(ctx: CanvasRenderingContext2D, agent: Agent, x: number, y: number) {
  const sprite = getCharacterSprite(agent.spriteIndex, agent.direction, agent.animationFrame);
  const tintedSprite = tintSprite(sprite, agent.color);
  
  ctx.drawImage(tintedSprite, x, y, CHARACTER_SPRITE_SIZE, CHARACTER_SPRITE_SIZE);
  
  // Draw agent name above sprite
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '12px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(agent.name, x + CHARACTER_SPRITE_SIZE / 2, y - 5);
}
```

### Step 6: Movement Animation

```typescript
// When agent moves from tile A to tile B
function animateAgentMovement(agent: Agent, fromX: number, fromY: number, toX: number, toY: number) {
  const duration = 500; // ms
  const startTime = Date.now();
  
  function animate() {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // Ease-out interpolation
    const eased = 1 - Math.pow(1 - progress, 3);
    
    const currentX = fromX + (toX - fromX) * eased;
    const currentY = fromY + (toY - fromY) * eased;
    
    // Update agent pixel position
    agent.pixelX = currentX;
    agent.pixelY = currentY;
    
    // Update animation frame based on direction
    agent.animationFrame = Math.floor(progress * ANIMATION_FRAMES) % ANIMATION_FRAMES;
    
    if (progress < 1) {
      requestAnimationFrame(animate);
    } else {
      // Movement complete
      agent.tileX = toX / TILE_SIZE;
      agent.tileY = toY / TILE_SIZE;
    }
  }
  
  animate();
}
```

### Step 7: Speech Bubbles (Pixel Art Style)

```typescript
function renderSpeechBubble(ctx: CanvasRenderingContext2D, agent: Agent, text: string) {
  const bubbleWidth = 200;
  const bubbleHeight = 60;
  const x = agent.pixelX;
  const y = agent.pixelY - bubbleHeight - 10;
  
  // White fill
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(x, y, bubbleWidth, bubbleHeight);
  
  // Black border (1px)
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, bubbleWidth, bubbleHeight);
  
  // Pointer (pixel-perfect triangle)
  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.moveTo(x + bubbleWidth / 2 - 5, y + bubbleHeight);
  ctx.lineTo(x + bubbleWidth / 2 + 5, y + bubbleHeight);
  ctx.lineTo(x + bubbleWidth / 2, y + bubbleHeight + 8);
  ctx.closePath();
  ctx.fill();
  
  ctx.strokeStyle = '#000000';
  ctx.stroke();
  
  // Text
  ctx.fillStyle = '#000000';
  ctx.font = '12px monospace';
  ctx.textAlign = 'left';
  
  // Word wrap
  const words = text.split(' ');
  let line = '';
  let lineY = y + 15;
  const lineHeight = 14;
  const padding = 10;
  
  words.forEach(word => {
    const testLine = line + word + ' ';
    const metrics = ctx.measureText(testLine);
    
    if (metrics.width > bubbleWidth - padding * 2 && line !== '') {
      ctx.fillText(line, x + padding, lineY);
      line = word + ' ';
      lineY += lineHeight;
    } else {
      line = testLine;
    }
  });
  ctx.fillText(line, x + padding, lineY);
}
```

### Step 8: Main Render Loop

```typescript
function render() {
  const ctx = canvas.getContext('2d')!;
  
  // Clear canvas
  ctx.clearRect(0, 0, VIEWPORT_WIDTH, VIEWPORT_HEIGHT);
  
  // Render map (ground, paths, buildings, decorations)
  renderMap(ctx);
  
  // Render agents (sorted by Y position for depth)
  const sortedAgents = [...agents].sort((a, b) => a.pixelY - b.pixelY);
  sortedAgents.forEach(agent => {
    renderAgent(ctx, agent, agent.pixelX, agent.pixelY);
    
    if (agent.speechText) {
      renderSpeechBubble(ctx, agent, agent.speechText);
    }
  });
  
  requestAnimationFrame(render);
}

// Start render loop
render();
```

---

## Summary

This specification transforms the visualizer from hand-drawn vector art to Smallville-style pixel art:

1. **Tile-based rendering**: 40×25 grid, 32px tiles (16×16 scaled 2×)
2. **Kenney RPG Urban Kit**: Use specific tile indices for ground, buildings, water, foliage
3. **Character sprites**: Kenney character tilesheet, tinted per agent color
4. **Pixel art aesthetic**: Crisp edges, no anti-aliasing, retro 16-bit RPG feel
5. **Z-order rendering**: Ground → paths → buildings → decorations → agents → UI
6. **Animation**: 500ms ease-out movement between tiles, 3-frame walk cycle

The result should look like a retro RPG town map, similar to Stanford's Smallville simulation.
