import { useState, useEffect } from 'react'

const cache = new Map<string, string | null>()

export function useMetImage(objectId: string | undefined): { imageUrl: string | null; loading: boolean } {
  const [imageUrl, setImageUrl] = useState<string | null>(() => {
    if (!objectId) return null
    return cache.get(objectId) ?? null
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!objectId) return

    if (cache.has(objectId)) {
      setImageUrl(cache.get(objectId)!)
      return
    }

    let cancelled = false
    setLoading(true)

    fetch(`https://collectionapi.metmuseum.org/public/collection/v1/objects/${objectId}`)
      .then(res => res.json())
      .then(data => {
        if (cancelled) return
        const url: string | null = data.primaryImageSmall || null
        cache.set(objectId, url)
        setImageUrl(url)
      })
      .catch(() => {
        if (cancelled) return
        cache.set(objectId, null)
        setImageUrl(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [objectId])

  return { imageUrl, loading }
}
