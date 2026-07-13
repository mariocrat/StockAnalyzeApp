export function getTooltipPosition({
  pointX,
  pointY,
  containerWidth,
  containerHeight,
  tooltipWidth,
  tooltipHeight,
  gap = 12,
  padding = 8,
}) {
  const maxX = Math.max(padding, containerWidth - tooltipWidth - padding);
  const maxY = Math.max(padding, containerHeight - tooltipHeight - padding);
  const preferredX = pointX + gap + tooltipWidth <= containerWidth - padding
    ? pointX + gap
    : pointX - gap - tooltipWidth;
  const preferredY = pointY + gap + tooltipHeight <= containerHeight - padding
    ? pointY + gap
    : pointY - gap - tooltipHeight;

  return {
    x: Math.min(Math.max(preferredX, padding), maxX),
    y: Math.min(Math.max(preferredY, padding), maxY),
  };
}

export function getPaneHeights(totalHeight, indicatorCount) {
  const safeHeight = Math.max(160, Math.floor(totalHeight || 0));
  const count = Math.max(0, Math.floor(indicatorCount || 0));
  const volume = Math.max(count ? 30 : 36, Math.floor(safeHeight * (count ? 0.14 : 0.23)));
  if (!count) return [safeHeight - volume, volume];

  const preferredIndicator = Math.max(32, Math.floor(safeHeight * 0.42 / count));
  const maxIndicator = Math.floor((safeHeight - volume - 80) / count);
  const indicator = Math.max(20, Math.min(preferredIndicator, maxIndicator));
  const main = safeHeight - volume - indicator * count;
  return [main, volume, ...Array(count).fill(indicator)];
}
