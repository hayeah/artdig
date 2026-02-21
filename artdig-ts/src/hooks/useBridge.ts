import { createContext, useContext, createElement, type ReactNode } from 'react'
import { postArtworkTap } from '../bridge'
import type { ArtworkTapPayload } from '../types'

interface BridgeContextValue {
  postArtworkTap: (payload: ArtworkTapPayload) => void
}

const BridgeContext = createContext<BridgeContextValue>({
  postArtworkTap,
})

export function BridgeProvider({ children }: { children: ReactNode }) {
  return createElement(BridgeContext.Provider, { value: { postArtworkTap } }, children)
}

export function useBridge() {
  return useContext(BridgeContext)
}
