import Foundation
import Observation
import WidgetKit

@Observable
final class FavoritesManager {
    static let appGroupID = "group.com.artdig.shared"

    private(set) var artworks: [ArtworkLink] = []

    private let storageKey = "likedArtworks"
    private let migrationKey = "didMigrateToAppGroup"
    private let defaults: UserDefaults

    var count: Int { artworks.count }

    init() {
        defaults = UserDefaults(suiteName: Self.appGroupID) ?? .standard
        migrateIfNeeded()
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
            ThumbnailCache.cacheInBackground(artwork)
        }
        WidgetCenter.shared.reloadAllTimelines()
    }

    func remove(_ artwork: ArtworkLink) {
        artworks.removeAll { $0.source == artwork.source && $0.sourceID == artwork.sourceID }
        save()
        ThumbnailCache.removeCached(artwork)
        WidgetCenter.shared.reloadAllTimelines()
    }

    // MARK: - Shared Container Helpers

    static var sharedContainerURL: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupID)
    }

    static var thumbnailsDirectory: URL? {
        guard let container = sharedContainerURL else { return nil }
        let dir = container.appendingPathComponent("thumbnails", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func thumbnailFilename(for artwork: ArtworkLink) -> String {
        "\(artwork.source.rawValue)_\(artwork.sourceID).jpg"
    }

    static func thumbnailURL(for artwork: ArtworkLink) -> URL? {
        thumbnailsDirectory?.appendingPathComponent(thumbnailFilename(for: artwork))
    }

    // MARK: - Private

    private func save() {
        guard let data = try? JSONEncoder().encode(artworks) else { return }
        defaults.set(data, forKey: storageKey)
    }

    private func load() {
        guard let data = defaults.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([ArtworkLink].self, from: data)
        else { return }
        artworks = decoded
    }

    private func migrateIfNeeded() {
        guard !defaults.bool(forKey: migrationKey) else { return }
        if let data = UserDefaults.standard.data(forKey: storageKey) {
            defaults.set(data, forKey: storageKey)
            UserDefaults.standard.removeObject(forKey: storageKey)
        }
        defaults.set(true, forKey: migrationKey)
    }
}

// Extracted to avoid Swift 6 region-based isolation checker bug with Task closures in @Observable classes
enum ThumbnailCache {
    static func cacheInBackground(_ artwork: ArtworkLink) {
        let source = artwork.source
        let sourceID = artwork.sourceID
        let imageURL = artwork.imageURL
        let fileURL = FavoritesManager.thumbnailURL(for: artwork)
        Task {
            guard let fileURL else { return }
            guard let data = await downloadThumbnail(source: source, sourceID: sourceID, imageURL: imageURL) else { return }
            try? data.write(to: fileURL)
        }
    }

    static func removeCached(_ artwork: ArtworkLink) {
        guard let fileURL = FavoritesManager.thumbnailURL(for: artwork) else { return }
        try? FileManager.default.removeItem(at: fileURL)
    }

    private static func downloadThumbnail(source: ArtworkLink.Source, sourceID: String, imageURL: URL?) async -> Data? {
        guard let url = await resolveURL(source: source, sourceID: sourceID, imageURL: imageURL) else { return nil }
        return try? await URLSession.shared.data(from: url).0
    }

    private static func resolveURL(source: ArtworkLink.Source, sourceID: String, imageURL: URL?) async -> URL? {
        switch source {
        case .met:
            let response = try? await MetImageService.shared.fetchArtwork(objectID: sourceID)
            return response.flatMap { $0.primaryImageSmall.isEmpty ? nil : URL(string: $0.primaryImageSmall) }
        case .nga:
            guard let fullURL = imageURL else { return nil }
            let str = fullURL.absoluteString
            if str.contains("/full/max/") {
                return URL(string: str.replacingOccurrences(of: "/full/max/", with: "/full/!600,600/"))
            } else {
                return URL(string: str.replacingOccurrences(of: "/full/!1080,1080/", with: "/full/!600,600/"))
            }
        }
    }
}
