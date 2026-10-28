import type { Element, Root, RootContent } from 'hast'

/** Links keep their text whole (a citation is recognised by it); code keeps its exact spacing. */
const WHOLE = new Set(['a', 'code', 'pre'])

/**
 * A rehype plugin for an answer being written: each word gets its own `span.w`, so a word that has just
 * arrived can condense into place while the words before it, already in the page, stay as they are.
 */
export function rehypeWords() {
  return (tree: Root) => wrap(tree)
}

function wrap(node: Root | Element) {
  const children: RootContent[] = node.children
  node.children = children.flatMap((child): RootContent[] => {
    if (child.type === 'element' && !WHOLE.has(child.tagName)) wrap(child)
    if (child.type !== 'text') return [child]
    return child.value
      .split(/(\s+)/)
      .filter(Boolean)
      .map(
        (part): RootContent =>
          /^\s+$/.test(part)
            ? { type: 'text', value: part }
            : { type: 'element', tagName: 'span', properties: { className: ['w'] }, children: [{ type: 'text', value: part }] },
      )
  }) as Element['children']
}
