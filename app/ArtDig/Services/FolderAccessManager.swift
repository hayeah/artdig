import Foundation
import Observation

@Observable
final class FolderAccessManager {
    var folderURL: URL?
    var markdownFiles: [URL] = []
    var isShowingPicker = false

    private let bookmarkKey = "iCloudFolderBookmark"

    init() {
        restoreBookmark()
    }

    func selectFolder(_ url: URL) {
        guard url.startAccessingSecurityScopedResource() else { return }
        saveBookmark(for: url)
        folderURL = url
        scanForMarkdownFiles()
    }

    private func saveBookmark(for url: URL) {
        do {
            let bookmarkData = try url.bookmarkData(
                options: [],
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            UserDefaults.standard.set(bookmarkData, forKey: bookmarkKey)
        } catch {
            print("Failed to save bookmark: \(error)")
        }
    }

    private func restoreBookmark() {
        guard let bookmarkData = UserDefaults.standard.data(forKey: bookmarkKey) else { return }
        do {
            var isStale = false
            let url = try URL(
                resolvingBookmarkData: bookmarkData,
                bookmarkDataIsStale: &isStale
            )
            guard url.startAccessingSecurityScopedResource() else { return }
            if isStale {
                saveBookmark(for: url)
            }
            folderURL = url
            scanForMarkdownFiles()
        } catch {
            print("Failed to restore bookmark: \(error)")
        }
    }

    func scanForMarkdownFiles() {
        guard let folderURL else { return }
        do {
            let contents = try FileManager.default.contentsOfDirectory(
                at: folderURL,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: .skipsHiddenFiles
            )
            markdownFiles = contents
                .filter { $0.pathExtension.lowercased() == "md" }
                .sorted {
                    $0.lastPathComponent.localizedCaseInsensitiveCompare($1.lastPathComponent) == .orderedAscending
                }
        } catch {
            print("Failed to scan folder: \(error)")
            markdownFiles = []
        }
    }
}
