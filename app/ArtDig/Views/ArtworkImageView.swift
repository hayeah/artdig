import SwiftUI
import Nuke
import UIKit

struct ArtworkImageView: View {
    let artwork: ArtworkLink
    @State private var previewImage: UIImage?
    @State private var fullImage: UIImage?
    @State private var paintingAspectRatio: CGFloat?
    @State private var isLoadingFull = false
    @State private var downloadProgress: Float = 0
    @State private var downloadedBytes: Int64 = 0
    @State private var errorMessage: String?
    @State private var fullURL: URL?
    @Environment(FavoritesManager.self) private var favorites
    @Environment(\.openURL) private var openURL
    @Environment(\.dismiss) private var dismiss

    private var displayImage: UIImage? {
        fullImage ?? previewImage
    }

    private var hasFullRes: Bool {
        fullImage != nil
    }

    private var windowAspectRatio: CGFloat {
        paintingAspectRatio ?? 1
    }

    private var targetWindowSize: CGSize? {
        guard let aspectRatio = paintingAspectRatio, aspectRatio.isFinite, aspectRatio > 0 else {
            return nil
        }

        let maxSide: CGFloat = 800
        if aspectRatio >= 1 {
            return CGSize(width: maxSide, height: maxSide / aspectRatio)
        } else {
            return CGSize(width: maxSide * aspectRatio, height: maxSide)
        }
    }

    var body: some View {
        Group {
            if let image = displayImage {
                Image(uiImage: image)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .overlay(alignment: .bottomLeading) {
                        Button {
                            favorites.toggle(artwork)
                        } label: {
                            Image(systemName: favorites.isLiked(artwork) ? "heart.fill" : "heart")
                                .font(.title2)
                                .symbolRenderingMode(.hierarchical)
                                .foregroundStyle(favorites.isLiked(artwork) ? .pink : .white)
                        }
                        .buttonStyle(.plain)
                        .opacity(0.2)
                        .padding(12)
                    }
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
        .aspectRatio(windowAspectRatio, contentMode: .fit)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            if let targetWindowSize {
                WindowGeometryUpdater(
                    size: targetWindowSize,
                    resizingRestrictions: .uniform
                )
                .frame(width: 0, height: 0)
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
                let image = cached.image
                fullImage = image
                updateAspectRatio(from: image)
                return
            }
        }

        // Load preview
        if let previewURL = urls.preview {
            do {
                let image = try await pipeline.image(for: previewURL)
                previewImage = image
                updateAspectRatio(from: image)
            } catch {
                // Preview failure is OK
            }
        }

        if previewImage == nil && fullImage == nil {
            if artwork.source == .met, let webURL = artwork.metWebURL {
                openURL(webURL)
                dismiss()
                return
            }
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
            let image = try await task.image
            fullImage = image
            updateAspectRatio(from: image)
        } catch {
            // Keep preview visible on failure
        }
        isLoadingFull = false
    }

    private func updateAspectRatio(from image: UIImage) {
        let size = image.size
        guard size.width > 0, size.height > 0 else { return }

        let ratio = size.width / size.height
        guard ratio.isFinite, ratio > 0 else { return }

        paintingAspectRatio = ratio
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

private struct WindowGeometryUpdater: UIViewRepresentable {
    let size: CGSize
    let resizingRestrictions: UIWindowScene.ResizingRestrictions

    func makeUIView(context: Context) -> WindowGeometryHostView {
        WindowGeometryHostView()
    }

    func updateUIView(_ uiView: WindowGeometryHostView, context: Context) {
        uiView.update(size: size, resizingRestrictions: resizingRestrictions)
    }
}

private final class WindowGeometryHostView: UIView {
    private struct GeometryRequest: Equatable {
        let size: CGSize
        let resizingRestrictions: UIWindowScene.ResizingRestrictions
    }

    private var request: GeometryRequest?
    private var lastAppliedRequest: GeometryRequest?

    override func didMoveToWindow() {
        super.didMoveToWindow()
        applyIfNeeded()
    }

    func update(size: CGSize, resizingRestrictions: UIWindowScene.ResizingRestrictions) {
        request = GeometryRequest(size: size, resizingRestrictions: resizingRestrictions)
        applyIfNeeded()
    }

    private func applyIfNeeded() {
        guard let windowScene = window?.windowScene, let request else { return }
        guard request != lastAppliedRequest else { return }

        let preferences = UIWindowScene.GeometryPreferences.Vision(
            size: request.size,
            minimumSize: nil,
            maximumSize: nil,
            resizingRestrictions: request.resizingRestrictions
        )

        windowScene.requestGeometryUpdate(preferences) { error in
            print("Failed to update window geometry: \(error.localizedDescription)")
        }
        lastAppliedRequest = request
    }
}
