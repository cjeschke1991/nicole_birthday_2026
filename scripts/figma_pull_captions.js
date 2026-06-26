// Run via Figma MCP use_figma to export caption box positions (pt coords).
// Save return value to scripts/figma-caption-export-raw.json, then:
//   python scripts/pull_figma_captions.py
//   python scripts/figma_to_captions.py --version v2

const capPage = figma.root.children.find((p) => p.name === 'Caption Layouts');
if (!capPage) {
  return { error: 'Caption Layouts page not found' };
}
await figma.setCurrentPageAsync(capPage);

const pages = {};
for (const frame of capPage.children) {
  if (frame.type !== 'FRAME') continue;
  if (!/^\d{4}-\d{2}$/.test(frame.name)) continue;

  const caps = {};
  for (const child of frame.children) {
    if (!child.name.startsWith('caption-')) continue;
    caps[child.name] = { x: child.x, y: child.y };
  }
  if (Object.keys(caps).length) {
    pages[frame.name] = caps;
  }
}

return { pages, count: Object.keys(pages).length };
