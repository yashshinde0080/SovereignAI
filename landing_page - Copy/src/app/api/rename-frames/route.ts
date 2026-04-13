import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  const dir = path.join(process.cwd(), 'public', 'frames');
  const results: string[] = [];
  let renamed = 0;
  let errors = 0;

  // List all files to debug
  let allFiles: string[] = [];
  try {
    allFiles = fs.readdirSync(dir).slice(0, 5);
  } catch (e: any) {
    return NextResponse.json({ error: `Cannot read dir: ${e.message}`, dir });
  }

  for (let i = 1; i <= 240; i++) {
    const oldName = `S (${i}).jpg`;
    const newName = `frame-${String(i).padStart(3, '0')}.jpg`;
    const oldPath = path.join(dir, oldName);
    const newPath = path.join(dir, newName);

    try {
      fs.renameSync(oldPath, newPath);
      renamed++;
    } catch (e: any) {
      errors++;
      if (i <= 3) results.push(`${oldName}: ${e.message}`);
    }
  }

  return NextResponse.json({ renamed, errors, total: 240, dir, sampleFiles: allFiles, errorSamples: results });
}
