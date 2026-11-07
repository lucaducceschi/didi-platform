import type { ActivityEntry } from './api'

const VERBS: Record<string, string> = {
  'project.created': 'created the project',
  'project.updated': 'updated the project',
  'code.created': 'added the code',
  'code.updated': 'changed the code',
  'code.deleted': 'deleted the code',
  'code.merged': 'merged',
  'member.added': 'added the member',
  'member.removed': 'removed the member',
  'member.role_changed': 'changed the role of',
  'articles.added': 'added',
  'articles.removed': 'removed',
}

export function describeActivity(entry: ActivityEntry): string {
  const who = entry.user?.display_name ?? 'The system'
  if (entry.action === 'annotations.reconciled') {
    const { reanchored = 0, stale = 0, restored = 0 } = entry.details as Record<string, number>
    return `${who} checked segments after a corpus update: ${reanchored} moved, ${restored} restored, ${stale} need review.`
  }
  const verb = VERBS[entry.action] ?? entry.action
  return `${who} ${verb}${entry.target ? ` ${entry.target}` : ''}.`
}
