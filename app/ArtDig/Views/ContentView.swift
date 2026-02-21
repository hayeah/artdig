import SwiftUI
import UniformTypeIdentifiers

enum SidebarSelection: Hashable {
    case guide(URL)
    case liked
}

struct ContentView: View {
    @State private var folderManager = FolderAccessManager()
    @State private var selection: SidebarSelection?
    @State private var markdownContent: String?
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        NavigationSplitView {
            GuideListView(
                folderManager: folderManager,
                selection: $selection
            )
        } detail: {
            switch selection {
            case .liked:
                LikedArtworksView()
            case .guide:
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
            case nil:
                ContentUnavailableView(
                    "Select a Guide",
                    systemImage: "doc.richtext",
                    description: Text("Choose a markdown file from the sidebar")
                )
            }
        }
        .onChange(of: selection) { _, newSelection in
            if case .guide(let url) = newSelection {
                loadMarkdownFile(url)
            } else {
                markdownContent = nil
            }
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

    private func loadMarkdownFile(_ url: URL) {
        do {
            markdownContent = try String(contentsOf: url, encoding: .utf8)
        } catch {
            print("Failed to load file: \(error)")
            markdownContent = nil
        }
    }
}
