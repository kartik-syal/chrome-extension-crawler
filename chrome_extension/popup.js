// When the popup loads, get the active tab's URL and title
document.addEventListener('DOMContentLoaded', function () {
    // Fetch the active tab's URL and title
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        const activeTab = tabs[0];
        const pageTitle = activeTab.title;  // Get the title of the current page
        const pageUrl = activeTab.url;      // Get the URL of the current page

        // Prefill the form fields
        document.getElementById('crawlName').value = pageTitle;
        document.getElementById('crawlUrl').value = pageUrl;
    });
});

// Start crawl when the button is clicked
document.getElementById('startCrawl').addEventListener('click', function () {
    const crawlName = document.getElementById('crawlName').value || document.title;
    const crawlUrl = document.getElementById('crawlUrl').value;
    const crawlDepth = parseInt(document.getElementById('crawlDepth').value);
    const maxLinks = parseInt(document.getElementById('maxLinks').value);
    const followExternal = document.getElementById('followExternal').checked;
    const concurrency = parseInt(document.getElementById('concurrency').value);

    // Send settings to background script to start crawl
    chrome.runtime.sendMessage({
        action: 'startCrawl',
        crawlName,
        crawlUrl,
        crawlDepth,
        maxLinks,
        followExternal,
        concurrency
    });

    // Add crawl status to the list
    const crawlList = document.getElementById('crawlList');
    const crawlItem = document.createElement('li');
    crawlItem.textContent = `${crawlName} - Running...`;
    crawlList.appendChild(crawlItem);
});
