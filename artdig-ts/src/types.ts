export interface ArtworkData {
  title: string
  date?: string
  artist?: string
  source: 'met' | 'nga'
  sourceID: string
  sourceURL: string
  imageURL?: string
}

export interface ArtworkTapPayload {
  source: string
  sourceID: string
  title: string
  imageURL?: string
}
