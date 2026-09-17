export function renderMarkdown(text: string) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let currentList: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Flush any pending list items
    if (currentList.length > 0 && !line.trim().startsWith('-') && !line.trim().startsWith('•')) {
      elements.push(
        <ul key={`list-${i}`} className="markdown-list">
          {currentList.map((item, idx) => (
            <li key={idx}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      )
      currentList = []
    }

    if (!line.trim()) {
      elements.push(<br key={`br-${i}`} />)
    } else if (line.trim().startsWith('# ')) {
      elements.push(
        <h1 key={`h1-${i}`} className="markdown-h1">
          {renderInlineMarkdown(line.trim().substring(2))}
        </h1>
      )
    } else if (line.trim().startsWith('## ')) {
      elements.push(
        <h2 key={`h2-${i}`} className="markdown-h2">
          {renderInlineMarkdown(line.trim().substring(3))}
        </h2>
      )
    } else if (line.trim().startsWith('### ')) {
      elements.push(
        <h3 key={`h3-${i}`} className="markdown-h3">
          {renderInlineMarkdown(line.trim().substring(4))}
        </h3>
      )
    } else if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
      currentList.push(
        line
          .trim()
          .replace(/^[-•]\s*/, '')
          .trim()
      )
    } else {
      elements.push(
        <p key={`p-${i}`} className="markdown-p">
          {renderInlineMarkdown(line.trim())}
        </p>
      )
    }
  }

  // Flush remaining list
  if (currentList.length > 0) {
    elements.push(
      <ul key="final-list" className="markdown-list">
        {currentList.map((item, idx) => (
          <li key={idx}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>
    )
  }

  return elements
}

export function renderInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  let lastIndex = 0

  // Bold: **text**
  const boldRegex = /\*\*(.*?)\*\*/g
  let match
  while ((match = boldRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }
    parts.push(
      <strong key={`bold-${match.index}`}>{match[1]}</strong>
    )
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }

  return parts.length > 0 ? parts : text
}
