import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @State private var folderManager = FolderAccessManager()
    @State private var selectedFile: URL?
    @State private var markdownContent: String?
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        NavigationSplitView {
            GuideListView(
                folderManager: folderManager,
                selectedFile: $selectedFile
            )
        } detail: {
            if let content = markdownContent {
                MarkdownWebView(
                    markdownContent: content,
                    onArtworkTapped: { artwork in
                        openWindow(id: "imageViewer", value: artwork)
                    }
                )
            } else {
                ContentUnavailableView(
                    "Select a Guide",
                    systemImage: "doc.richtext",
                    description: Text("Choose a markdown file from the sidebar")
                )
            }
        }
        .onChange(of: selectedFile) { _, newFile in
            loadMarkdownFile(newFile)
        }
        .fileImporter(
            isPresented: $folderManager.isShowingPicker,
            allowedContentTypes: [.folder]
        ) { result in
            if case .success(let url) = result {
                folderManager.selectFolder(url)
            }
        }
    }

    private func loadMarkdownFile(_ url: URL?) {
        guard let url else {
            markdownContent = nil
            return
        }
        do {
            markdownContent = try String(contentsOf: url, encoding: .utf8)
        } catch {
            print("Failed to load file: \(error)")
            markdownContent = nil
        }
    }
}
