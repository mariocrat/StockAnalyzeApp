import assert from 'node:assert/strict';

// DOM evidence from actual React HTML, never a review/Markdown parser or renderer.
function decodeEntities(text) {
  const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
  return text.replace(/&(#x[0-9a-f]+|#[0-9]+|amp|lt|gt|quot|apos);/gi, (_, entity) => {
    if (entity.startsWith('#x')) return String.fromCodePoint(parseInt(entity.slice(2), 16));
    if (entity.startsWith('#')) return String.fromCodePoint(parseInt(entity.slice(1), 10));
    return named[entity];
  });
}

export function readRenderedDom(html) {
  const root = { tag: 'root', children: [] };
  const stack = [root];
  const tokens = html.match(/<!--[\s\S]*?-->|<[^>]+>|[^<]+/g) ?? [];
  assert.equal(tokens.join(''), html);
  const voidTags = new Set(['area', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);
  for (const token of tokens) {
    if (token.startsWith('<!--')) continue;
    if (token.startsWith('</')) {
      assert.equal(token, `</${stack.at(-1).tag}>`);
      stack.pop();
      assert.ok(stack.length);
    } else if (token.startsWith('<')) {
      const match = token.match(/^<([a-z][a-z0-9-]*)(?:\s[^<>]*)?\/?\s*>$/);
      assert.ok(match, `unexpected rendered element: ${token}`);
      const node = { tag: match[1], children: [], block: token.match(/data-review-block="([a-z_]+)"/)?.[1] };
      stack.at(-1).children.push(node);
      if (!voidTags.has(node.tag)) stack.push(node);
    } else stack.at(-1).children.push({ tag: 'text', value: decodeEntities(token) });
  }
  assert.equal(stack.length, 1);
  return root;
}

export function textContent(node) {
  return node.tag === 'text' ? node.value : node.children.map(textContent).join('');
}

export function nodeEvidence(dom) {
  const strongRanges = [];
  const blocks = [];
  let text = '';
  function walk(node) {
    if (node.tag === 'text') {
      text += node.value;
      return;
    }
    if (node.block) blocks.push(node.block);
    const start = Array.from(text).length;
    for (const child of node.children) walk(child);
    if (node.tag === 'strong') strongRanges.push({ start, end: Array.from(text).length, text: textContent(node) });
  }
  walk(dom);
  return { text, strong: strongRanges.map(range => range.text), strongRanges, blocks };
}

export function renderEvidence(html) {
  const dom = readRenderedDom(html);
  return { html, dom, ...nodeEvidence(dom) };
}

// V2 has semantic shell labels around the original canonical parts. Observe
// actual DOM block parents (including their exact separators), not source text.
export function canonicalBodyEvidence(html) {
  const rendered = renderEvidence(html);
  if (!html.includes('data-review-version="review-display.v2"')) return rendered;
  const parts = [];
  function walk(node) {
    if (node.children?.some(child => child.block)) parts.push(nodeEvidence(node));
    else node.children?.forEach(walk);
  }
  walk(rendered.dom);
  const strongRanges = [];
  let offset = 0;
  for (const part of parts) {
    strongRanges.push(...part.strongRanges.map(range => ({ ...range, start: offset + range.start, end: offset + range.end })));
    offset += Array.from(part.text).length;
  }
  return { ...rendered, text: parts.map(part => part.text).join(''),
    blocks: parts.flatMap(part => part.blocks), strongRanges, strong: strongRanges.map(range => range.text) };
}
