import { describe, expect, it } from 'vitest'
import type { SourceRef } from './api'
import { gatheringLine } from './gathering'

const ref = (source: string, used = true, id = `${source}-${Math.random()}`): SourceRef => ({
  id,
  title: id,
  source,
  url: `https://example.org/${id}`,
  used,
})

describe('gatheringLine', () => {
  it('searches until the sources arrive', () => {
    expect(gatheringLine(undefined)).toBe('Searching the sources')
  })

  it('counts only the passages the answer is written from, and names their sources', () => {
    expect(gatheringLine([ref('d3fend'), ref('d3fend', false)])).toBe('Reading 1 passage from MITRE D3FEND')
    expect(gatheringLine([ref('d3fend'), ref('attack'), ref('d3fend')])).toBe(
      'Reading 3 passages from MITRE D3FEND and MITRE ATT&CK',
    )
    expect(gatheringLine([ref('atlas'), ref('attack'), ref('cwe')])).toBe(
      'Reading 3 passages from MITRE ATLAS, MITRE ATT&CK and MITRE CWE',
    )
  })

  it('counts the sources beyond the first two when there are more than three', () => {
    expect(gatheringLine(['atlas', 'attack', 'cwe', 'capec', 'vulns'].map((s) => ref(s)))).toBe(
      'Reading 5 passages from MITRE ATLAS, MITRE ATT&CK and 3 more sources',
    )
  })

  it('falls back to the source id for an unknown source, and to writing when nothing was used', () => {
    expect(gatheringLine([ref('new-source')])).toBe('Reading 1 passage from new-source')
    expect(gatheringLine([ref('atlas', false)])).toBe('Writing the answer')
  })
})
