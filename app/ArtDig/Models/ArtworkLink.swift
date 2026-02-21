import Foundation

struct ArtworkLink: Codable, Hashable {
    enum Source: String, Codable {
        case met, nga
    }

    let source: Source
    let sourceID: String
    let title: String?
    let imageURL: URL?
}
