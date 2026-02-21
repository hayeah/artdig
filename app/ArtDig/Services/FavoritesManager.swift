import Foundation
import Observation

@Observable
final class FavoritesManager {
    private(set) var artworks: [ArtworkLink] = []

    private let storageKey = "likedArtworks"

    var count: Int { artworks.count }

    init() {
        load()
    }

    func isLiked(_ artwork: ArtworkLink) -> Bool {
        artworks.contains { $0.source == artwork.source && $0.sourceID == artwork.sourceID }
    }

    func toggle(_ artwork: ArtworkLink) {
        if isLiked(artwork) {
            remove(artwork)
        } else {
            artworks.append(artwork)
            save()
        }
    }

    func remove(_ artwork: ArtworkLink) {
        artworks.removeAll { $0.source == artwork.source && $0.sourceID == artwork.sourceID }
        save()
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(artworks) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([ArtworkLink].self, from: data)
        else { return }
        artworks = decoded
    }
}
