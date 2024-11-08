// chrome_extension/offscreen.js

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'parseHTML') {
        const { html, url } = message;
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const title = doc.querySelector('title') ? doc.querySelector('title').innerText : '';

        // Remove all <style> and <script> elements from the document
        doc.querySelectorAll('style, script').forEach(el => el.remove());

        // Get clean text content from the document body, excluding styles and scripts
        const text = doc.body ? doc.body.innerText : '';

        // Get the base URL for resolving relative links
        const baseUrl = new URL(url);

        // Extract and convert links to absolute URLs
        const links = Array.from(doc.querySelectorAll('a[href]'))
            .map(a => {
                const href = a.getAttribute('href');
                return href.startsWith('http') ? href : new URL(href, baseUrl).href;
            })
            .filter(href => href.startsWith('http'));  // Ensure it's a valid HTTP(S) link

        // Extract favicon URL
        let faviconUrl = '';
        const faviconElement = doc.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
        if (faviconElement) {
            faviconUrl = faviconElement.getAttribute('href');
        }

        // Resolve relative favicon URL
        if (faviconUrl && !faviconUrl.startsWith('http')) {
            faviconUrl = new URL(faviconUrl, baseUrl.origin).href;
        }

        // Send parsed data back to the client
        sendResponse({ title, text, links, faviconUrl });
    }
    return true;  // Indicates asynchronous response
});
