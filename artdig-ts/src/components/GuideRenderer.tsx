import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkArtworks, { artworkHandlers } from '../remark-artworks'
import { Carousel } from './Carousel'
import { Artwork } from './Artwork'

interface GuideRendererProps {
  markdown: string
}

const components: Record<string, React.ComponentType<any>> = {
  carousel: Carousel,
  artwork: Artwork,
}

export function GuideRenderer({ markdown }: GuideRendererProps) {
  return (
    <article className="guide">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkArtworks]}
        remarkRehypeOptions={{ handlers: artworkHandlers }}
        components={components}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  )
}
