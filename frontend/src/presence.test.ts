import { afterEach, expect, test, vi } from 'vitest'
import { leaveArticle, sendHeartbeat } from './api'

afterEach(() => vi.unstubAllGlobals())

test('a check-in is not sent until a leave on its way has finished', async () => {
  const sent: string[] = []
  let finishLeave = () => {}
  vi.stubGlobal('fetch', (_path: string, init: RequestInit) => {
    sent.push(init.method!)
    if (init.method === 'DELETE') return new Promise((resolve) => { finishLeave = () => resolve(new Response(null, { status: 204 })) })
    return Promise.resolve(new Response(JSON.stringify({ others: [] })))
  })

  leaveArticle('project', 'article')
  const checkIn = sendHeartbeat('project', 'article')
  await new Promise((resolve) => setTimeout(resolve))
  expect(sent).toEqual(['DELETE'])

  finishLeave()
  await checkIn
  expect(sent).toEqual(['DELETE', 'POST'])
})
