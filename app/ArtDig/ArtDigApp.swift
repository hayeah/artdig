import SwiftUI

@main
struct ArtDigApp: App {
    var body: some Scene {
        WindowGroup(id: "main") {
            ContentView()
        }

        WindowGroup(id: "imageViewer", for: ArtworkLink.self) { $artwork in
            if let artwork {
                ArtworkImageView(artwork: artwork)
            }
        }
        .windowStyle(.plain)
        .defaultSize(width: 800, height: 800)
    }
}
