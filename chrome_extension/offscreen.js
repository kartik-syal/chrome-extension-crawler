// chrome_extension/offscreen.js

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'parseHTML') {
        const { html } = message;
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const title = doc.querySelector('title') ? doc.querySelector('title').innerText : '';
        const text = doc.body ? doc.body.innerText : '';

        // Extract links
        const links = Array.from(doc.querySelectorAll('a[href]'))
            .map(a => a.href)
            .filter(href => href.startsWith('http'));

        sendResponse({ title, text, links });
    }
    return true; // Indicates that the response is sent asynchronously
});
