// Reads the game data block from index.html and writes every voice line to tools/lines.json.
// Run: node tools/extract_lines.mjs
import fs from "fs";
import vm from "vm";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const m = html.match(/<script id="lt-data">([\s\S]*?)<\/script>/);
if (!m) throw new Error('No <script id="lt-data"> block in index.html');
const ctx = { window: {} };
vm.createContext(ctx);
vm.runInContext(m[1], ctx);
const lines = ctx.window.LT.voiceLines();
fs.writeFileSync(new URL("./lines.json", import.meta.url), JSON.stringify(lines, null, 1));
console.log(Object.keys(lines).length, "lines written to tools/lines.json");
