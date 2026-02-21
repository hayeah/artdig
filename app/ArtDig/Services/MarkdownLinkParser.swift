import Foundation

final class MarkdownLinkParser {
    private var ngaImageURLs: [String: URL] = [:]

    func preprocess(markdown: String) {
        ngaImageURLs.removeAll()

        // Match: [NGA {id}](...) · [image]({iiif_url})
        let pattern = /\[NGA\s+(\d+)\]\([^)]+\)\s*·\s*\[image\]\((https:\/\/api\.nga\.gov\/iiif\/[^)]+)\)/
        for match in markdown.matches(of: pattern) {
            let id = String(match.1)
            if let url = URL(string: String(match.2)) {
                ngaImageURLs[id] = url
            }
        }
    }

    func artworkLink(for url: URL) -> ArtworkLink? {
        let urlString = url.absoluteString

        // Met: metmuseum.org/art/collection/search/{id}
        let metPattern = /metmuseum\.org\/art\/collection\/search\/(\d+)/
        if let match = urlString.firstMatch(of: metPattern) {
            return ArtworkLink(source: .met, sourceID: String(match.1), title: nil, imageURL: nil)
        }

        // NGA collection: nga.gov/collection/art-object-page.{id}.html
        let ngaPattern = /nga\.gov\/collection\/art-object-page\.(\d+)\.html/
        if let match = urlString.firstMatch(of: ngaPattern) {
            let id = String(match.1)
            return ArtworkLink(source: .nga, sourceID: id, title: nil, imageURL: ngaImageURLs[id])
        }

        // Direct NGA IIIF image URL
        if urlString.contains("api.nga.gov/iiif/") {
            return ArtworkLink(source: .nga, sourceID: "", title: nil, imageURL: url)
        }

        return nil
    }
}
