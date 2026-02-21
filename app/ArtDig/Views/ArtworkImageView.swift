import SwiftUI
import NukeUI

struct ArtworkImageView: View {
    let artwork: ArtworkLink
    @State private var resolvedImageURL: URL?
    @State private var metadata: MetAPIResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 0)

            if let resolvedImageURL {
                LazyImage(url: resolvedImageURL) { state in
                    if let image = state.image {
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    } else if state.isLoading {
                        ProgressView("Loading painting...")
                    } else {
                        ContentUnavailableView(
                            "Failed to Load",
                            systemImage: "photo",
                            description: Text("Could not load the painting image")
                        )
                    }
                }
                .padding()
            } else if isLoading {
                ProgressView("Resolving artwork...")
            } else if let errorMessage {
                ContentUnavailableView(
                    "Error",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            }

            Spacer(minLength: 0)

            metadataBar
                .padding()
        }
        .frame(minWidth: 500, minHeight: 500)
        .task { await resolveImage() }
    }

    @ViewBuilder
    private var metadataBar: some View {
        if let metadata {
            VStack(spacing: 4) {
                Text(metadata.title)
                    .font(.headline)
                    .multilineTextAlignment(.center)
                if !metadata.artistDisplayName.isEmpty {
                    Text(metadata.artistDisplayName)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                if !metadata.objectDate.isEmpty {
                    Text(metadata.objectDate)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
        } else {
            Text("\(artwork.source == .met ? "Met" : "NGA") #\(artwork.sourceID)")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func resolveImage() async {
        if let url = artwork.imageURL {
            resolvedImageURL = url
            isLoading = false
            return
        }

        guard artwork.source == .met else {
            errorMessage = "No image URL available"
            isLoading = false
            return
        }

        do {
            let response = try await MetImageService.shared.fetchArtwork(objectID: artwork.sourceID)
            metadata = response
            if !response.primaryImage.isEmpty {
                resolvedImageURL = URL(string: response.primaryImage)
            } else {
                errorMessage = "No image available for this artwork"
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
