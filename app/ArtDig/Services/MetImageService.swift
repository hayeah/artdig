import Foundation

actor MetImageService {
    static let shared = MetImageService()
    private var cache: [String: MetAPIResponse] = [:]

    func fetchArtwork(objectID: String) async throws -> MetAPIResponse {
        if let cached = cache[objectID] { return cached }

        guard let url = URL(string: "https://collectionapi.metmuseum.org/public/collection/v1/objects/\(objectID)") else {
            throw URLError(.badURL)
        }

        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(MetAPIResponse.self, from: data)
        cache[objectID] = response
        return response
    }
}
