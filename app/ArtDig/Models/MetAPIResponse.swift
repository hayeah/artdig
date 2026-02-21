import Foundation

struct MetAPIResponse: Codable, Sendable {
    let objectID: Int
    let primaryImage: String
    let primaryImageSmall: String
    let title: String
    let artistDisplayName: String
    let objectDate: String
    let department: String?
    let medium: String?
}
