# NYPL Digital Collections API

Notes on how to programmatically access items from [NYPL Digital Collections](https://digitalcollections.nypl.org/).

## Overview

NYPL exposes two API layers:

- **Collections API** (`api-collections.nypl.org`) — the newer backend powering the current site. Most endpoints require an API key, but **IIIF manifests are public**.
- **Repo API** (`api.repo.nypl.org`) — the older API with token-based auth. Documented at <https://api.repo.nypl.org/>. Requires signing up for a token.

For building a reader, the manifest endpoint is all you need.

## Public Endpoints (No Auth)

### IIIF Manifest

```
GET https://api-collections.nypl.org/manifests/{item-uuid}
```

Returns a [IIIF Presentation API 3.0](https://iiif.io/api/presentation/3.0/) manifest in JSON-LD. Contains:

- All canvases (pages) with labels
- Image service references for each page
- Rendering links at multiple sizes
- Metadata (title, creator, dates, rights)
- `behavior: ["paged"]` for book-like items

Example:

```
https://api-collections.nypl.org/manifests/ac68db70-b960-013c-62f9-0242ac110004
```

### IIIF Image API

The image server is at `iiif.nypl.org`, running Cantaloupe 5.0.7. Supports IIIF Image API v2 and v3.

**URL pattern:**

```
https://iiif.nypl.org/iiif/{version}/{imageId}/{region}/{size}/{rotation}/default.{format}
```

**Common requests:**

| URL | Description |
|---|---|
| `https://iiif.nypl.org/iiif/3/{id}/full/max/0/default.jpg` | Full resolution JPEG |
| `https://iiif.nypl.org/iiif/3/{id}/full/max/0/default.tif` | Full resolution TIFF |
| `https://iiif.nypl.org/iiif/3/{id}/full/{w},{h}/0/default.jpg` | Specific pixel dimensions |
| `https://iiif.nypl.org/iiif/3/{id}/full/,{h}/0/default.jpg` | Scale by height only |
| `https://iiif.nypl.org/iiif/2/{id}/full/max/0/default.jpg` | Same via IIIF v2 |

**Image info (dimensions, tile sizes):**

```
GET https://iiif.nypl.org/iiif/3/{imageId}/info.json
```

Returns:

```json
{
  "width": 566,
  "height": 760,
  "sizes": [
    {"width": 71, "height": 95},
    {"width": 142, "height": 190},
    {"width": 283, "height": 380},
    {"width": 566, "height": 760}
  ],
  "tiles": [{"width": 512, "height": 512, "scaleFactors": [1, 2, 4, 8]}]
}
```

## Authenticated Endpoints

These require the header `x-nypl-collections-api-key: {key}`:

| Endpoint | Description |
|---|---|
| `GET /items/{uuid}` | Item metadata, captures list, content type |
| `GET /items/{uuid}/citations` | Citation data |
| `GET /captures/{uuid}/metadata` | Capture-level metadata |
| `GET /collections/{uuid}` | Collection info |

The key name was found in the [digital-collections source](https://github.com/NYPL/digital-collections/blob/main/app/src/utils/fetchApi/fetchApi.ts).

## Repo API (Legacy)

Base URL: `https://api.repo.nypl.org/api/v2/`

Auth: `Authorization: Token token="YOUR_TOKEN"` header. Sign up at <https://api.repo.nypl.org/sign_up>. Rate limit: 10,000 requests/day.

Key endpoints:

- `GET /items/{uuid}` — capture UUIDs and metadata
- `GET /items/item_details/{uuid}` — full capture details with image links
- `GET /items/mods_captures/{uuid}` — MODS metadata plus captures
- `GET /mods/{uuid}` — bibliographic metadata (MODS XML)
- `GET /items/search?q={query}` — full-text search
- `GET /items/plain_text/{uuid}` — OCR text from captures
- `GET /collections` — list all collections
- `GET /collections/{uuid}` — collection details and children

All endpoints accept `.json` or `.xml` suffix. Pagination via `page` and `per_page` (max 500).

## Manifest Structure

The IIIF v3 manifest follows this structure:

```
manifest
├── @context: "http://iiif.io/api/presentation/3/context.json"
├── id: manifest URL
├── type: "Manifest"
├── label: item title
├── behavior: ["paged"]
├── metadata: array of label/value pairs
├── summary: parent collection info ("Title || collection-uuid")
├── rights: rights URI
├── requiredStatement: attribution text
└── items: array of canvases
    └── canvas
        ├── id: canvas URI
        ├── label: page number
        ├── width / height: display dimensions (may not match actual image)
        ├── thumbnail: small image URL
        ├── items: annotation pages
        │   └── annotation page
        │       └── items: annotations
        │           └── annotation
        │               └── body
        │                   ├── id: image URL
        │                   ├── type: "Image"
        │                   ├── format: "image/jpeg"
        │                   └── service: array of IIIF image services
        │                       └── { id: "https://iiif.nypl.org/iiif/3/{imageId}", type: "ImageService3" }
        └── rendering: array of download options at various sizes
```

## Extracting Image IDs from a Manifest

Image IDs are integers (e.g. `1269894`) embedded in the service URLs. To extract them:

```python
import requests

manifest_url = "https://api-collections.nypl.org/manifests/{uuid}"
data = requests.get(manifest_url).json()

for canvas in data["items"]:
    label = canvas["label"]["en"][0]
    for ann_page in canvas["items"]:
        for ann in ann_page["items"]:
            for service in ann["body"].get("service", []):
                image_id = service["id"].rsplit("/", 1)[-1]
                print(f"Page {label}: {image_id}")
```

## Gotchas

- **Canvas dimensions lie.** The manifest reports uniform `2560x2560` canvas sizes, but actual image dimensions vary. Always check `info.json` for the real size.
- **`!` size syntax doesn't work.** IIIF 3.0's `!w,h` (best fit within box) and `^!w,h` (upscale to fit) return 400 errors on their Cantaloupe server. Use `max` or exact `w,h` instead.
- **No IIIF presentation endpoint on iiif.nypl.org.** URLs like `https://iiif.nypl.org/presentation/{uuid}/manifest` return 404. The manifest lives on `api-collections.nypl.org`.
- **Old image URLs.** Legacy URLs of the form `https://images.nypl.org/...` and `https://iiif-prod.nypl.org/index.php?id={id}&t=w` still exist but `iiif.nypl.org` is the current path.

## How the Official Frontend Works

The [NYPL/digital-collections](https://github.com/NYPL/digital-collections) repo is a Next.js app. The item viewer flow:

- Server-side page (`app/items/[uuid]/page.tsx`) fetches item data via authenticated Collections API
- `ItemModel` (`app/src/models/item.ts`) constructs the manifest URL
- The viewer component (`app/src/components/items/viewer/viewer.tsx`) passes the manifest URL to [UniversalViewer](https://universalviewer.io/)
- UniversalViewer embeds OpenSeadragon for tiled image display
- Image URLs are constructed via a utility at `app/src/utils/utils.ts`:
  ```
  https://iiif.nypl.org/iiif/3/${imageId}/${region}/${size}/${rotation}/default.jpg
  ```

## Quick Reference

| What | URL |
|---|---|
| Manifest (public) | `https://api-collections.nypl.org/manifests/{item-uuid}` |
| Full-res image | `https://iiif.nypl.org/iiif/3/{imageId}/full/max/0/default.jpg` |
| Image info | `https://iiif.nypl.org/iiif/3/{imageId}/info.json` |
| Thumbnail | `https://iiif.nypl.org/iiif/3/{imageId}/full/,150/0/default.jpg` |
| Repo API docs | `https://api.repo.nypl.org/` |
| Source code | `https://github.com/NYPL/digital-collections` |
