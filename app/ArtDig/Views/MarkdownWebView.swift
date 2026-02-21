import SwiftUI
@preconcurrency import WebKit

struct MarkdownWebView: UIViewRepresentable {
    let markdownContent: String
    let onArtworkTapped: (ArtworkLink) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onArtworkTapped: onArtworkTapped)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(context.coordinator, name: "linkTapped")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear

        #if DEBUG
        webView.isInspectable = true
        #endif

        if let templateURL = Bundle.main.url(forResource: "guide", withExtension: "html") {
            webView.loadFileURL(templateURL, allowingReadAccessTo: templateURL.deletingLastPathComponent())
        }

        context.coordinator.pendingMarkdown = markdownContent
        context.coordinator.currentMarkdown = markdownContent
        context.coordinator.linkParser.preprocess(markdown: markdownContent)

        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let coordinator = context.coordinator
        guard coordinator.currentMarkdown != markdownContent else { return }
        coordinator.currentMarkdown = markdownContent
        coordinator.linkParser.preprocess(markdown: markdownContent)

        if coordinator.isTemplateLoaded {
            coordinator.injectMarkdown(markdownContent, into: webView)
        } else {
            coordinator.pendingMarkdown = markdownContent
        }
    }

    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        let onArtworkTapped: (ArtworkLink) -> Void
        let linkParser = MarkdownLinkParser()
        var currentMarkdown: String = ""
        var pendingMarkdown: String?
        var isTemplateLoaded = false

        init(onArtworkTapped: @escaping (ArtworkLink) -> Void) {
            self.onArtworkTapped = onArtworkTapped
        }

        // MARK: - WKScriptMessageHandler

        func userContentController(_ userContentController: WKUserContentController,
                                   didReceive message: WKScriptMessage) {
            guard message.name == "linkTapped",
                  let urlString = message.body as? String,
                  let url = URL(string: urlString) else { return }

            if let artwork = linkParser.artworkLink(for: url) {
                onArtworkTapped(artwork)
            } else {
                print("Unrecognized link tapped: \(urlString)")
            }
        }

        // MARK: - Markdown injection

        func injectMarkdown(_ markdown: String, into webView: WKWebView) {
            let escaped = markdown
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "`", with: "\\`")
                .replacingOccurrences(of: "$", with: "\\$")
            webView.evaluateJavaScript("renderMarkdown(`\(escaped)`)") { _, error in
                if let error {
                    print("Markdown injection error: \(error)")
                }
            }
        }

        // MARK: - WKNavigationDelegate

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            isTemplateLoaded = true
            if let pending = pendingMarkdown {
                pendingMarkdown = nil
                injectMarkdown(pending, into: webView)
            }
        }

        // Safety net: cancel all non-file navigations
        func webView(_ webView: WKWebView,
                     decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.allow)
                return
            }

            if url.isFileURL {
                decisionHandler(.allow)
            } else {
                decisionHandler(.cancel)
            }
        }
    }
}
