import Foundation

struct ArtworkLink: Codable, Hashable {
    enum Source: String, Codable {
        case met, nga
    }

    let source: Source
    let sourceID: String
    let title: String?
    let imageURL: URL?

    var metWebURL: URL? {
        guard source == .met else { return nil }
        return URL(string: "https://www.metmuseum.org/art/collection/search/\(sourceID)")
    }
}
