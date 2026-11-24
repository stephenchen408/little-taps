// Builds the home-screen (PWA) version of Little Taps into docs/, which GitHub Pages serves.
// index.html stays the single source: this wraps it in a full page with the app manifest,
// icons and offline service worker, and copies the voice files.
// Run: node tools/build_site.mjs
import fs from "fs";
import path from "path";
import crypto from "crypto";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const out = path.join(root, "docs");
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, "voice"), { recursive: true });
fs.mkdirSync(path.join(out, "icons"), { recursive: true });

const src = fs.readFileSync(path.join(root, "index.html"), "utf8");
const cut = src.indexOf('<div id="app">');
const headExtra = src.slice(0, cut).replace(/<meta name="claude:[^>]*>\n?/, ""), body = src.slice(cut);
const head = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Little Taps">
<meta name="theme-color" content="#9FE3D8">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<link rel="icon" type="image/png" href="icons/icon-192.png">
<style>:root{padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
${headExtra}
</head>
<body>
`;
const tail = `
<script>if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");</script>
</body>
</html>
`;
fs.writeFileSync(path.join(out, "index.html"), head + body + tail);

const copy = (from, to) => fs.copyFileSync(path.join(root, from), path.join(out, to));
for (const f of fs.readdirSync(path.join(root, "voice"))) copy(path.join("voice", f), path.join("voice", f));
for (const f of fs.readdirSync(path.join(root, "site", "icons"))) copy(path.join("site", "icons", f), path.join("icons", f));
copy(path.join("site", "manifest.webmanifest"), "manifest.webmanifest");

const files = ["./", "manifest.webmanifest",
  ...fs.readdirSync(path.join(out, "icons")).map(f => "icons/" + f),
  ...fs.readdirSync(path.join(out, "voice")).map(f => "voice/" + f)];
const version = crypto.createHash("sha1").update(head + body + files.map(f => {
  const p = path.join(out, f === "./" ? "index.html" : f); return fs.statSync(p).size + f;
}).join()).digest("hex").slice(0, 10);
const sw = fs.readFileSync(path.join(root, "site", "sw.js"), "utf8").replace(/__VERSION__/g, version).replace(/__FILES__/g, JSON.stringify(files));
fs.writeFileSync(path.join(out, "sw.js"), sw);
fs.writeFileSync(path.join(out, ".nojekyll"), "");
console.log(`built docs/ (version ${version}, ${files.length} cached files)`);
