// ── Download Kenney CC0 sprite packs and extract to public/sprites/ ──
// Run: node scripts/download-sprites.js

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const zlib = require('zlib');

const SPRITES_DIR = path.resolve(__dirname, '..', 'visualizer', 'public', 'sprites');
const TILES_DIR = path.join(SPRITES_DIR, 'tiles');
const CHARACTERS_DIR = path.join(SPRITES_DIR, 'characters');
const NATURE_DIR = path.join(SPRITES_DIR, 'nature');

// Alternative URLs for Kenney packs (from the actual Kenney CDN)
const URLS = {
  rpgUrban: [
    'https://kenney.nl/media/pages/assets/rpg-urban-pack/0a097d1dc7-1677578575/kenney_rpg-urban-pack.zip',
    'https://kenney.nl/assets/rpg-urban-pack',
  ],
  foliage: [
    'https://kenney.nl/media/pages/assets/foliage-pack/06a6c43298-1677693473/kenney_foliage-pack.zip',
    'https://kenney.nl/assets/foliage-pack',
  ],
};

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const proto = url.startsWith('https') ? https : http;
    proto.get(url, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        // Follow redirect
        file.close();
        fs.unlinkSync(dest);
        return download(response.headers.location, dest).then(resolve).catch(reject);
      }
      if (response.statusCode !== 200) {
        file.close();
        fs.unlinkSync(dest);
        return reject(new Error(`HTTP ${response.statusCode} for ${url}`));
      }
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      file.close();
      if (fs.existsSync(dest)) fs.unlinkSync(dest);
      reject(err);
    });
  });
}

function extractZip(zipPath, destDir) {
  // Use PowerShell's Expand-Archive as a cross-platform approach
  const cmd = `powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${destDir}' -Force"`;
  execSync(cmd, { stdio: 'pipe' });
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function findAndCopyPngs(srcDir, destDir, filterFn = () => true) {
  ensureDir(destDir);
  const walk = (dir) => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.name.endsWith('.png') && filterFn(entry.name, fullPath)) {
        const dest = path.join(destDir, entry.name);
        if (!fs.existsSync(dest)) {
          fs.copyFileSync(fullPath, dest);
          console.log(`  Copied: ${entry.name}`);
        }
      }
    }
  };
  walk(srcDir);
}

// Fallback: generate minimal colored-tile sprites if download fails
function generateFallbackTiles() {
  console.log('\nGenerating fallback colored-tile sprites...');
  const tileSize = 16;

  // Tile colors (simple colored squares with a pixel-art border)
  const TILE_TEMPLATES = {
    grass: { r: 100, g: 180, b: 80 },
    path: { r: 180, g: 150, b: 90 },
    water: { r: 60, g: 140, b: 210 },
    tree: { r: 50, g: 120, b: 40 },
    bush: { r: 80, g: 160, b: 60 },
    wall: { r: 140, g: 120, b: 90 },
    floor: { r: 180, g: 160, b: 130 },
    roof: { r: 120, g: 70, b: 40 },
    door: { r: 80, g: 50, b: 20 },
    window: { r: 160, g: 200, b: 230 },
    road: { r: 130, g: 120, b: 100 },
  };

  const canvas = require('canvas') || null;
  if (!canvas) {
    console.log('  canvas package not available, creating 16x16 minimal PNG files...');
    // Create minimal valid PNG files (1-pixel PNGs as placeholders)
    // Minimal 16x16 green PNG
    for (const [name, { r, g, b }] of Object.entries(TILE_TEMPLATES)) {
      // Create a simple 16x16 raw PGM-like colored PNG
      const buf = createMinimalPNG(16, 16, r, g, b);
      fs.writeFileSync(path.join(TILES_DIR, `${name}.png`), buf);
      console.log(`  Created fallback: ${name}.png`);
    }
    // Character placeholder
    fs.writeFileSync(path.join(CHARACTERS_DIR, 'character.png'), createMinimalPNG(16, 24, 200, 200, 200));
    console.log('  Created fallback: character.png');
    return;
  }
}

function createMinimalPNG(width, height, r, g, b) {
  // Create a minimal valid PNG file
  // PNG signature
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR chunk
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8;  // bit depth
  ihdrData[9] = 2;  // color type (RGB)
  ihdrData[10] = 0; // compression
  ihdrData[11] = 0; // filter
  ihdrData[12] = 0; // interlace

  const ihdr = createChunk('IHDR', ihdrData);

  // IDAT chunk - raw pixel data (filter byte + RGB per row)
  const rawData = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    rawData[y * (1 + width * 3)] = 0; // filter byte (none)
    for (let x = 0; x < width; x++) {
      const offset = y * (1 + width * 3) + 1 + x * 3;
      // Border pixels are darker
      const isBorder = x === 0 || x === width - 1 || y === 0 || y === height - 1;
      rawData[offset] = isBorder ? Math.max(0, r - 40) : r;
      rawData[offset + 1] = isBorder ? Math.max(0, g - 40) : g;
      rawData[offset + 2] = isBorder ? Math.max(0, b - 40) : b;
    }
  }
  const compressed = zlib.deflateSync(rawData);
  const idat = createChunk('IDAT', compressed);

  // IEND chunk
  const iend = createChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([sig, ihdr, idat, iend]);
}

function createChunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeB = Buffer.from(type, 'ascii');
  const crcData = Buffer.concat([typeB, data]);
  const crc = crc32(crcData);
  const crcB = Buffer.alloc(4);
  crcB.writeUInt32BE(crc, 0);
  return Buffer.concat([len, typeB, data, crcB]);
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xEDB88320 : 0);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

async function main() {
  console.log('=== Kenney Sprite Downloader ===\n');

  ensureDir(SPRITES_DIR);
  ensureDir(TILES_DIR);
  ensureDir(CHARACTERS_DIR);
  ensureDir(NATURE_DIR);

  // Try downloading the RPG Urban Pack
  console.log('1. Downloading Kenney RPG Urban Pack...');
  let rpgDownloaded = false;
  for (const url of URLS.rpgUrban) {
    if (rpgDownloaded) break;
    const zipPath = path.join(SPRITES_DIR, 'kenney_rpg-urban-pack.zip');
    try {
      console.log(`   Trying: ${url}`);
      await download(url, zipPath);
      console.log('   Downloaded! Extracting...');
      const extractDir = path.join(SPRITES_DIR, '_rpg_extract');
      ensureDir(extractDir);
      extractZip(zipPath, extractDir);

      // Copy PNGs to appropriate directories
      console.log('   Copying tiles...');
      findAndCopyPngs(extractDir, TILES_DIR, (name, fullPath) => {
        // Exclude character sprites (those go to characters/)
        return !name.startsWith('character') && !name.includes('person');
      });
      console.log('   Copying characters...');
      findAndCopyPngs(extractDir, CHARACTERS_DIR, (name, fullPath) => {
        return name.startsWith('character') || name.includes('person');
      });

      // Cleanup
      fs.rmSync(extractDir, { recursive: true, force: true });
      fs.rmSync(zipPath, { force: true });
      rpgDownloaded = true;
      console.log('   RPG Urban Pack extracted successfully!');
    } catch (err) {
      console.log(`   Failed: ${err.message}`);
    }
  }

  if (!rpgDownloaded) {
    console.log('   Could not download RPG Urban Pack from any URL.');
  }

  // Try downloading the Foliage Pack
  console.log('\n2. Downloading Kenney Foliage Pack...');
  let foliageDownloaded = false;
  for (const url of URLS.foliage) {
    if (foliageDownloaded) break;
    const zipPath = path.join(SPRITES_DIR, 'kenney_foliage-pack.zip');
    try {
      console.log(`   Trying: ${url}`);
      await download(url, zipPath);
      console.log('   Downloaded! Extracting...');
      const extractDir = path.join(SPRITES_DIR, '_foliage_extract');
      ensureDir(extractDir);
      extractZip(zipPath, extractDir);

      // Copy PNGs to nature directory
      console.log('   Copying nature sprites...');
      findAndCopyPngs(extractDir, NATURE_DIR);

      // Also copy to tiles for tree/bush tiles
      console.log('   Copying to tiles...');
      findAndCopyPngs(extractDir, TILES_DIR);

      // Cleanup
      fs.rmSync(extractDir, { recursive: true, force: true });
      fs.rmSync(zipPath, { force: true });
      foliageDownloaded = true;
      console.log('   Foliage Pack extracted successfully!');
    } catch (err) {
      console.log(`   Failed: ${err.message}`);
    }
  }

  if (!foliageDownloaded) {
    console.log('   Could not download Foliage Pack from any URL.');
  }

  // If nothing was downloaded, generate fallback tiles
  const tilesCount = fs.readdirSync(TILES_DIR).filter(f => f.endsWith('.png')).length;
  const charsCount = fs.readdirSync(CHARACTERS_DIR).filter(f => f.endsWith('.png')).length;
  const natureCount = fs.readdirSync(NATURE_DIR).filter(f => f.endsWith('.png')).length;

  console.log(`\n=== Summary ===`);
  console.log(`Tiles: ${tilesCount} PNGs`);
  console.log(`Characters: ${charsCount} PNGs`);
  console.log(`Nature: ${natureCount} PNGs`);

  if (tilesCount === 0 && charsCount === 0 && natureCount === 0) {
    console.log('\nNo sprites downloaded. Generating fallback colored tiles...');
    generateFallbackTiles();
  } else {
    console.log('\nSprites downloaded and extracted successfully!');
  }

  // List all files
  console.log('\n=== Files in tiles/ ===');
  if (fs.existsSync(TILES_DIR)) {
    for (const f of fs.readdirSync(TILES_DIR).sort()) {
      console.log(`  ${f}`);
    }
  }
  console.log('\n=== Files in characters/ ===');
  if (fs.existsSync(CHARACTERS_DIR)) {
    for (const f of fs.readdirSync(CHARACTERS_DIR).sort()) {
      console.log(`  ${f}`);
    }
  }
  console.log('\n=== Files in nature/ ===');
  if (fs.existsSync(NATURE_DIR)) {
    for (const f of fs.readdirSync(NATURE_DIR).sort()) {
      console.log(`  ${f}`);
    }
  }
}

main().catch(console.error);
