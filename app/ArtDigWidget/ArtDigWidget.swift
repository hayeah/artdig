import WidgetKit
import SwiftUI
import AppIntents

struct ArtworkEntry: TimelineEntry {
    let date: Date
    let title: String
    let image: UIImage?
}

struct NextPaintingIntent: AppIntent {
    static let title: LocalizedStringResource = "Next Painting"

    func perform() async throws -> some IntentResult {
        let appGroupID = "group.com.artdig.shared"
        let defaults = UserDefaults(suiteName: appGroupID)
        let current = defaults?.integer(forKey: "widgetPaintingIndex") ?? 0
        defaults?.set(current + 1, forKey: "widgetPaintingIndex")
        WidgetCenter.shared.reloadAllTimelines()
        return .result()
    }
}

struct ArtDigProvider: TimelineProvider {
    private let appGroupID = "group.com.artdig.shared"

    func placeholder(in context: Context) -> ArtworkEntry {
        ArtworkEntry(date: .now, title: "ArtDig", image: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping @Sendable (ArtworkEntry) -> Void) {
        Task {
            let entry = await loadEntry() ?? ArtworkEntry(date: .now, title: "ArtDig", image: nil)
            completion(entry)
        }
    }

    func getTimeline(in context: Context, completion: @escaping @Sendable (Timeline<ArtworkEntry>) -> Void) {
        Task {
            let entry = await loadEntry() ?? ArtworkEntry(date: .now, title: "No favorites yet", image: nil)
            completion(Timeline(entries: [entry], policy: .never))
        }
    }

    private func loadEntry() async -> ArtworkEntry? {
        guard let defaults = UserDefaults(suiteName: appGroupID),
              let data = defaults.data(forKey: "likedArtworks"),
              let artworks = try? JSONDecoder().decode([ArtworkLink].self, from: data),
              !artworks.isEmpty
        else { return nil }

        let index = defaults.integer(forKey: "widgetPaintingIndex") % artworks.count
        let artwork = artworks[index]
        let image = await fetchImage(for: artwork)
        let title = artwork.title ?? "\(artwork.source == .met ? "Met" : "NGA") #\(artwork.sourceID)"
        return ArtworkEntry(date: .now, title: title, image: image)
    }

    private func fetchImage(for artwork: ArtworkLink) async -> UIImage? {
        if let cached = loadCachedImage(for: artwork) { return cached }

        guard let url = await resolveImageURL(for: artwork) else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }

        cacheImageData(data, for: artwork)
        return UIImage(data: data)
    }

    private func resolveImageURL(for artwork: ArtworkLink) async -> URL? {
        switch artwork.source {
        case .met:
            guard let apiURL = URL(string: "https://collectionapi.metmuseum.org/public/collection/v1/objects/\(artwork.sourceID)"),
                  let (data, _) = try? await URLSession.shared.data(from: apiURL),
                  let response = try? JSONDecoder().decode(MetResponse.self, from: data),
                  !response.primaryImageSmall.isEmpty
            else { return nil }
            return URL(string: response.primaryImageSmall)
        case .nga:
            guard let fullURL = artwork.imageURL else { return nil }
            let str = fullURL.absoluteString
            if str.contains("/full/max/") {
                return URL(string: str.replacingOccurrences(of: "/full/max/", with: "/full/!600,600/"))
            } else {
                return URL(string: str.replacingOccurrences(of: "/full/!1080,1080/", with: "/full/!600,600/"))
            }
        }
    }

    private func loadCachedImage(for artwork: ArtworkLink) -> UIImage? {
        guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else { return nil }
        let fileURL = container.appendingPathComponent("thumbnails").appendingPathComponent("\(artwork.source.rawValue)_\(artwork.sourceID).jpg")
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        return UIImage(data: data)
    }

    private func cacheImageData(_ imageData: Data, for artwork: ArtworkLink) {
        guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else { return }
        let dir = container.appendingPathComponent("thumbnails", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let fileURL = dir.appendingPathComponent("\(artwork.source.rawValue)_\(artwork.sourceID).jpg")
        try? imageData.write(to: fileURL)
    }
}

private struct MetResponse: Codable {
    let primaryImageSmall: String
}

struct ArtDigWidgetEntryView: View {
    var entry: ArtworkEntry

    var body: some View {
        Group {
            if let image = entry.image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "heart.fill")
                        .font(.largeTitle)
                        .foregroundStyle(.pink)
                    Text(entry.title)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
        }
        .containerBackground(for: .widget) {
            Color.black
        }
    }
}

struct ArtDigWidget: Widget {
    let kind = "ArtDigWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ArtDigProvider()) { entry in
            ArtDigWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("ArtDig")
        .description("Display a favorite painting on your wall.")
        .supportedFamilies([.systemLarge, .systemExtraLarge])
        #if os(visionOS)
        .supportedMountingStyles([.elevated])
        .widgetTexture(.paper)
        #endif
    }
}
