import SwiftUI
import Nuke

struct ArtworkImageView: View {
    let artwork: ArtworkLink
    @State private var previewImage: UIImage?
    @State private var fullImage: UIImage?
    @State private var isLoadingFull = false
    @State private var downloadProgress: Float = 0
    @State private var downloadedBytes: Int64 = 0
    @State private var errorMessage: String?

    private var displayImage: UIImage? {
        fullImage ?? previewImage
    }

    var body: some View {
        Group {
            if let image = displayImage {
                Image(uiImage: image)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
                    .overlay(alignment: .bottom) {
                        if isLoadingFull {
                            VStack(spacing: 4) {
                                ProgressView(value: downloadProgress)
                                    .progressViewStyle(.linear)
                                Text(progressLabel)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.horizontal, 40)
                            .padding(.bottom, 12)
                        }
                    }
            } else if let errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ProgressView("Loading preview...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task { await loadImage() }
    }

    private var progressLabel: String {
        let pct = Int(downloadProgress * 100)
        let mb = String(format: "%.1f", Double(downloadedBytes) / 1_000_000)
        return "\(pct)% — \(mb) MB"
    }

    private func loadImage() async {
        let urls = await resolveURLs()
        let pipeline = ImagePipeline.shared

        // Stage 1: load preview (fast, cached by Nuke)
        if let previewURL = urls.preview {
            do {
                previewImage = try await pipeline.image(for: previewURL)
            } catch {
                // Preview failure is OK, continue to full
            }
        }

        // Stage 2: load full resolution with progress (cached by Nuke)
        guard let fullURL = urls.full else {
            if previewImage == nil {
                errorMessage = "No image available"
            }
            return
        }

        // Check cache first — skip progress if already cached
        let fullRequest = ImageRequest(url: fullURL)
        if let cached = pipeline.cache.cachedImage(for: fullRequest) {
            fullImage = cached.image
            return
        }

        isLoadingFull = true
        let task = pipeline.imageTask(with: fullRequest)

        // Observe progress
        Task {
            for await progress in task.progress {
                downloadProgress = progress.fraction
                downloadedBytes = progress.completed
            }
        }

        do {
            fullImage = try await task.image
        } catch {
            if previewImage == nil {
                errorMessage = error.localizedDescription
            }
        }
        isLoadingFull = false
    }

    private struct ImageURLs {
        let preview: URL?
        let full: URL?
    }

    private func resolveURLs() async -> ImageURLs {
        if let fullURL = artwork.imageURL {
            // NGA IIIF — derive preview by swapping size parameter
            let previewURL = ngaPreviewURL(from: fullURL)
            return ImageURLs(preview: previewURL, full: fullURL)
        }

        if artwork.source == .met {
            do {
                let response = try await MetImageService.shared.fetchArtwork(objectID: artwork.sourceID)
                let full = response.primaryImage.isEmpty ? nil : URL(string: response.primaryImage)
                let preview = response.primaryImageSmall.isEmpty ? nil : URL(string: response.primaryImageSmall)
                return ImageURLs(preview: preview, full: full)
            } catch {
                errorMessage = error.localizedDescription
                return ImageURLs(preview: nil, full: nil)
            }
        }

        return ImageURLs(preview: nil, full: nil)
    }

    /// Swap IIIF `/full/max/` for a smaller size to get a fast preview
    private func ngaPreviewURL(from fullURL: URL) -> URL? {
        let str = fullURL.absoluteString
        guard str.contains("/full/max/") else { return nil }
        return URL(string: str.replacingOccurrences(of: "/full/max/", with: "/full/!600,600/"))
    }
}
