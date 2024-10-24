let crawls = [];

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'startCrawl') {
        const { crawlName, crawlUrl, crawlDepth, maxLinks, followExternal, concurrency } = message;

        const crawlId = Date.now();
        const crawl = {
            id: crawlId,
            name: crawlName,
            url: crawlUrl,  // Add the crawl URL here
            depth: crawlDepth,
            maxLinks,
            followExternal,
            concurrency,
            status: 'Running',
            completedPages: 0,
            startTime: new Date().toISOString(),
        };

        // Add crawl to the list
        crawls.push(crawl);

        // Simulate crawl process (just for demo)
        startCrawlSimulation(crawlId);
    }

    sendResponse({ success: true });
});


function startCrawlSimulation(crawlId) {
    const crawl = crawls.find(c => c.id === crawlId);

    if (!crawl) return;

    // Simulate crawl process by updating the crawl status every second
    const intervalId = setInterval(() => {
        crawl.completedPages += 10;  // Simulating 10 pages crawled per second

        // Stop simulation after reaching the max number of links
        if (crawl.completedPages >= crawl.maxLinks) {
            crawl.status = 'Completed';
            clearInterval(intervalId);

            // Mock sending crawl data to backend
            sendCrawlDataToBackend(crawl);
        }
    }, 1000);
}

function sendCrawlDataToBackend(crawl) {
    console.log('Sending crawl data to backend:', crawl);

    // Simulate a backend call (FastAPI) with a POST request
    fetch('https://mock-fastapi-backend.com/crawl', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(crawl),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Backend response:', data);
    })
    .catch(error => {
        console.error('Error sending data to backend:', error);
    });
}
