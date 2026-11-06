import type { Code } from './api'

export interface CodeNode {
  code: Code
  depth: number
  path: string
}

/** Flatten codes into display order, with each child following its parent. */
export function flattenCodeTree(codes: Code[]): CodeNode[] {
  const known = new Set(codes.map((code) => code.id))
  const children = new Map<string | null, Code[]>()
  for (const code of codes) {
    const parent = code.parent_id && known.has(code.parent_id) ? code.parent_id : null
    children.set(parent, [...(children.get(parent) ?? []), code])
  }
  const nodes: CodeNode[] = []
  const visit = (parent: string | null, depth: number, prefix: string) => {
    for (const code of children.get(parent) ?? []) {
      const path = prefix ? `${prefix} > ${code.name}` : code.name
      nodes.push({ code, depth, path })
      visit(code.id, depth + 1, path)
    }
  }
  visit(null, 0, '')
  return nodes
}

/** Codes this code can move under: everything except itself and its descendants. */
export function allowedParents(codes: Code[], codeId: string): Code[] {
  const excluded = new Set([codeId])
  let grew = true
  while (grew) {
    grew = false
    for (const code of codes) {
      if (code.parent_id && excluded.has(code.parent_id) && !excluded.has(code.id)) {
        excluded.add(code.id)
        grew = true
      }
    }
  }
  return codes.filter((code) => !excluded.has(code.id))
}
