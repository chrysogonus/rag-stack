import { describe, expect, it } from 'vitest'
import { rememberChat } from './chats'

describe('rememberChat', () => {
  const chats = [
    { id: 'a', title: 'First' },
    { id: 'b', title: 'Second' },
    { id: 'c', title: 'Third' },
  ]

  it('puts a new chat on top', () => {
    expect(rememberChat(chats, 'd', 'Fourth').map((c) => c.id)).toEqual(['d', 'a', 'b', 'c'])
  })

  it('moves a known chat to the top and keeps its original title', () => {
    expect(rememberChat(chats, 'b', 'A follow-up')).toEqual([
      { id: 'b', title: 'Second' },
      { id: 'a', title: 'First' },
      { id: 'c', title: 'Third' },
    ])
  })
})
