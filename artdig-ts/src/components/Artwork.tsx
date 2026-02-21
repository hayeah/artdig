import { useBridge } from '../hooks/useBridge'
import { useMetImage } from '../hooks/useMetImage'
import { ArtworkImage } from './ArtworkImage'

interface ArtworkProps {
  title: string
  date?: string
  artist?: string
  source: string
  sourceId: string
  sourceUrl: string
  imageUrl?: string
  node?: unknown
  children?: React.ReactNode
}

export function Artwork({ title, date, artist, source, sourceId, sourceUrl, imageUrl }: ArtworkProps) {
  const bridge = useBridge()
  const metObjectId = source === 'met' ? sourceId : undefined
  const { imageUrl: metImageUrl, loading: metLoading } = useMetImage(metObjectId)

  const resolvedImageUrl = imageUrl || metImageUrl

  function handleClick() {
    bridge.postArtworkTap({
      source,
      sourceID: sourceId,
      title,
      imageURL: resolvedImageUrl || undefined,
    })
  }

  return (
    <div className="artwork-card" onClick={handleClick} role="button" tabIndex={0}>
      <div className="artwork-card__image">
        {resolvedImageUrl ? (
          <ArtworkImage src={resolvedImageUrl} alt={title} />
        ) : metLoading ? (
          <div className="artwork-image artwork-image--placeholder">
            <div className="artwork-image__skeleton" />
          </div>
        ) : (
          <div className="artwork-image artwork-image--placeholder">
            <span className="artwork-image__icon">🖼</span>
          </div>
        )}
      </div>
      <div className="artwork-card__info">
        <span className={`artwork-card__badge artwork-card__badge--${source}`}>
          {source.toUpperCase()}
        </span>
        <h4 className="artwork-card__title">{title}</h4>
        {date && <span className="artwork-card__date">{date}</span>}
        {artist && <span className="artwork-card__artist">{artist}</span>}
      </div>
    </div>
  )
}
