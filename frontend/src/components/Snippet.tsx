import type { SnippetPart } from '../api'

export function Snippet({ parts }: { parts: SnippetPart[] }) {
  return (
    <p className="snippet">
      {parts.map((part, index) => (part.match ? <mark key={index}>{part.text}</mark> : <span key={index}>{part.text}</span>))}
    </p>
  )
}
