import test from 'node:test';
import assert from 'node:assert/strict';
import { getPaneHeights, getPaneStretchFactors, getTooltipPosition } from '../src/utils/chartLayout.js';

test('tooltip flips inside every chart edge', () => {
  const common = {
    containerWidth: 320,
    containerHeight: 240,
    tooltipWidth: 180,
    tooltipHeight: 90,
  };
  const points = [
    [2, 2],
    [318, 2],
    [2, 238],
    [318, 238],
  ];

  for (const [pointX, pointY] of points) {
    const { x, y } = getTooltipPosition({ ...common, pointX, pointY });
    assert.ok(x >= 8 && x + common.tooltipWidth <= common.containerWidth - 8);
    assert.ok(y >= 8 && y + common.tooltipHeight <= common.containerHeight - 8);
  }
});

test('pane layout only allocates selected indicator panes', () => {
  assert.equal(getPaneHeights(500, 0).length, 2);
  assert.equal(getPaneHeights(500, 1).length, 3);
  assert.equal(getPaneHeights(500, 3).length, 5);
  assert.ok(getPaneHeights(320, 3).every(height => height >= 42));
  assert.equal(getPaneHeights(180, 3).reduce((sum, height) => sum + height, 0), 180);
});

test('pane stretch factors keep indicators equal and the price pane dominant', () => {
  for (let count = 0; count <= 3; count += 1) {
    const factors = getPaneStretchFactors(count);
    assert.equal(factors.length, count + 2);
    assert.equal(factors.reduce((sum, value) => sum + value, 0), 100);
    assert.ok(factors[0] > factors[1]);
    if (count === 2) assert.equal(factors[2], factors[3]);
  }
});
