import SwiftUI

struct GuideListView: View {
    var folderManager: FolderAccessManager
    @Binding var selection: SidebarSelection?
    @Environment(FavoritesManager.self) private var favorites

    var body: some View {
        List(selection: $selection) {
            Section {
                NavigationLink(value: SidebarSelection.liked) {
                    Label {
                        HStack {
                            Text("Liked")
                            Spacer()
                            if favorites.count > 0 {
                                Text("\(favorites.count)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 2)
                                    .background(.fill.tertiary, in: Capsule())
                            }
                        }
                    } icon: {
                        Image(systemName: "heart.fill")
                            .foregroundStyle(.pink)
                    }
                }
            }

            Section("Guides") {
                if folderManager.markdownFiles.isEmpty && folderManager.folderURL != nil {
                    ContentUnavailableView(
                        "No Guides Found",
                        systemImage: "doc",
                        description: Text("No markdown files in this folder")
                    )
                } else {
                    ForEach(folderManager.markdownFiles, id: \.self) { file in
                        NavigationLink(value: SidebarSelection.guide(file)) {
                            Label(
                                file.deletingPathExtension().lastPathComponent,
                                systemImage: "doc.richtext"
                            )
                        }
                    }
                }
            }
        }
        .navigationTitle("Guides")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Open Folder", systemImage: "folder") {
                    folderManager.isShowingPicker = true
                }
            }
        }
    }
}
