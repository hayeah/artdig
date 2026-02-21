import SwiftUI

@main
struct ArtDigApp: App {
    @State private var favoritesManager = FavoritesManager()

    var body: some Scene {
        WindowGroup(id: "main") {
            ContentView()
                .environment(favoritesManager)
        }

        WindowGroup(id: "imageViewer", for: ArtworkLink.self) { $artwork in
            if let artwork {
                ArtworkImageView(artwork: artwork)
                    .environment(favoritesManager)
            }
        }
        .windowStyle(.plain)
        .defaultSize(width: 800, height: 800)
    }
}
