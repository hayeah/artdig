import type { ArtworkTapPayload } from './types'

declare global {
  interface Window {
    webkit?: {
      messageHandlers?: {
        artworkTapped?: {
          postMessage(payload: ArtworkTapPayload): void
        }
      }
    }
  }
}

export function postArtworkTap(payload: ArtworkTapPayload): void {
  if (window.webkit?.messageHandlers?.artworkTapped) {
    window.webkit.messageHandlers.artworkTapped.postMessage(payload)
  } else {
    window.dispatchEvent(new CustomEvent('artworkTapped', { detail: payload }))
    console.log('[bridge] artworkTapped', payload)
  }
}
