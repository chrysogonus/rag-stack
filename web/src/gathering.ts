import type { SourceRef } from './api'
import { SOURCES } from './sky/layout'

const LABELS = new Map(SOURCES.map((s) => [s.id, s.label]))
/** Sources named before the rest are counted instead. */
const NAMED = 3

/** What the waiting answer is doing: searching, then reading the passages it will be written from. */
export function gatheringLine(sources: SourceRef[] | undefined): string {
  if (!sources) return 'Searching the sources'
  const used = sources.filter((s) => s.used)
  if (!used.length) return 'Writing the answer'
  const names = [...new Set(used.map((s) => LABELS.get(s.source) ?? s.source))]
  const rest = names.length - NAMED
  const listed = rest > 1 ? [...names.slice(0, NAMED - 1), `${rest + 1} more sources`] : names
  const from = listed.length > 1 ? `${listed.slice(0, -1).join(', ')} and ${listed.at(-1)}` : listed[0]
  return `Reading ${used.length} ${used.length === 1 ? 'passage' : 'passages'} from ${from}`
}
