// Pull photo, clipart, and caption positions from scatter-a … scatter-d frames.
// Run via use_figma; save result to scripts/figma-scatter-export-raw.json, then:
//   python scripts/pull_figma_scatter.py
//   python scripts/figma_to_scatter.py

const scatterPage = figma.root.children.find((p) => p.name === 'Scatter Recipes');
if (!scatterPage) {
  return { error: 'Scatter Recipes page not found' };
}
await figma.setCurrentPageAsync(scatterPage);

const recipes = {};
for (const frame of scatterPage.children) {
  if (frame.type !== 'FRAME') continue;
  if (!/^scatter-[a-d]$/.test(frame.name)) continue;

  const slots = [];
  for (let i = 1; i <= 3; i++) {
    const photo = frame.findOne((n) => n.name === `photo-${i}`);
    if (!photo) continue;
    const clip = frame.findOne((n) => n.name === `clipart-${i}`);
    const cap = frame.findOne((n) => n.name === `caption-${i}`);
    slots.push({
      photo: { x: photo.x, y: photo.y, w: photo.width, h: photo.height, rot: photo.rotation },
      clip: clip ? { x: clip.x, y: clip.y } : null,
      caption: cap ? { x: cap.x, y: cap.y } : null,
    });
  }
  if (slots.length) {
    recipes[frame.name] = slots;
  }
}

return { recipes, count: Object.keys(recipes).length };
