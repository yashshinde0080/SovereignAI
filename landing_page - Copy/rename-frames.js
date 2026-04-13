// Rename script: "S (1).jpg" → "frame-001.jpg"
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, 'public', 'sovereignaiframes');

for (let i = 1; i <= 240; i++) {
  const oldName = `S (${i}).jpg`;
  const newName = `frame-${String(i).padStart(3, '0')}.jpg`;
  const oldPath = path.join(dir, oldName);
  const newPath = path.join(dir, newName);
  
  try {
    if (fs.existsSync(oldPath)) {
      fs.renameSync(oldPath, newPath);
      console.log(`${oldName} → ${newName}`);
    } else {
      console.log(`SKIP: ${oldName} not found`);
    }
  } catch (e) {
    console.error(`ERROR: ${oldName} - ${e.message}`);
  }
}

console.log('Done! Renamed 240 frames.');
