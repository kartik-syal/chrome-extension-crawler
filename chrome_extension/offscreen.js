// chrome_extension/offscreen.js

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'parseHTML') {
        const { html, url } = message;
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const title = doc.querySelector('title') ? doc.querySelector('title').innerText : '';
        const text = doc.body ? doc.body.innerText : '';

        // Extract links
        const links = Array.from(doc.querySelectorAll('a[href]'))
            .map(a => a.href)
            .filter(href => href.startsWith('http'));

        // Extract favicon URL
        let faviconUrl = '';
        const faviconElement = doc.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
        if (faviconElement) {
            faviconUrl = faviconElement.getAttribute('href');
        }

        // Resolve relative favicon URL
        if (faviconUrl && !faviconUrl.startsWith('http')) {
            // If the favicon is relative, resolve it using the page's origin
            const baseUrl = new URL(url).origin;
            faviconUrl = new URL(faviconUrl, baseUrl).href;
        }

        // Send parsed data back to the client
        sendResponse({ title, text, links, faviconUrl });
    }
    return true; // Indicates asynchronous response
});