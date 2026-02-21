import { visit, SKIP } from 'unist-util-visit'
import { toString } from 'mdast-util-to-string'
import type { Root, List, ListItem, Paragraph, PhrasingContent, Link, Emphasis } from 'mdast'
import type { ArtworkData } from './types'

// Custom MDAST node types
declare module 'mdast' {
  interface RootContentMap {
    artwork: ArtworkNode
    carousel: CarouselNode
  }
}

interface ArtworkNode {
  type: 'artwork'
  data: ArtworkData
  children: []
}

interface CarouselNode {
  type: 'carousel'
  children: ArtworkNode[]
  data: Record<string, never>
}

const SOURCE_PATTERN = /^(Met|NGA)\s+(\d+)$/

function parseArtworkItem(item: ListItem): ArtworkData | null {
  if (item.children.length !== 1 || item.children[0].type !== 'paragraph') return null

  const para = item.children[0] as Paragraph
  const children = para.children

  // Find the source link whose text matches "Met 123" or "NGA 456"
  let sourceLink: Link | null = null
  let sourceLinkIndex = -1
  for (let i = 0; i < children.length; i++) {
    const child = children[i]
    if (child.type === 'link') {
      const text = toString(child)
      if (SOURCE_PATTERN.test(text)) {
        sourceLink = child
        sourceLinkIndex = i
        break
      }
    }
  }
  if (!sourceLink) return null

  const linkText = toString(sourceLink)
  const match = linkText.match(SOURCE_PATTERN)!
  const source = match[1].toLowerCase() as 'met' | 'nga'
  const sourceID = match[2]

  // Find title from emphasis node before the source link
  let title = ''
  let emphasisIndex = -1
  for (let i = 0; i < sourceLinkIndex; i++) {
    if (children[i].type === 'emphasis') {
      title = toString(children[i] as Emphasis)
      emphasisIndex = i
      break
    }
  }
  if (!title) return null

  // Collect text between emphasis and source link to extract date and artist
  let betweenText = ''
  for (let i = emphasisIndex + 1; i < sourceLinkIndex; i++) {
    const child = children[i]
    if (child.type === 'text') {
      betweenText += (child as { value: string }).value
    }
  }

  // Extract date from parenthetical: (c. 1656–57), (1628), etc.
  let date: string | undefined
  const dateMatch = betweenText.match(/\(([^)]+)\)/)
  if (dateMatch) {
    date = dateMatch[1]
  }

  // Extract artist: text between date and last em-dash before source link
  let artist: string | undefined
  let textForArtist = betweenText
  if (dateMatch) {
    textForArtist = textForArtist.replace(dateMatch[0], '')
  }
  // Split by em-dash and filter non-empty parts
  const parts = textForArtist.split(/\s*\u2014\s*/).filter(p => p.trim().length > 0)
  if (parts.length > 0) {
    artist = parts[0].trim()
  }

  // Find optional [image](url) link after source link
  let imageURL: string | undefined
  for (let i = sourceLinkIndex + 1; i < children.length; i++) {
    const child = children[i]
    if (child.type === 'link' && toString(child) === 'image') {
      imageURL = (child as Link).url
      break
    }
  }

  return { title, date, artist, source, sourceID, sourceURL: sourceLink.url, imageURL }
}

interface ItemGroup {
  type: 'regular' | 'artwork'
  items: ListItem[]
  artworks: ArtworkData[]
}

function groupListItems(list: List): ItemGroup[] {
  const groups: ItemGroup[] = []
  let currentGroup: ItemGroup | null = null

  for (const item of list.children) {
    const artwork = parseArtworkItem(item as ListItem)
    const groupType = artwork ? 'artwork' : 'regular'

    if (!currentGroup || currentGroup.type !== groupType) {
      currentGroup = { type: groupType, items: [], artworks: [] }
      groups.push(currentGroup)
    }

    currentGroup.items.push(item as ListItem)
    if (artwork) {
      currentGroup.artworks.push(artwork)
    }
  }

  return groups
}

export default function remarkArtworks() {
  return (tree: Root) => {
    visit(tree, 'list', (node, index, parent) => {
      if (index === undefined || !parent) return
      const list = node as List
      const groups = groupListItems(list)

      // If no artwork items, leave the list unchanged
      if (!groups.some(g => g.type === 'artwork')) return

      // Build replacement nodes
      const replacements: any[] = []
      for (const group of groups) {
        if (group.type === 'regular') {
          // Keep as a regular list
          replacements.push({
            type: list.type,
            ordered: list.ordered,
            start: list.start,
            spread: list.spread,
            children: group.items,
          })
        } else {
          const artworkNodes: ArtworkNode[] = group.artworks.map(data => ({
            type: 'artwork' as const,
            data,
            children: [] as [],
          }))

          if (artworkNodes.length === 1) {
            replacements.push(artworkNodes[0])
          } else {
            replacements.push({
              type: 'carousel' as const,
              children: artworkNodes,
              data: {},
            })
          }
        }
      }

      parent.children.splice(index, 1, ...replacements)
      return [SKIP, index + replacements.length] as const
    })
  }
}

// remark-rehype handlers for custom node types
export const artworkHandlers = {
  carousel(state: any, node: any) {
    return {
      type: 'element' as const,
      tagName: 'carousel',
      properties: {},
      children: state.all(node),
    }
  },
  artwork(_state: any, node: any) {
    const d = node.data as ArtworkData
    const properties: Record<string, string> = {
      title: d.title,
      source: d.source,
      sourceId: d.sourceID,
      sourceUrl: d.sourceURL,
    }
    if (d.date) properties.date = d.date
    if (d.artist) properties.artist = d.artist
    if (d.imageURL) properties.imageUrl = d.imageURL

    return {
      type: 'element' as const,
      tagName: 'artwork',
      properties,
      children: [],
    }
  },
}
