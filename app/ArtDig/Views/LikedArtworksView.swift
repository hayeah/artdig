import SwiftUI

struct LikedArtworksView: View {
    @Environment(FavoritesManager.self) private var favorites
    @Environment(\.openWindow) private var openWindow

    private let columns = [
        GridItem(.adaptive(minimum: 200, maximum: 300), spacing: 16)
    ]

    var body: some View {
        Group {
            if favorites.artworks.isEmpty {
                ContentUnavailableView(
                    "No Liked Artworks",
                    systemImage: "heart.slash",
                    description: Text("Tap the heart icon in the image viewer to like artworks")
                )
            } else {
                ScrollView {
                    LazyVGrid(columns: columns, spacing: 16) {
                        ForEach(favorites.artworks, id: \.self) { artwork in
                            ArtworkCard(artwork: artwork)
                                .onTapGesture {
                                    openWindow(id: "imageViewer", value: artwork)
                                }
                        }
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("Liked")
    }
}

private struct ArtworkCard: View {
    let artwork: ArtworkLink
    @State private var thumbnailURL: URL?
    @State private var didResolve = false

    var body: some View {
        VStack(spacing: 8) {
            Group {
                if let url = thumbnailURL {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        case .failure:
                            placeholder
                        default:
                            ProgressView()
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                        }
                    }
                } else if didResolve {
                    placeholder
                } else {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .frame(height: 200)
            .clipped()
            .cornerRadius(12)

            Text(cardLabel)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .task { await resolveThumbnail() }
    }

    private var cardLabel: String {
        if let title = artwork.title, !title.isEmpty {
            return title
        }
        return "\(artwork.source == .met ? "Met" : "NGA") #\(artwork.sourceID)"
    }

    private var placeholder: some View {
        Image(systemName: "photo")
            .font(.largeTitle)
            .foregroundStyle(.tertiary)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func resolveThumbnail() async {
        defer { didResolve = true }

        switch artwork.source {
        case .met:
            guard let response = try? await MetImageService.shared.fetchArtwork(objectID: artwork.sourceID) else { return }
            if !response.primaryImageSmall.isEmpty {
                thumbnailURL = URL(string: response.primaryImageSmall)
            }
        case .nga:
            if let url = artwork.imageURL {
                let str = url.absoluteString
                if str.contains("/full/max/") {
                    thumbnailURL = URL(string: str.replacingOccurrences(of: "/full/max/", with: "/full/!300,300/"))
                } else {
                    thumbnailURL = URL(string: str.replacingOccurrences(of: "/full/!1080,1080/", with: "/full/!300,300/"))
                }
            }
        }
    }
}
