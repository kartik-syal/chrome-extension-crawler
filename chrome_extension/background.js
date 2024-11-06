const API_URL = 'http://127.0.0.1:8000';

chrome.runtime.onInstalled.addListener(() => {
    // Ensure UUID creation on first installation
    chrome.storage.local.get("userUUID", (data) => {
        if (!data.userUUID) {
            const uuid = crypto.randomUUID();
            chrome.storage.local.set({ userUUID: uuid });
        }
    });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'startClientCrawl') {
        const crawlConfig = message.crawlConfig;
        startClientCrawl(crawlConfig);
        sendResponse({ message: 'Client-side crawling started' });
    }
    return true; // Indicates that the response is sent asynchronously
});

async function startClientCrawl(crawlConfig) {
    // Create crawl session in the backend
    const response = await fetch(`${API_URL}/create-crawl-session/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(crawlConfig)
    });

    if (response.ok) {
        const result = await response.json();
        const crawlId = result.crawl_id;

        // Ensure the offscreen document is created
        await ensureOffscreenDocument();

        // Start crawling process
        crawlConfig.crawl_id = crawlId;
        crawlConfig.crawl_session_id = result.crawl_session_id;
        clientCrawler(crawlConfig);
    } else {
        console.error('Failed to create crawl session:', response.statusText);
    }
}

async function ensureOffscreenDocument() {
    const offscreenUrl = 'offscreen.html';

    const existing = await chrome.offscreen.hasDocument();
    if (existing) {
        return;
    }

    await chrome.offscreen.createDocument({
        url: offscreenUrl,
        reasons: [chrome.offscreen.Reason.DOM_PARSER],
        justification: 'Parse HTML content to extract links'
    });
}

async function clientCrawler(crawlConfig) {
    const {
        crawl_id,
        user_id,
        start_urls,
        max_links,
        follow_external,
        depth_limit,
        concurrent_requests,
        delay,
        only_child_pages,
        crawl_session_id
    } = crawlConfig;

    let queue = [];
    let visited = new Set();
    let linkCount = 0;

    // Initialize the queue with the start URLs
    start_urls.forEach(url => queue.push({ url, depth: 0 }));

    const baseUrl = new URL(start_urls[0]);
    const baseDomain = baseUrl.hostname;
    let basePath = baseUrl.pathname;

    // Adjust basePath for only_child_pages
    if (only_child_pages) {
        if (basePath.includes('.')) {
            basePath = basePath.substring(0, basePath.lastIndexOf('/') + 1);
        }
        if (!basePath.endsWith('/')) {
            basePath += '/';
        }
    }

    while (queue.length > 0 && linkCount < max_links) {
        const current = queue.shift();
        const { url, depth } = current;

        // Skip the URL if already visited or depth exceeds limit
        if (visited.has(url) || depth > depth_limit) {
            continue;
        }

        visited.add(url);

        try {
            const response = await fetch(url, { credentials: 'omit' });
            const contentType = response.headers.get('Content-Type');
            if (!contentType || !contentType.includes('text/html')) {
                continue;  // Only process HTML content
            }
            const html = await response.text();

            // Parse HTML in the offscreen document
            const parsedData = await parseHTMLInOffscreen(html, url);
            const { title, text, links, faviconUrl } = parsedData;

            // Send data to backend
            const websiteData = {
                website_url: url,
                title: title,
                text: text,
                html: html,
                status: true,
                crawl_session_id: crawl_session_id,
                favicon_url: faviconUrl 
            };
            
            linkCount++;

            // the combined request body
            const combinedRequest = {
                website_data: websiteData,  
                crawl_session_update: {
                    crawl_id: crawl_id,
                    link_count: linkCount
                }
            };

            // Send the store-data request to your backend API
            await fetch(`${API_URL}/store-website-data/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(combinedRequest)
            }).then(response => {
                if (response.ok) {
                    console.log("Data stored and crawl session updated successfully");
                } else {
                    console.error("Error while processing the request:", response);
                }
            }).catch(error => {
                console.error("Request failed:", error);
            });

            // Crawl links found in the current page (child links)
            for (const link of links) {
                const linkUrl = new URL(link);

                // Apply follow_external and only_child_pages filters
                if (!follow_external && linkUrl.hostname !== baseDomain) {
                    continue;
                }

                if (only_child_pages) {
                    let linkPath = linkUrl.pathname;
                    if (linkPath.includes('.')) {
                        linkPath = linkPath.substring(0, linkPath.lastIndexOf('/') + 1);
                    }
                    if (!linkPath.endsWith('/')) {
                        linkPath += '/';
                    }
                    if (!linkPath.startsWith(basePath)) {
                        continue;
                    }
                }

                // If the link is not visited, add it to the queue for further crawling
                if (!visited.has(link)) {
                    queue.push({ url: link, depth: depth + 1 });
                }
            }

            // Delay if needed
            if (delay > 0) {
                await new Promise(resolve => setTimeout(resolve, delay * 1000));
            }

        } catch (error) {
            console.error(`Error fetching ${url}: ${error}`);
        }
    }

    // Update crawl session status to 'completed' in backend
    await fetch(`${API_URL}/store-website-data/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            crawl_session_update: {
            crawl_id: crawl_id,
            status: "completed"
            }
        })
    });

    console.log('Client-side crawling completed');

    // Close the offscreen document
    await chrome.offscreen.closeDocument();
}

async function parseHTMLInOffscreen(html, url) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ action: 'parseHTML', html, url }, (response) => {
            if (chrome.runtime.lastError) {
                console.error(chrome.runtime.lastError);
                reject(chrome.runtime.lastError);
            } else {
                resolve(response);
            }
        });
    });
}