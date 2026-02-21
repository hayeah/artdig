import { createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { GuideRenderer } from './components/GuideRenderer'
import { BridgeProvider } from './hooks/useBridge'
import guideStyles from './styles/guide.css?inline'
import artworkStyles from './styles/artwork.css?inline'

let root: Root | null = null
let stylesInjected = false

function injectStyles() {
  if (stylesInjected) return
  stylesInjected = true
  const style = document.createElement('style')
  style.textContent = guideStyles + '\n' + artworkStyles
  document.head.appendChild(style)
}

export function renderMarkdown(markdown: string, container?: HTMLElement) {
  const target = container || document.getElementById('content')
  if (!target) return

  injectStyles()

  if (!root) {
    root = createRoot(target)
  }

  root.render(
    createElement(BridgeProvider, null,
      createElement(GuideRenderer, { markdown })
    )
  )
}
