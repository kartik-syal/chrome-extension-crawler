chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'capturePage') {
        const pageData = {
            url: window.location.href,
            title: document.title,
            content: document.body.innerText,
        };

        // Send page data to background script
        chrome.runtime.sendMessage({ action: 'pageCaptured', pageData });
        sendResponse({ success: true });
    }
});
