import { useState } from 'react'

interface ArtworkImageProps {
  src: string
  alt: string
}

/** Transforms NGA IIIF URLs from /full/max/ to /full/!600,600/ for thumbnails */
function thumbnailUrl(url: string): string {
  if (url.includes('api.nga.gov/iiif/')) {
    return url.replace('/full/max/', '/full/!600,600/')
  }
  return url
}

export function ArtworkImage({ src, alt }: ArtworkImageProps) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const url = thumbnailUrl(src)

  if (error) {
    return (
      <div className="artwork-image artwork-image--placeholder">
        <span className="artwork-image__icon">🖼</span>
      </div>
    )
  }

  return (
    <div className={`artwork-image ${loaded ? 'artwork-image--loaded' : ''}`}>
      {!loaded && <div className="artwork-image__skeleton" />}
      <img
        src={url}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
      />
    </div>
  )
}
