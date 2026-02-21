import WidgetKit
import SwiftUI

struct ArtworkEntry: TimelineEntry {
    let date: Date
    let title: String
    let image: UIImage?
}

struct ArtDigProvider: TimelineProvider {
    func placeholder(in context: Context) -> ArtworkEntry {
        ArtworkEntry(date: .now, title: "ArtDig", image: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (ArtworkEntry) -> Void) {
        let entry = loadRandomEntry() ?? ArtworkEntry(date: .now, title: "ArtDig", image: nil)
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ArtworkEntry>) -> Void) {
        let entry = loadRandomEntry() ?? ArtworkEntry(date: .now, title: "No favorites yet", image: nil)
        let nextUpdate = Calendar.current.date(byAdding: .hour, value: 1, to: .now) ?? .now
        completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
    }

    private func loadRandomEntry() -> ArtworkEntry? {
        let appGroupID = "group.com.artdig.shared"
        guard let defaults = UserDefaults(suiteName: appGroupID),
              let data = defaults.data(forKey: "likedArtworks"),
              let artworks = try? JSONDecoder().decode([ArtworkLink].self, from: data),
              !artworks.isEmpty
        else { return nil }

        let artwork = artworks.randomElement()!
        let image = loadCachedImage(for: artwork, appGroupID: appGroupID)
        let title = artwork.title ?? "\(artwork.source == .met ? "Met" : "NGA") #\(artwork.sourceID)"
        return ArtworkEntry(date: .now, title: title, image: image)
    }

    private func loadCachedImage(for artwork: ArtworkLink, appGroupID: String) -> UIImage? {
        guard let container = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else { return nil }
        let filename = "\(artwork.source.rawValue)_\(artwork.sourceID).jpg"
        let fileURL = container.appendingPathComponent("thumbnails").appendingPathComponent(filename)
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        return UIImage(data: data)
    }
}

struct ArtDigWidgetEntryView: View {
    var entry: ArtworkEntry

    var body: some View {
        Group {
            if let image = entry.image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .overlay(alignment: .bottom) {
                        Text(entry.title)
                            .font(.caption2)
                            .foregroundStyle(.white)
                            .shadow(radius: 2)
                            .lineLimit(1)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .frame(maxWidth: .infinity)
                            .background(.ultraThinMaterial.opacity(0.6))
                    }
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
        .supportedMountingStyles([.recessed])
        .widgetTexture(.paper)
        #endif
    }
}
