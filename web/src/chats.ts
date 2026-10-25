/** A saved conversation: its server thread ID and the question it started with. */
export interface Chat {
  id: string
  title: string
}

/** Moves the chat to the top (most recent first), keeping the title it was first saved with. */
export function rememberChat(chats: Chat[], id: string, title: string): Chat[] {
  const existing = chats.find((c) => c.id === id)
  return [existing ?? { id, title }, ...chats.filter((c) => c.id !== id)]
}
