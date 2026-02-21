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
    @State private var fullURL: URL?

    private var displayImage: UIImage? {
        fullImage ?? previewImage
    }

    private var hasFullRes: Bool {
        fullImage != nil
    }

    var body: some View {
        Group {
            if let image = displayImage {
                Image(uiImage: image)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
                    .overlay(alignment: .bottomTrailing) {
                        if isLoadingFull {
                            // Download progress
                            HStack(spacing: 8) {
                                ProgressView(value: downloadProgress)
                                    .progressViewStyle(.linear)
                                    .frame(width: 120)
                                Text(progressLabel)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(12)
                        } else if !hasFullRes && fullURL != nil {
                            // Full-res download button
                            Button {
                                Task { await loadFullRes() }
                            } label: {
                                Image(systemName: "arrow.down.circle.fill")
                                    .font(.title2)
                                    .symbolRenderingMode(.hierarchical)
                                    .foregroundStyle(.white)
                            }
                            .buttonStyle(.plain)
                            .padding(12)
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
        .task { await loadPreview() }
    }

    private var progressLabel: String {
        let pct = Int(downloadProgress * 100)
        let mb = String(format: "%.1f", Double(downloadedBytes) / 1_000_000)
        return "\(pct)% — \(mb) MB"
    }

    private func loadPreview() async {
        let urls = await resolveURLs()
        fullURL = urls.full
        let pipeline = ImagePipeline.shared

        // Check if full-res is already cached
        if let full = urls.full {
            let fullRequest = ImageRequest(url: full)
            if let cached = pipeline.cache.cachedImage(for: fullRequest) {
                fullImage = cached.image
                return
            }
        }

        // Load preview
        if let previewURL = urls.preview {
            do {
                previewImage = try await pipeline.image(for: previewURL)
            } catch {
                // Preview failure is OK
            }
        }

        if previewImage == nil && fullImage == nil {
            errorMessage = "No image available"
        }
    }

    private func loadFullRes() async {
        guard let url = fullURL else { return }

        isLoadingFull = true
        downloadProgress = 0
        downloadedBytes = 0

        let task = ImagePipeline.shared.imageTask(with: ImageRequest(url: url))

        Task {
            for await progress in task.progress {
                downloadProgress = progress.fraction
                downloadedBytes = progress.completed
            }
        }

        do {
            fullImage = try await task.image
        } catch {
            // Keep preview visible on failure
        }
        isLoadingFull = false
    }

    private struct ImageURLs {
        let preview: URL?
        let full: URL?
    }

    private func resolveURLs() async -> ImageURLs {
        if let fullURL = artwork.imageURL {
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

    /// Swap IIIF `/full/max/` for `!1080,1080` for a quick but decent preview
    private func ngaPreviewURL(from fullURL: URL) -> URL? {
        let str = fullURL.absoluteString
        guard str.contains("/full/max/") else { return nil }
        return URL(string: str.replacingOccurrences(of: "/full/max/", with: "/full/!1080,1080/"))
    }
}
