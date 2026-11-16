// Rebuild an exported Site checkout without fetching or silently updating its pinned source.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
const data = JSON.parse(readFileSync('data.json', 'utf8'));
const manifest = JSON.parse(readFileSync('source-manifest.json', 'utf8'));
if (!data.version.startsWith('2.') || manifest.version !== data.version || manifest.commit !== data.commit) throw Error('Source provenance mismatch; re-export from the GitHub checkout');
for (const [key, path] of Object.entries(data.paths)) {
  const raw = readFileSync('upstream/' + path);
  if (createHash('sha256').update(raw).digest('hex') !== manifest.sha256[path]) throw Error('Pinned source changed: ' + path);
  data.documents[key] = raw.toString('utf8');
}
const hosting = JSON.parse(readFileSync('.openai/hosting.json', 'utf8'));
if (hosting.project_id !== 'appgprj_6ac4a1336bac81918aad9da3e140ebf2' || !hosting.capabilities?.includes('mcp')) throw Error('Wrong Site identity/capability');
const html = readFileSync('index.html', 'utf8').replaceAll('__SOURCE_SHA__', data.commit).replaceAll('__SOURCE_SHORT__', data.commit.slice(0, 7)).replaceAll('__VERSION__', data.version);
const source = readFileSync('worker.mjs', 'utf8').replace('// BUILD_DATA', 'const DATA = ' + JSON.stringify(data) + ';\nconst HTML = ' + JSON.stringify(html) + ';');
mkdirSync('dist/server', { recursive: true }); mkdirSync('dist/.openai', { recursive: true });
writeFileSync('dist/server/index.js', source); writeFileSync('dist/.openai/hosting.json', JSON.stringify(hosting, null, 2) + '\n');
console.log('Built Mathematician Humanizer v2 from ' + data.commit);
