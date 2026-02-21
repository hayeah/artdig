import { useState, useEffect } from 'react'
import { GuideRenderer } from '../components/GuideRenderer'
import { BridgeProvider } from '../hooks/useBridge'
import '../styles/guide.css'
import '../styles/artwork.css'

export function App() {
  const [guides, setGuides] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [events, setEvents] = useState<Array<{ time: string; payload: any }>>([])

  useEffect(() => {
    fetch('/api/notes')
      .then(r => r.json())
      .then((names: string[]) => {
        setGuides(names)
        if (names.length > 0) setSelected(names[0])
      })
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    fetch(`/api/notes/${encodeURIComponent(selected)}`)
      .then(r => r.text())
      .then(content => {
        setMarkdown(content)
        setLoading(false)
      })
  }, [selected])

  useEffect(() => {
    function handleTap(e: Event) {
      const detail = (e as CustomEvent).detail
      setEvents(prev => [
        { time: new Date().toLocaleTimeString(), payload: detail },
        ...prev.slice(0, 19),
      ])
    }
    window.addEventListener('artworkTapped', handleTap)
    return () => window.removeEventListener('artworkTapped', handleTap)
  }, [])

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Guide list sidebar */}
      <div style={{
        width: 220,
        borderRight: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(0,0,0,0.2)',
        padding: '16px 0',
        overflowY: 'auto',
        flexShrink: 0,
      }}>
        <h3 style={{
          color: '#f0ebe4',
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          margin: '0 16px 12px',
          fontFamily: '-apple-system, sans-serif',
        }}>
          Guides
        </h3>
        {guides.length === 0 && (
          <p style={{
            color: '#666',
            fontSize: 13,
            padding: '0 16px',
            fontFamily: '-apple-system, sans-serif',
          }}>
            No guides found
          </p>
        )}
        {guides.map(name => (
          <button
            key={name}
            onClick={() => setSelected(name)}
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              padding: '8px 16px',
              border: 'none',
              background: selected === name ? 'rgba(126,184,224,0.15)' : 'transparent',
              color: selected === name ? '#7eb8e0' : '#c0b8a8',
              fontSize: 13,
              fontFamily: '-apple-system, sans-serif',
              cursor: 'pointer',
              lineHeight: 1.4,
            }}
          >
            {name}
          </button>
        ))}
      </div>

      {/* Guide content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && (
          <div style={{ color: '#666', padding: 40, fontFamily: '-apple-system, sans-serif' }}>
            Loading...
          </div>
        )}
        {!loading && markdown && (
          <BridgeProvider>
            <GuideRenderer markdown={markdown} />
          </BridgeProvider>
        )}
        {!loading && !markdown && (
          <div style={{ color: '#666', padding: 40, fontFamily: '-apple-system, sans-serif' }}>
            Select a guide from the sidebar.
          </div>
        )}
      </div>

      {/* Event log sidebar */}
      <div style={{
        width: 300,
        borderLeft: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(0,0,0,0.3)',
        padding: 16,
        overflowY: 'auto',
        flexShrink: 0,
        fontFamily: 'SF Mono, Menlo, monospace',
        fontSize: 12,
        color: '#a0a0a0',
      }}>
        <h3 style={{
          color: '#f0ebe4',
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          margin: '0 0 12px',
          fontFamily: '-apple-system, sans-serif',
        }}>
          Event Log
        </h3>
        {events.length === 0 && (
          <p style={{ opacity: 0.5, fontSize: 12 }}>Click an artwork card to see events here.</p>
        )}
        {events.map((ev, i) => (
          <div key={i} style={{
            marginBottom: 12,
            padding: 8,
            background: 'rgba(255,255,255,0.04)',
            borderRadius: 6,
          }}>
            <div style={{ color: '#7eb8e0', marginBottom: 4 }}>{ev.time}</div>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(ev.payload, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}
