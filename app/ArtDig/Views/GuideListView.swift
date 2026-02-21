import SwiftUI

struct GuideListView: View {
    var folderManager: FolderAccessManager
    @Binding var selectedFile: URL?

    var body: some View {
        List(selection: $selectedFile) {
            if folderManager.markdownFiles.isEmpty && folderManager.folderURL != nil {
                ContentUnavailableView(
                    "No Guides Found",
                    systemImage: "doc",
                    description: Text("No markdown files in this folder")
                )
            } else {
                ForEach(folderManager.markdownFiles, id: \.self) { file in
                    NavigationLink(value: file) {
                        Label(
                            file.deletingPathExtension().lastPathComponent,
                            systemImage: "doc.richtext"
                        )
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
